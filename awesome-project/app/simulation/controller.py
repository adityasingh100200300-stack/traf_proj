import logging
from typing import Optional
from app.core.config import settings
from app.simulation.base import SimulationClient
from app.simulation.mock_client import MockSimulationClient
from app.simulation.sumo_client import SumoTraCIClient
from app.services.signal_service import SignalService
from app.schemas.signal import OptimizeRequest, LaneStateInput

logger = logging.getLogger(__name__)

class SimulationController:
    _client: Optional[SimulationClient] = None

    @classmethod
    def get_client(cls) -> SimulationClient:
        if cls._client is None:
            if settings.SIMULATION_MODE.lower() == "traci":
                cls._client = SumoTraCIClient(
                    sumo_binary=settings.SUMO_BINARY,
                    config_file=settings.SUMO_CONFIG,
                    port=settings.SUMO_PORT
                )
            else:
                cls._client = MockSimulationClient()
        return cls._client

    @classmethod
    async def step_and_sync(cls, intersection_id: str = "INT-001") -> dict:
        """
        Advances the simulation by one step, extracts simulated road telemetry,
        runs the SignalOptimizer, and applies updated timing plans back into the simulation.
        """
        client = cls.get_client()
        if not await client.is_connected():
            await client.connect()

        # 1. Step simulation & fetch state
        step_result = await client.step()

        # 2. Build lane states for optimizer
        lane_inputs = []
        for lane_id, metric in step_result.lanes.items():
            group = "north_south" if "north" in lane_id or "south" in lane_id else "east_west"
            lane_inputs.append(
                LaneStateInput(
                    lane_id=lane_id,
                    phase_group=group,
                    vehicle_count=metric.vehicle_count,
                    queue_length=metric.queue_length,
                    average_speed=metric.average_speed
                )
            )

        # 3. Optimize signals based on simulation state
        opt_response = await SignalService.optimize_intersection(
            intersection_id=intersection_id,
            request=OptimizeRequest(algorithm="queue_based", lanes=lane_inputs)
        )

        # 4. Push optimized plan into simulation client
        phase_dict = [{"phase": p.phase, "green": p.green, "yellow": p.yellow} for p in opt_response.phases]
        await client.set_signal_program(intersection_id, phase_dict)

        return {
            "step": step_result.step,
            "active_vehicles": step_result.active_vehicles,
            "applied_cycle": opt_response.cycle_length,
            "next_phase": opt_response.next_phase,
            "lanes": {k: v.__dict__ for k, v in step_result.lanes.items()}
        }