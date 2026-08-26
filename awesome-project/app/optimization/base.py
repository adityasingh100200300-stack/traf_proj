from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass(frozen=True)
class SafetyConstraints:
    min_green: int = 10
    max_green: int = 60
    yellow_time: int = 4
    all_red_time: int = 2
    min_cycle: int = 40
    max_cycle: int = 150

@dataclass
class LaneState:
    lane_id: str
    phase_group: str  # e.g., 'north_south', 'east_west'
    vehicle_count: int
    queue_length: float
    average_speed: float
    saturation_flow: float = 1800.0  # vehicles per hour of green

@dataclass
class IntersectionState:
    intersection_id: str
    lanes: List[LaneState]
    current_phase: Optional[str] = None
    constraints: SafetyConstraints = field(default_factory=SafetyConstraints)

@dataclass
class PhaseDuration:
    phase: str
    green: int
    yellow: int
    all_red: int

@dataclass
class OptimizationResult:
    intersection_id: str
    cycle_length: int
    phases: List[PhaseDuration]
    next_phase: str
    algorithm: str

class SignalOptimizer(ABC):
    @abstractmethod
    def optimize(self, state: IntersectionState) -> OptimizationResult:
        """
        Calculates optimal phase splits and cycle length based on state.
        Must strictly adhere to state.constraints.
        """
        pass