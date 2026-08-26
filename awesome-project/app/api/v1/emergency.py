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
