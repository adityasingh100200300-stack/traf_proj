from pydantic import BaseModel, Field
from typing import List, Tuple, Optional

class EmergencyCorridorRequest(BaseModel):
    vehicle_id: str = Field(..., description="Unique vehicle ID, e.g., 'AMB-911'")
    vehicle_type: str = Field(default="ambulance", description="'ambulance', 'fire_truck', 'police'")
    current_position: Tuple[float, float] = Field(..., description="Current [lat, lon]")
    route_coordinates: List[Tuple[float, float]] = Field(..., min_length=2, description="List of [lat, lon] waypoints")
    priority_level: int = Field(default=1, ge=1, le=3, description="1 (highest) to 3 (standard)")

class AffectedIntersectionOverride(BaseModel):
    intersection_id: str
    override_phase: str
    green_duration: int
    distance_meters: float

class EmergencyCorridorResponse(BaseModel):
    status: str
    vehicle_id: str
    corridor_active: bool
    affected_intersections: List[AffectedIntersectionOverride]
    message: str