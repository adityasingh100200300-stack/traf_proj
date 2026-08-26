import json
import logging
from typing import Dict, Any, Type
from app.optimization.base import SignalOptimizer, IntersectionState, LaneState, SafetyConstraints
from app.optimization.queue_based import QueueBasedOptimizer
from app.optimization.webster import WebsterOptimizer
from app.schemas.signal import OptimizeRequest, OptimizeResponse, PhaseDurationOutput
from app.core.redis import redis_manager

logger = logging.getLogger(__name__)

class SignalService:
    _OPTIMIZERS: Dict[str, Type[SignalOptimizer]] = {
        "queue_based": QueueBasedOptimizer,
        "webster": WebsterOptimizer
    }

    @classmethod
    async def optimize_intersection(
        cls,
        intersection_id: str,
        request: OptimizeRequest
    ) -> OptimizeResponse:
        optimizer_class = cls._OPTIMIZERS.get(request.algorithm.lower(), QueueBasedOptimizer)
        optimizer = optimizer_class()

        lane_states = []
        if request.lanes:
            lane_states = [
                LaneState(
                    lane_id=l.lane_id,
                    phase_group=l.phase_group,
                    vehicle_count=l.vehicle_count,
                    queue_length=l.queue_length,
                    average_speed=l.average_speed
                ) for l in request.lanes
            ]
        else:
            # Fallback to cached Redis traffic state if direct payload omitted
            cached_data = await redis_manager.get_state(f"traffic:{intersection_id}")
            if cached_data and "traffic" in cached_data:
                for lane_id, data in cached_data["traffic"].items():
                    # Extract directional prefix for grouping (e.g. 'north_straight' -> 'north_south')
                    group = "north_south" if "north" in lane_id or "south" in lane_id else "east_west"
                    lane_states.append(
                        LaneState(
                            lane_id=lane_id,
                            phase_group=group,
                            vehicle_count=data.get("vehicles", 0),
                            queue_length=data.get("queue", 0.0),
                            average_speed=data.get("speed", 30.0)
                        )
                    )

        # Default minimal state if no inputs found
        if not lane_states:
            lane_states = [
                LaneState(lane_id="north", phase_group="north_south", vehicle_count=10, queue_length=5.0, average_speed=30.0),
                LaneState(lane_id="east", phase_group="east_west", vehicle_count=10, queue_length=5.0, average_speed=30.0)
            ]

        intersection_state = IntersectionState(
            intersection_id=intersection_id,
            lanes=lane_states,
            constraints=SafetyConstraints()
        )

        result = optimizer.optimize(intersection_state)

        # Cache new signal timing plan and publish event to Redis
        signal_state = {
            "intersection_id": result.intersection_id,
            "cycle_length": result.cycle_length,
            "next_phase": result.next_phase,
            "algorithm": result.algorithm,
            "phases": [{"phase": p.phase, "green": p.green, "yellow": p.yellow, "all_red": p.all_red} for p in result.phases]
        }
        await redis_manager.set_state(f"signal:{intersection_id}", signal_state, expire=3600)
        await redis_manager.publish_event(f"signal:{intersection_id}", signal_state)

        return OptimizeResponse(
            intersection_id=result.intersection_id,
            cycle_length=result.cycle_length,
            phases=[
                PhaseDurationOutput(phase=p.phase, green=p.green, yellow=p.yellow, all_red=p.all_red)
                for p in result.phases
            ],
            next_phase=result.next_phase,
            algorithm=result.algorithm
        )