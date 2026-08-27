from fastapi import APIRouter, status
from app.schemas.emergency import EmergencyCorridorRequest, EmergencyCorridorResponse
from app.services.emergency_service import EmergencyService

router = APIRouter()

@router.post(
    "/emergency/corridor",
    response_model=EmergencyCorridorResponse,
    status_code=status.HTTP_200_OK,
    summary="Create emergency vehicle priority green corridor",
    description="Calculates affected intersections along an emergency vehicle's GPS route and triggers priority green signal overrides."
)
async def create_emergency_corridor(payload: EmergencyCorridorRequest):
    return await EmergencyService.create_corridor(payload)

@router.post(
    "/emergency/corridor/clear",
    status_code=status.HTTP_200_OK,
    summary="Clear active emergency green corridor",
    description="Releases emergency priority lockout and restores normal signal cycles."
)
async def clear_emergency_corridor(intersection_id: str = "INT-001", vehicle_id: str = "AMB-911"):
    return await EmergencyService.clear_corridor(vehicle_id=vehicle_id, intersection_ids=[intersection_id])
