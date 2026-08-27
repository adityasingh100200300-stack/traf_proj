import os
import sys
import time
import argparse
import datetime
from pathlib import Path
import numpy as np
import httpx

# Automatically locate and configure SUMO_HOME if missing
SUMO_CANDIDATES = [
    os.environ.get("SUMO_HOME"),
    r"C:\Program Files (x86)\Eclipse\Sumo",
    r"C:\Program Files\Eclipse\Sumo",
    r"C:\Eclipse\Sumo"
]

sumo_path = next((p for p in SUMO_CANDIDATES if p and os.path.isdir(p)), None)
if sumo_path:
    os.environ["SUMO_HOME"] = sumo_path
    bin_dir = os.path.join(sumo_path, "bin")
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{bin_dir};{os.environ.get('PATH', '')}"

import traci
from sumolib import checkBinary
from stable_baselines3 import DQN

# 1. Configuration & Paths
MODEL_PATH = Path("app/optimization/weights/dqn_single_intersection.zip")
CONFIG_PATH = Path("app/simulation/networks/single-intersection.sumocfg")
API_URL = "http://127.0.0.1:8000/api/v1/telemetry/ingest"
TLS_ID = "t"

# 8 Inflow lanes defined in single-intersection.net.xml
INFLOW_LANES = [
    "n_t_0", "n_t_1",
    "s_t_0", "s_t_1",
    "e_t_0", "e_t_1",
    "w_t_0", "w_t_1"
]

# Map DQN action (0..3) to SUMO TLS phase indices
ACTION_TO_GREEN_PHASE = {0: 0, 1: 2, 2: 4, 3: 6}
ACTION_TO_YELLOW_PHASE = {0: 1, 1: 3, 2: 5, 3: 7}


class SumoRLRunner:
    def __init__(self, use_gui: bool = True, stream_api: bool = True):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"RL weights not found at: {MODEL_PATH.resolve()}")

        print(f"[*] Loading RL Model from {MODEL_PATH}...")
        self.model = DQN.load(MODEL_PATH)

        binary_name = "sumo-gui" if use_gui else "sumo"
        try:
            self.sumo_binary = checkBinary(binary_name)
        except Exception:
            print(f"[!] '{binary_name}' binary not found, falling back to 'sumo' headless.")
            self.sumo_binary = checkBinary("sumo")

        self.stream_api = stream_api
        self.http_client = httpx.Client(timeout=3.0) if stream_api else None
        
        self.current_action = 0
        self.yellow_timer = 0
        self.pending_action = None

    def start(self):
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"SUMO config file not found at: {CONFIG_PATH.resolve()}")

        sumo_cmd = [
            self.sumo_binary,
            "-c", str(CONFIG_PATH.resolve()),
            "--start",
            "--quit-on-end"
        ]
        traci.start(sumo_cmd)
        print(f"[*] SUMO TraCI connected successfully using: {self.sumo_binary}")
        if self.stream_api:
            print(f"[*] Live telemetry streaming enabled -> {API_URL}")

    def get_observation(self) -> np.ndarray:
        densities = []
        for lane in INFLOW_LANES:
            halting = traci.lane.getLastStepHaltingNumber(lane)
            length = traci.lane.getLength(lane)
            densities.append(min((halting * 7.5) / length, 1.0))

        while len(densities) < 16:
            densities.append(0.0)

        phase_one_hot = [0.0] * 5
        if 0 <= self.current_action < 5:
            phase_one_hot[self.current_action] = 1.0

        return np.array(densities + phase_one_hot, dtype=np.float32)

    def stream_telemetry_to_api(self, sim_step: int = 0):
        if not self.stream_api or not self.http_client:
            return

        lanes_data = []
        for lane in INFLOW_LANES:
            count = traci.lane.getLastStepVehicleNumber(lane)
            speed_kmh = round(max(0.0, traci.lane.getLastStepMeanSpeed(lane) * 3.6), 1)
            queue_m = round(max(0.0, traci.lane.getLastStepHaltingNumber(lane) * 7.5), 1)
            occupancy = round(min(1.0, max(0.0, traci.lane.getLastStepOccupancy(lane))), 2)

            lanes_data.append({
                "lane_id": lane,
                "vehicle_count": count,
                "average_speed": speed_kmh,
                "queue_length": queue_m,
                "occupancy": occupancy,
                "vehicle_classes": {"car": count}
            })

        sim_sec = sim_step
        cur_m, cur_s = divmod(sim_sec, 60)
        sim_ts = f"{cur_m:02d}:{cur_s:02d} / 60:00"

        payload = {
            "intersection_id": "INT-001",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "lanes": lanes_data,
            "frame_number": sim_step,
            "video_time_seconds": float(sim_sec),
            "total_duration_seconds": 3600.0,
            "video_timestamp": sim_ts
        }

        try:
            res = self.http_client.post(API_URL, json=payload)
            return res.json()
        except Exception as e:
            return None

    def step(self, sim_step: int):
        traci.simulationStep()

        # Handle 3-second yellow clearance transition
        if self.yellow_timer > 0:
            self.yellow_timer -= 1
            if self.yellow_timer == 0 and self.pending_action is not None:
                self.current_action = self.pending_action
                green_phase = ACTION_TO_GREEN_PHASE[self.current_action]
                traci.trafficlight.setPhase(TLS_ID, green_phase)
                self.pending_action = None
        else:
            # RL evaluation every 10 simulation seconds
            if sim_step % 10 == 0:
                obs = self.get_observation()
                optimal_action, _ = self.model.predict(obs, deterministic=True)
                optimal_action = int(optimal_action)

                if optimal_action != self.current_action:
                    yellow_phase = ACTION_TO_YELLOW_PHASE[self.current_action]
                    traci.trafficlight.setPhase(TLS_ID, yellow_phase)
                    self.pending_action = optimal_action
                    self.yellow_timer = 3
                else:
                    green_phase = ACTION_TO_GREEN_PHASE[self.current_action]
                    traci.trafficlight.setPhase(TLS_ID, green_phase)

        # Stream telemetry to frontend every simulation step
        api_res = self.stream_telemetry_to_api(sim_step)
        if sim_step % 10 == 0 and api_res:
            c_score = api_res.get("congestion_score", 0.0)
            active_dir = "N-S" if self.current_action in [0, 1] else "E-W"
            print(f"[Sim Step {sim_step:04d}] Phase: {active_dir} (Act {self.current_action}) | Congestion: {c_score:>5.1f}% | Sent to Frontend")

    def close(self):
        try:
            if self.http_client:
                self.http_client.close()
            traci.close()
        except Exception:
            pass
        print("[*] SUMO TraCI session closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SUMO Simulation with DQN RL Agent & Live Dashboard Streaming")
    parser.add_argument("--headless", action="store_true", help="Run without SUMO GUI window")
    parser.add_argument("--steps", type=int, default=3600, help="Number of simulation steps (default 3600)")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between steps in seconds (default 0.05)")
    args = parser.parse_args()

    use_gui = not args.headless
    runner = SumoRLRunner(use_gui=use_gui, stream_api=True)
    try:
        runner.start()
        print(f"[*] Running simulation for {args.steps} steps...")
        for t in range(args.steps):
            runner.step(t)
            time.sleep(args.delay)
        print("\n[*] Simulation completed.")
    except KeyboardInterrupt:
        print("\n[*] Stopping simulation upon user interrupt...")
    except (traci.exceptions.FatalTraCIError, traci.exceptions.TraCIException):
        print("\n[*] SUMO GUI window closed or simulation ended.")
    finally:
        runner.close()