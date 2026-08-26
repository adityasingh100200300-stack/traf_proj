# app/simulation/sumo_client.py
import traci
from typing import Dict, Any, List
from app.optimization.rl_optimizer import RLOptimizer

class SumoTraCIClient:
    def __init__(
        self,
        config_path: str = "app/simulation/networks/single-intersection.sumocfg",
        tls_id: str = "t",
        use_gui: bool = False
    ):
        self.config_path = config_path
        self.tls_id = tls_id
        self.sumo_binary = "sumo-gui" if use_gui else "sumo"
        self.inflow_lanes = [
            "n_t_0", "n_t_1",
            "s_t_0", "s_t_1",
            "e_t_0", "e_t_1",
            "w_t_0", "w_t_1"
        ]
        # Maps DQN action index (0..3) to SUMO Green Phase Indices (0, 2, 4, 6)
        self.action_to_phase_index = {
            0: 0,  # North-South Through/Right
            1: 2,  # North-South Left Turn
            2: 4,  # East-West Through/Right
            3: 6   # East-West Left Turn
        }
        self.rl_optimizer = RLOptimizer()

    def start(self):
        sumo_cmd = [self.sumo_binary, "-c", self.config_path, "--start", "--quit-on-end"]
        traci.start(sumo_cmd)

    def get_telemetry_state(self) -> Dict[str, Any]:
        """Extracts queue metrics and halting vehicle counts from junction lanes."""
        lane_data = {}
        densities = []

        for lane in self.inflow_lanes:
            halting = traci.lane.getLastStepHaltingNumber(lane)
            vehicles = traci.lane.getLastStepVehicleNumber(lane)
            speed = traci.lane.getLastStepMeanSpeed(lane) * 3.6  # m/s to km/h
            length = traci.lane.getLength(lane)
            occupancy = min(halting * 7.5 / length, 1.0)

            lane_data[lane] = {
                "vehicles": vehicles,
                "queue_length": float(halting * 7.5),
                "speed": float(speed),
                "occupancy": round(occupancy, 2)
            }
            densities.append(occupancy)

        return {"lane_data": lane_data, "densities": densities}

    def step(self, current_sim_step: int):
        """Advances simulation and evaluates RL phase control every 10 seconds."""
        traci.simulationStep()

        if current_sim_step % 10 == 0:
            state = self.get_telemetry_state()
            current_phase = traci.trafficlight.getPhase(self.tls_id)
            
            # Predict optimal phase using trained DQN model
            optimal_action = self.rl_optimizer.optimize_phase(
                lane_densities=state["densities"],
                current_phase_idx=current_phase // 2
            )
            
            target_phase = self.action_to_phase_index.get(optimal_action, 0)
            if target_phase != current_phase:
                # Transition through yellow before switching if needed
                traci.trafficlight.setPhase(self.tls_id, target_phase)

    def close(self):
        traci.close()