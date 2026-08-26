# backend/app/optimization/rl_optimizer.py
from pathlib import Path
import numpy as np
from stable_baselines3 import DQN
from app.optimization.base import SignalOptimizer

class RLOptimizer(SignalOptimizer):
    def __init__(self, model_path: str = "app/optimization/weights/dqn_single_intersection.zip"):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"RL weights not found at {self.model_path}")
        # Load weights once into memory during startup
        self.model = DQN.load(self.model_path)

    def optimize_phase(self, lane_densities: list[float], current_phase: int) -> int:
        """
        Converts live telemetry queue metrics into the observation vector
        expected by the DQN model, then predicts the optimal action/phase.
        """
        # Shape state vector: [normalized queue densities..., one-hot active phase]
        obs = np.array(lane_densities, dtype=np.float32)
        
        # Fast deterministic inference
        action, _ = self.model.predict(obs, deterministic=True)
        return int(action)