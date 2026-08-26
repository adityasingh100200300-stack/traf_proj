from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class IntersectionStatusResponse(BaseModel):
    intersection_id: str
    name: str
    active_phase: str
    remaining_phase_time: int
    cycle_length: int
    congestion_score: float
    emergency_active: bool
    emergency_details: Optional[Dict[str, Any]] = None
    lanes: Dict[str, Any]
    last_updated: Optional[datetime] = None