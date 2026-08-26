import pytest
from app.optimization.base import IntersectionState, LaneState, SafetyConstraints
from app.optimization.queue_based import QueueBasedOptimizer
from app.optimization.webster import WebsterOptimizer
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

@pytest.fixture
def base_constraints():
    return SafetyConstraints(
        min_green=10,
        max_green=60,
        yellow_time=4,
        all_red_time=2,
        min_cycle=40,
        max_cycle=150
    )

def test_queue_based_safety_constraints(base_constraints):
    optimizer = QueueBasedOptimizer()
    # Heavily imbalanced queue: North-South = 100m, East-West = 0m
    state = IntersectionState(
        intersection_id="INT-001",
        lanes=[
            LaneState(lane_id="north", phase_group="north_south", vehicle_count=50, queue_length=100.0, average_speed=5.0),
            LaneState(lane_id="east", phase_group="east_west", vehicle_count=0, queue_length=0.0, average_speed=40.0)
        ],
        constraints=base_constraints
    )
    result = optimizer.optimize(state)
    
    for p in result.phases:
        assert p.green >= base_constraints.min_green
        assert p.green <= base_constraints.max_green
        assert p.yellow == base_constraints.yellow_time
        assert p.all_red == base_constraints.all_red_time

    assert result.cycle_length >= base_constraints.min_cycle
    assert result.cycle_length <= base_constraints.max_cycle
    assert result.next_phase == "north_south"

def test_webster_optimizer_calculation(base_constraints):
    optimizer = WebsterOptimizer()
    state = IntersectionState(
        intersection_id="INT-001",
        lanes=[
            LaneState(lane_id="north", phase_group="north_south", vehicle_count=15, queue_length=10.0, average_speed=25.0),
            LaneState(lane_id="east", phase_group="east_west", vehicle_count=15, queue_length=10.0, average_speed=25.0)
        ],
        constraints=base_constraints
    )
    result = optimizer.optimize(state)
    
    assert result.algorithm == "webster"
    assert len(result.phases) == 2
    # Balanced flows should produce equal green times
    assert result.phases[0].green == result.phases[1].green
    assert result.cycle_length >= base_constraints.min_cycle

@pytest.mark.asyncio
async def test_signal_optimization_endpoint(async_client: AsyncClient):
    with patch("app.core.redis.redis_manager.set_state", new_callable=AsyncMock), \
         patch("app.core.redis.redis_manager.publish_event", new_callable=AsyncMock):
        
        payload = {
            "algorithm": "queue_based",
            "lanes": [
                {"lane_id": "lane_n", "phase_group": "north_south", "vehicle_count": 20, "queue_length": 35.0, "average_speed": 10.0},
                {"lane_id": "lane_e", "phase_group": "east_west", "vehicle_count": 5, "queue_length": 5.0, "average_speed": 35.0}
            ]
        }
        response = await async_client.post("/api/v1/signals/INT-001/optimize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["intersection_id"] == "INT-001"
        assert data["algorithm"] == "queue_based"
        assert data["next_phase"] == "north_south"
        assert len(data["phases"]) == 2