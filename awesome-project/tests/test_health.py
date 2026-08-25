import pytest

@pytest.mark.asyncio
async def test_health_check(async_client):
    # Tests the routing and schema, though DB/Redis will be unhealthy in a pure unit test run
    # without mocked dependencies or a test database.
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data