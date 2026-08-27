import json
from fastapi import APIRouter, status
from pydantic import BaseModel
from app.schemas.signal import OptimizeRequest, OptimizeResponse
from app.services.signal_service import SignalService
from app.core.redis import redis_manager
from app.websocket.manager import websocket_manager

router = APIRouter()

class PhaseOverrideRequest(BaseModel):
    phase: str  # "north_south" or "east_west"

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

@router.post(
    "/signals/{intersection_id}/override-phase",
    status_code=status.HTTP_200_OK,
    summary="Manually switch active green corridor phase",
    description="Forces immediate signal transition to specified phase group."
)
async def override_phase(
    intersection_id: str,
    payload: PhaseOverrideRequest
):
    signal_state = {
        "intersection_id": intersection_id,
        "cycle_length": 60,
        "next_phase": payload.phase,
        "algorithm": "manual_override",
        "phases": []
    }
    await redis_manager.set_state(f"signal:{intersection_id}", signal_state, expire=3600)
    await redis_manager.publish_event(f"signal:{intersection_id}", signal_state)

    event = {
        "type": "phase_override",
        "intersection_id": intersection_id,
        "active_phase": payload.phase
    }
    await websocket_manager.broadcast_to_intersection(intersection_id, json.dumps(event))
    return {"status": "success", "active_phase": payload.phase}