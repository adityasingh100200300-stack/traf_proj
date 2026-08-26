import pytest
from app.optimization.rl_optimizer import RLOptimizer

def test_rl_optimizer_prediction():
    optimizer = RLOptimizer("app/optimization/weights/dqn_single_intersection.zip")
    lane_densities = [0.1, 0.4, 0.8, 0.2, 0.5, 0.9, 0.3, 0.6]
    action = optimizer.optimize_phase(lane_densities=lane_densities, current_phase_idx=0)
    assert isinstance(action, int)
    assert 0 <= action <= 3
