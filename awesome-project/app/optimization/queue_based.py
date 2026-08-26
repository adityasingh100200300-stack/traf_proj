from collections import defaultdict
from typing import Dict, List
from app.optimization.base import SignalOptimizer, IntersectionState, OptimizationResult, PhaseDuration

class QueueBasedOptimizer(SignalOptimizer):
    """
    Allocates effective cycle time proportionally to maximum queue lengths
    accumulated in competing phase groups.
    """
    def optimize(self, state: IntersectionState) -> OptimizationResult:
        c = state.constraints
        
        # Aggregate maximum queue per phase group
        group_queues: Dict[str, float] = defaultdict(float)
        for lane in state.lanes:
            if lane.queue_length > group_queues[lane.phase_group]:
                group_queues[lane.phase_group] = lane.queue_length

        phases = sorted(list(group_queues.keys()))
        if not phases:
            # Fallback if no lanes configured
            phases = ["phase_1", "phase_2"]
            group_queues = {"phase_1": 0.0, "phase_2": 0.0}

        num_phases = len(phases)
        total_lost_time = num_phases * (c.yellow_time + c.all_red_time)
        total_queue = sum(group_queues.values())

        phase_durations: List[PhaseDuration] = []

        if total_queue == 0:
            # Equal distribution under empty conditions
            base_green = c.min_green
            for phase_name in phases:
                phase_durations.append(
                    PhaseDuration(
                        phase=phase_name,
                        green=base_green,
                        yellow=c.yellow_time,
                        all_red=c.all_red_time
                    )
                )
            calculated_cycle = (base_green * num_phases) + total_lost_time
            actual_cycle = max(c.min_cycle, min(calculated_cycle, c.max_cycle))
            return OptimizationResult(
                intersection_id=state.intersection_id,
                cycle_length=actual_cycle,
                phases=phase_durations,
                next_phase=phases[0],
                algorithm="queue_based"
            )

        # Scale cycle length dynamically with overall queue pressure
        estimated_cycle = int(total_lost_time + (total_queue * 1.5))
        effective_cycle = max(c.min_cycle, min(estimated_cycle, c.max_cycle))
        available_green = max(0, effective_cycle - total_lost_time)

        assigned_green = {}
        for phase_name in phases:
            proportion = group_queues[phase_name] / total_queue
            green_time = int(round(proportion * available_green))
            # Clamp green time to safety constraints
            clamped_green = max(c.min_green, min(green_time, c.max_green))
            assigned_green[phase_name] = clamped_green

        for phase_name in phases:
            phase_durations.append(
                PhaseDuration(
                    phase=phase_name,
                    green=assigned_green[phase_name],
                    yellow=c.yellow_time,
                    all_red=c.all_red_time
                )
            )

        # Total cycle is sum of greens plus lost time
        final_cycle = sum(p.green for p in phase_durations) + total_lost_time
        final_cycle = max(c.min_cycle, min(final_cycle, c.max_cycle))

        # Select highest-queue phase as next priority
        next_phase = max(group_queues.items(), key=lambda x: x[1])[0]

        return OptimizationResult(
            intersection_id=state.intersection_id,
            cycle_length=final_cycle,
            phases=phase_durations,
            next_phase=next_phase,
            algorithm="queue_based"
        )