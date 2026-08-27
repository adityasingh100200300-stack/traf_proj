# backend/app/optimization/rl_optimizer.py
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
from stable_baselines3 import DQN
from app.optimization.base import (
    SignalOptimizer,
    IntersectionState,
    OptimizationResult,
    PhaseDuration
)

_MODEL_CACHE: Dict[str, DQN] = {}

class RLOptimizer(SignalOptimizer):
    def __init__(self, model_path: str = "app/optimization/weights/dqn_single_intersection.zip"):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"RL weights not found at {self.model_path}")
        
        path_str = str(self.model_path.resolve())
        if path_str not in _MODEL_CACHE:
            _MODEL_CACHE[path_str] = DQN.load(self.model_path)
        self.model = _MODEL_CACHE[path_str]

    def optimize_phase(self, lane_densities: List[float], current_phase_idx: int = 0) -> int:
        """
        Converts live telemetry queue metrics into the observation vector
        expected by the DQN model, then predicts the optimal action/phase.
        """
        densities = list(lane_densities)
        while len(densities) < 16:
            densities.append(0.0)

        phase_one_hot = [0.0] * 5
        if 0 <= current_phase_idx < 5:
            phase_one_hot[current_phase_idx] = 1.0

        obs = np.array(densities + phase_one_hot, dtype=np.float32)
        action, _ = self.model.predict(obs, deterministic=True)
        return int(action)

    def optimize(self, state: IntersectionState) -> OptimizationResult:
        c = state.constraints
        densities = []
        for lane in state.lanes:
            densities.append(min(lane.queue_length / 50.0, 1.0))

        current_idx = 0
        action = self.optimize_phase(densities, current_phase_idx=current_idx)

        # Map action 0/1 to North-South priority, action 2/3 to East-West priority
        if action in [0, 1]:
            ns_green = max(c.min_green, min(45, c.max_green))
            ew_green = max(c.min_green, min(20, c.max_green))
            next_phase = "north_south"
        else:
            ns_green = max(c.min_green, min(20, c.max_green))
            ew_green = max(c.min_green, min(45, c.max_green))
            next_phase = "east_west"

        phases = [
            PhaseDuration(phase="north_south", green=ns_green, yellow=c.yellow_time, all_red=c.all_red_time),
            PhaseDuration(phase="east_west", green=ew_green, yellow=c.yellow_time, all_red=c.all_red_time)
        ]

        total_cycle = ns_green + ew_green + 2 * (c.yellow_time + c.all_red_time)
        return OptimizationResult(
            intersection_id=state.intersection_id,
            cycle_length=total_cycle,
            phases=phases,
            next_phase=next_phase,
            algorithm="rl_dqn"
        )