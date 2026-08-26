from collections import defaultdict
from typing import Dict, List
from app.optimization.base import SignalOptimizer, IntersectionState, OptimizationResult, PhaseDuration

class WebsterOptimizer(SignalOptimizer):
    """
    Classic Webster's Method for optimal cycle length and phase split:
    C_opt = (1.5 * L + 5) / (1 - Y)
    where L = Total lost time, Y = sum(flow / saturation_flow for critical lanes).
    """
    def optimize(self, state: IntersectionState) -> OptimizationResult:
        c = state.constraints
        
        # Determine critical flow ratio (y_i = flow / sat_flow) per phase group
        group_flow_ratios: Dict[str, float] = defaultdict(float)
        for lane in state.lanes:
            sat_flow = lane.saturation_flow if lane.saturation_flow > 0 else 1800.0
            # Convert current vehicle count in interval to approximate vehicles/hour
            hourly_flow = lane.vehicle_count * 60.0
            ratio = min(hourly_flow / sat_flow, 0.90)  # Cap ratio to avoid divide-by-zero
            if ratio > group_flow_ratios[lane.phase_group]:
                group_flow_ratios[lane.phase_group] = ratio

        phases = sorted(list(group_flow_ratios.keys()))
        if not phases:
            phases = ["phase_1", "phase_2"]
            group_flow_ratios = {"phase_1": 0.05, "phase_2": 0.05}

        num_phases = len(phases)
        total_lost_time = num_phases * (c.yellow_time + c.all_red_time)
        Y = sum(group_flow_ratios.values())

        # Enforce practical upper bound on Y for stability
        Y = min(Y, 0.85)

        if Y < 0.05:
            # Under near-empty flow conditions, use minimum safe cycle
            opt_cycle = c.min_cycle
        else:
            webster_cycle = (1.5 * total_lost_time + 5.0) / (1.0 - Y)
            opt_cycle = int(round(webster_cycle))

        clamped_cycle = max(c.min_cycle, min(opt_cycle, c.max_cycle))
        available_green = max(num_phases * c.min_green, clamped_cycle - total_lost_time)

        phase_durations: List[PhaseDuration] = []
        for phase_name in phases:
            if Y > 0:
                proportion = group_flow_ratios[phase_name] / Y
            else:
                proportion = 1.0 / num_phases

            green_time = int(round(proportion * available_green))
            clamped_green = max(c.min_green, min(green_time, c.max_green))

            phase_durations.append(
                PhaseDuration(
                    phase=phase_name,
                    green=clamped_green,
                    yellow=c.yellow_time,
                    all_red=c.all_red_time
                )
            )

        final_cycle = sum(p.green for p in phase_durations) + total_lost_time
        final_cycle = max(c.min_cycle, min(final_cycle, c.max_cycle))

        next_phase = max(group_flow_ratios.items(), key=lambda x: x[1])[0]

        return OptimizationResult(
            intersection_id=state.intersection_id,
            cycle_length=final_cycle,
            phases=phase_durations,
            next_phase=next_phase,
            algorithm="webster"
        )
        