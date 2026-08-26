import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.simulation.mock_client import MockSimulationClient
from app.simulation.controller import SimulationController

@pytest.mark.asyncio
async def test_mock_simulation_client():
    client = MockSimulationClient()
    assert await client.is_connected() is False
    
    assert await client.connect() is True
    assert await client.is_connected() is True

    result = await client.step()
    assert result.step == 1
    assert result.active_vehicles >= 0
    assert len(result.lanes) == 4
    assert "north_straight" in result.lanes

    await client.disconnect()
    assert await client.is_connected() is False

@pytest.mark.asyncio
async def test_simulation_step_endpoint(async_client: AsyncClient):
    with patch("app.core.redis.redis_manager.set_state", new_callable=AsyncMock), \
         patch("app.core.redis.redis_manager.publish_event", new_callable=AsyncMock):
        
        response = await async_client.post("/api/v1/simulation/step?intersection_id=INT-001")
        assert response.status_code == 200
        data = response.json()
        assert data["step"] >= 1
        assert "applied_cycle" in data
        assert "next_phase" in data
        assert "lanes" in data