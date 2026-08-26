from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass
class SimulatedLaneMetric:
    lane_id: str
    vehicle_count: int
    queue_length: float
    average_speed: float
    occupancy: float

@dataclass
class SimulationStepResult:
    step: int
    timestamp: float
    active_vehicles: int
    lanes: Dict[str, SimulatedLaneMetric]

class SimulationClient(ABC):
    @abstractmethod
    async def connect(self) -> bool:
        """Establishes connection to the simulation instance."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Closes connection to the simulation."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Returns True if connected to an active simulation."""
        pass

    @abstractmethod
    async def step(self) -> SimulationStepResult:
        """Advances simulation by one step and extracts telemetry."""
        pass

    @abstractmethod
    async def set_signal_phase(self, intersection_id: str, phase_index: int) -> bool:
        """Forces the traffic light to a specific phase."""
        pass

    @abstractmethod
    async def set_signal_program(self, intersection_id: str, phases: List[Dict[str, Any]]) -> bool:
        """Updates traffic light program with calculated green splits."""
        pass