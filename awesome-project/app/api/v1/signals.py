from fastapi import APIRouter, status
from app.schemas.signal import OptimizeRequest, OptimizeResponse
from app.services.signal_service import SignalService

router = APIRouter()

@router.post(
    "/signals/{intersection_id}/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute optimal signal phase durations",
    description="Executes deterministic queue-based or Webster adaptive signal optimization."
)
async def optimize_signals(
    intersection_id: str,
    payload: OptimizeRequest = OptimizeRequest()
):
    return await SignalService.optimize_intersection(intersection_id, payload)