import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from app.main import app
from app.services.telemetry_service import TelemetryService
from app.schemas.telemetry import LaneTelemetryInput

@pytest.fixture
def valid_telemetry_payload():
    return {
        "intersection_id": "INT-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lanes": [
            {
                "lane_id": "north_left",
                "vehicle_count": 12,
                "average_speed": 35.0,
                "queue_length": 6.0,
                "occupancy": 0.40,
                "vehicle_classes": {"car": 10, "bus": 2}
            },
            {
                "lane_id": "east_straight",
                "vehicle_count": 28,
                "average_speed": 15.0,
                "queue_length": 22.0,
                "occupancy": 0.75,
                "vehicle_classes": {"car": 25, "truck": 3}
            }
        ]
    }

def test_congestion_score_calculation():
    lanes = [
        LaneTelemetryInput(lane_id="lane_1", vehicle_count=5, average_speed=45.0, queue_length=2.0, occupancy=0.1),
        LaneTelemetryInput(lane_id="lane_2", vehicle_count=45, average_speed=8.0, queue_length=40.0, occupancy=0.9)
    ]
    score = TelemetryService.calculate_congestion_score(lanes)
    assert 0.0 <= score <= 100.0
    assert score > 30.0  # Confirms congestion is properly weighted

@pytest.mark.asyncio
async def test_telemetry_ingestion_valid(async_client: AsyncClient, valid_telemetry_payload):
    with patch("app.core.redis.redis_manager.set_state", new_callable=AsyncMock) as mock_set, \
         patch("app.core.redis.redis_manager.publish_event", new_callable=AsyncMock) as mock_pub, \
         patch("app.websocket.manager.websocket_manager.broadcast_to_intersection", new_callable=AsyncMock) as mock_ws:
        
        response = await async_client.post("/api/v1/telemetry/ingest", json=valid_telemetry_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["intersection_id"] == "INT-001"
        assert data["processed_lanes"] == 2
        assert "congestion_score" in data
        assert mock_set.called
        assert mock_pub.called
        assert mock_ws.called

@pytest.mark.asyncio
async def test_telemetry_ingestion_invalid_schema(async_client: AsyncClient):
    invalid_payload = {
        "intersection_id": "INT-001",
        # Missing timestamp and invalid occupancy
        "lanes": [
            {
                "lane_id": "north_left",
                "vehicle_count": -5,  # Invalid negative count
                "average_speed": 25.0,
                "queue_length": 5.0,
                "occupancy": 1.5  # Invalid > 1.0
            }
        ]
    }
    response = await async_client.post("/api/v1/telemetry/ingest", json=invalid_payload)
    assert response.status_code == 422