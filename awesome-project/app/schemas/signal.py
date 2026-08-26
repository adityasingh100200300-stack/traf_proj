from pydantic import BaseModel, Field
from typing import List, Optional

class LaneStateInput(BaseModel):
    lane_id: str
    phase_group: str = Field(..., description="e.g., 'north_south', 'east_west'")
    vehicle_count: int = Field(default=0, ge=0)
    queue_length: float = Field(default=0.0, ge=0.0)
    average_speed: float = Field(default=30.0, ge=0.0)

class OptimizeRequest(BaseModel):
    algorithm: Optional[str] = Field(default="queue_based", description="'queue_based' or 'webster'")
    lanes: Optional[List[LaneStateInput]] = Field(default=None, description="Optional override state")

class PhaseDurationOutput(BaseModel):
    phase: str
    green: int
    yellow: int
    all_red: int

class OptimizeResponse(BaseModel):
    intersection_id: str
    cycle_length: int
    phases: List[PhaseDurationOutput]
    next_phase: str
    algorithm: str