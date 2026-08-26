import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from vision.tracker import LaneTracker
from vision.publisher import VisionTelemetryPublisher

@pytest.mark.asyncio
async def test_full_pipeline_flow(async_client: AsyncClient):
    with patch("app.core.redis.redis_manager.set_state", new_callable=AsyncMock) as mock_set, \
         patch("app.core.redis.redis_manager.publish_event", new_callable=AsyncMock) as mock_pub, \
         patch("app.websocket.manager.websocket_manager.broadcast_to_intersection", new_callable=AsyncMock) as mock_ws:

        # 1. Vision Ingestion
        telemetry_payload = {
            "intersection_id": "INT-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "lanes": [
                {"lane_id": "north", "vehicle_count": 30, "average_speed": 10.0, "queue_length": 45.0, "occupancy": 0.85},
                {"lane_id": "east", "vehicle_count": 5, "average_speed": 40.0, "queue_length": 2.0, "occupancy": 0.15}
            ]
        }
        res_ingest = await async_client.post("/api/v1/telemetry/ingest", json=telemetry_payload)
        assert res_ingest.status_code == 200
        assert res_ingest.json()["congestion_score"] > 30.0

        # 2. Signal Optimization Trigger
        opt_payload = {
            "algorithm": "queue_based",
            "lanes": [
                {"lane_id": "north", "phase_group": "north_south", "vehicle_count": 30, "queue_length": 45.0, "average_speed": 10.0},
                {"lane_id": "east", "phase_group": "east_west", "vehicle_count": 5, "queue_length": 2.0, "average_speed": 40.0}
            ]
        }
        res_opt = await async_client.post("/api/v1/signals/INT-001/optimize", json=opt_payload)
        assert res_opt.status_code == 200
        assert res_opt.json()["next_phase"] == "north_south"

        # 3. Emergency Override Trigger
        em_payload = {
            "vehicle_id": "AMB-E2E",
            "vehicle_type": "ambulance",
            "current_position": [12.9700, 77.5946],
            "route_coordinates": [[12.9700, 77.5946], [12.9750, 77.5946]],
            "priority_level": 1
        }
        res_em = await async_client.post("/api/v1/emergency/corridor", json=em_payload)
        assert res_em.status_code == 200
        assert res_em.json()["corridor_active"] is True

        # 4. Status Snapshot Check
        res_status = await async_client.get("/api/v1/intersections/INT-001/status")
        assert res_status.status_code == 200
        assert res_status.json()["intersection_id"] == "INT-001"

def test_vision_tracker_and_publisher():
    tracker = LaneTracker(lane_ids=["lane_a", "lane_b"])
    metrics = tracker.process_detections()
    assert len(metrics) == 2
    assert "queue_length" in metrics[0]

    with patch("httpx.Client.post") as mock_http:
        mock_http.return_value.status_code = 200
        pub = VisionTelemetryPublisher(api_url="http://test/ingest")
        success = pub.publish_frame_metrics("INT-001", metrics)
        assert success is True