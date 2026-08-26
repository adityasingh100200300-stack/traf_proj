import json
import logging
from typing import List, Dict, Any, Tuple
from app.schemas.emergency import EmergencyCorridorRequest, EmergencyCorridorResponse, AffectedIntersectionOverride
from app.utils.geometry import haversine_distance, calculate_bearing, bearing_to_phase_group, is_point_near_segment
from app.core.redis import redis_manager
from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)

# Known intersection layout coordinates for mock/prototype operations
REGISTERED_INTERSECTIONS = {
    "INT-001": {"lat": 12.9716, "lon": 77.5946, "name": "Central Crossing"},
    "INT-002": {"lat": 12.9750, "lon": 77.5948, "name": "North Junction"},
    "INT-003": {"lat": 12.9718, "lon": 77.6000, "name": "East Crossing"}
}

class EmergencyService:
    @classmethod
    async def create_corridor(cls, request: EmergencyCorridorRequest) -> EmergencyCorridorResponse:
        affected: List[AffectedIntersectionOverride] = []
        route = request.route_coordinates

        for int_id, info in REGISTERED_INTERSECTIONS.items():
            int_coord = (info["lat"], info["lon"])
            
            # Check proximity to any segment along the vehicle's planned path
            for i in range(len(route) - 1):
                seg_start = route[i]
                seg_end = route[i + 1]

                if is_point_near_segment(int_coord, seg_start, seg_end, threshold_meters=200.0):
                    bearing = calculate_bearing(seg_start, seg_end)
                    override_phase = bearing_to_phase_group(bearing)
                    dist = haversine_distance(request.current_position, int_coord)

                    affected.append(
                        AffectedIntersectionOverride(
                            intersection_id=int_id,
                            override_phase=override_phase,
                            green_duration=90,  # Extended green window for emergency corridor
                            distance_meters=round(dist, 1)
                        )
                    )
                    break

        # Publish override events for every affected intersection
        for item in affected:
            override_event = {
                "type": "emergency_override",
                "vehicle_id": request.vehicle_id,
                "vehicle_type": request.vehicle_type,
                "intersection_id": item.intersection_id,
                "override_phase": item.override_phase,
                "green_duration": item.green_duration,
                "active": True
            }

            # Cache lock in Redis and publish to Redis Pub/Sub
            await redis_manager.set_state(f"emergency:{item.intersection_id}", override_event, expire=180)
            await redis_manager.publish_event(f"emergency:{item.intersection_id}", override_event)

            # Broadcast directly to UI dashboard clients
            await websocket_manager.broadcast_to_intersection(
                intersection_id=item.intersection_id,
                message=json.dumps(override_event)
            )

        return EmergencyCorridorResponse(
            status="success" if affected else "no_intersections_affected",
            vehicle_id=request.vehicle_id,
            corridor_active=bool(affected),
            affected_intersections=affected,
            message=f"Created green corridor across {len(affected)} intersections."
        )

    @classmethod
    async def clear_corridor(cls, vehicle_id: str, intersection_ids: List[str]) -> dict:
        for int_id in intersection_ids:
            clear_event = {
                "type": "emergency_clear",
                "vehicle_id": vehicle_id,
                "intersection_id": int_id,
                "active": False
            }
            await redis_manager.set_state(f"emergency:{int_id}", clear_event, expire=10)
            await redis_manager.publish_event(f"emergency:{int_id}", clear_event)
            await websocket_manager.broadcast_to_intersection(
                intersection_id=int_id,
                message=json.dumps(clear_event)
            )
        return {"status": "cleared", "vehicle_id": vehicle_id, "cleared_intersections": intersection_ids}