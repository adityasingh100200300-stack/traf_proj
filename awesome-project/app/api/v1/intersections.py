from fastapi import APIRouter, status, HTTPException
from datetime import datetime, timezone
from app.schemas.intersection import IntersectionStatusResponse
from app.core.redis import redis_manager
from app.services.emergency_service import REGISTERED_INTERSECTIONS

router = APIRouter()

@router.get(
    "/intersections/{intersection_id}/status",
    response_model=IntersectionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get real-time intersection snapshot",
    description="Returns live active phase, current congestion, queue metrics, and active emergency priority overrides."
)
async def get_intersection_status(intersection_id: str):
    info = REGISTERED_INTERSECTIONS.get(intersection_id, {"name": f"Intersection {intersection_id}"})

    # 1. Fetch cached states from Redis
    traffic_state = await redis_manager.get_state(f"traffic:{intersection_id}") or {}
    signal_state = await redis_manager.get_state(f"signal:{intersection_id}") or {}
    emergency_state = await redis_manager.get_state(f"emergency:{intersection_id}") or {}

    active_emergency = emergency_state.get("active", False)
    active_phase = emergency_state.get("override_phase") if active_emergency else signal_state.get("next_phase", "north_south")
    cycle_len = signal_state.get("cycle_length", 60)
    congestion = traffic_state.get("congestion_score", 0.0)
    lanes = traffic_state.get("traffic", {})

    return IntersectionStatusResponse(
        intersection_id=intersection_id,
        name=info.get("name", intersection_id),
        active_phase=active_phase,
        remaining_phase_time=30,
        cycle_length=cycle_len,
        congestion_score=congestion,
        emergency_active=active_emergency,
        emergency_details=emergency_state if active_emergency else None,
        lanes=lanes,
        last_updated=datetime.now(timezone.utc)
    )