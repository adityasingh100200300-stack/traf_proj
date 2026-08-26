import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.utils.geometry import haversine_distance, calculate_bearing, bearing_to_phase_group, is_point_near_segment

def test_haversine_distance():
    # Approx distance between two known points in Bangalore (~380m)
    p1 = (12.9716, 77.5946)
    p2 = (12.9750, 77.5948)
    dist = haversine_distance(p1, p2)
    assert 350.0 < dist < 420.0

def test_bearing_and_phase_mapping():
    # Direct North movement
    p_start = (12.9700, 77.5946)
    p_end = (12.9800, 77.5946)
    bearing = calculate_bearing(p_start, p_end)
    assert 0.0 <= bearing <= 5.0 or 355.0 <= bearing <= 360.0
    assert bearing_to_phase_group(bearing) == "north_south"

    # Direct East movement
    p_east = (12.9700, 77.6046)
    bearing_east = calculate_bearing(p_start, p_east)
    assert 85.0 <= bearing_east <= 95.0
    assert bearing_to_phase_group(bearing_east) == "east_west"

def test_point_near_segment():
    seg_start = (12.9700, 77.5946)
    seg_end = (12.9800, 77.5946)
    point_on_path = (12.9750, 77.5946)
    point_far_away = (13.5000, 78.5000)

    assert is_point_near_segment(point_on_path, seg_start, seg_end, threshold_meters=100.0) is True
    assert is_point_near_segment(point_far_away, seg_start, seg_end, threshold_meters=100.0) is False

@pytest.mark.asyncio
async def test_emergency_corridor_endpoint(async_client: AsyncClient):
    with patch("app.core.redis.redis_manager.set_state", new_callable=AsyncMock), \
         patch("app.core.redis.redis_manager.publish_event", new_callable=AsyncMock), \
         patch("app.websocket.manager.websocket_manager.broadcast_to_intersection", new_callable=AsyncMock):

        payload = {
            "vehicle_id": "AMB-911",
            "vehicle_type": "ambulance",
            "current_position": [12.9700, 77.5946],
            "route_coordinates": [
                [12.9700, 77.5946],
                [12.9730, 77.5946],
                [12.9760, 77.5948]
            ],
            "priority_level": 1
        }
        response = await async_client.post("/api/v1/emergency/corridor", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["vehicle_id"] == "AMB-911"
        assert data["corridor_active"] is True
        assert len(data["affected_intersections"]) >= 1
        assert data["affected_intersections"][0]["override_phase"] == "north_south"