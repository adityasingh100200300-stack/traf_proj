from pydantic import BaseModel, Field
from typing import Dict, Any

class SimulationStepResponse(BaseModel):
    step: int
    active_vehicles: int
    applied_cycle: int
    next_phase: str
    lanes: Dict[str, Any]

class SimulationStatusResponse(BaseModel):
    connected: bool
    mode: str