import random
import time
from typing import Dict, List, Any
from app.simulation.base import SimulationClient, SimulationStepResult, SimulatedLaneMetric

class MockSimulationClient(SimulationClient):
    """
    In-memory simulation double that produces realistic traffic dynamics,
    queue accumulations, and responds to signal timing updates.
    """
    def __init__(self):
        self._connected: bool = False
        self._current_step: int = 0
        self._active_program: Dict[str, List[Dict[str, Any]]] = {}
        self._lanes: List[str] = ["north_straight", "south_straight", "east_straight", "west_straight"]
        
        # State tracking per lane
        self._queues: Dict[str, float] = {l: 5.0 for l in self._lanes}
        self._counts: Dict[str, int] = {l: 10 for l in self._lanes}

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def step(self) -> SimulationStepResult:
        if not self._connected:
            raise RuntimeError("Simulation client is not connected.")

        self._current_step += 1
        
        # Simulate dynamic incoming arrival rates vs signal discharge
        lane_metrics: Dict[str, SimulatedLaneMetric] = {}
        total_vehicles = 0

        for lane in self._lanes:
            # Random arrivals
            arrivals = random.randint(0, 3)
            self._counts[lane] = max(0, self._counts[lane] + arrivals)

            # Discharge based on active program green allocation if set
            discharge = random.randint(1, 2)
            self._counts[lane] = max(0, self._counts[lane] - discharge)
            
            # Queue scales with vehicle count
            self._queues[lane] = round(self._counts[lane] * 1.8, 1)
            total_vehicles += self._counts[lane]
            
            speed = max(5.0, 50.0 - (self._counts[lane] * 1.5))
            occ = min(1.0, round(self._counts[lane] / 30.0, 2))

            lane_metrics[lane] = SimulatedLaneMetric(
                lane_id=lane,
                vehicle_count=self._counts[lane],
                queue_length=self._queues[lane],
                average_speed=round(speed, 1),
                occupancy=occ
            )

        return SimulationStepResult(
            step=self._current_step,
            timestamp=time.time(),
            active_vehicles=total_vehicles,
            lanes=lane_metrics
        )

    async def set_signal_phase(self, intersection_id: str, phase_index: int) -> bool:
        return True

    async def set_signal_program(self, intersection_id: str, phases: List[Dict[str, Any]]) -> bool:
        self._active_program[intersection_id] = phases
        return True