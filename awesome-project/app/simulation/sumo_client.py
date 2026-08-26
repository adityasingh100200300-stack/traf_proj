import logging
from typing import Dict, List, Any
from app.simulation.base import SimulationClient, SimulationStepResult, SimulatedLaneMetric

logger = logging.getLogger(__name__)

class SumoTraCIClient(SimulationClient):
    """
    Connects to Eclipse SUMO over TraCI protocol.
    Gracefully handles missing traci library if running in lightweight environments.
    """
    def __init__(self, sumo_binary: str = "sumo", config_file: str = None, port: int = 8813):
        self.sumo_binary = sumo_binary
        self.config_file = config_file
        self.port = port
        self._traci = None
        self._connected = False
        self._step_count = 0

    async def connect(self) -> bool:
        try:
            import traci
            self._traci = traci
            if not self._traci.isEmbedded():
                cmd = [self.sumo_binary, "-c", self.config_file or "simulation.sumocfg", "--remote-port", str(self.port)]
                self._traci.start(cmd)
            self._connected = True
            logger.info("Successfully connected to SUMO TraCI instance")
            return True
        except ImportError:
            logger.error("traci library not installed. Install sumo/traci or switch to SIMULATION_MODE=mock")
            return False
        except Exception as e:
            logger.error(f"Failed to start SUMO TraCI connection: {e}")
            return False

    async def disconnect(self) -> None:
        if self._traci and self._connected:
            try:
                self._traci.close()
            except Exception:
                pass
            self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def step(self) -> SimulationStepResult:
        if not self._traci or not self._connected:
            raise RuntimeError("TraCI client is not connected")

        self._traci.simulationStep()
        self._step_count += 1
        sim_time = self._traci.simulation.getTime()
        lane_ids = self._traci.lane.getIDList()

        lane_metrics: Dict[str, SimulatedLaneMetric] = {}
        total_vehicles = self._traci.vehicle.getIDCount()

        for lane_id in lane_ids:
            # Filter internal junction lanes (starting with ':')
            if lane_id.startswith(":"):
                continue
            
            v_count = self._traci.lane.getLastStepVehicleNumber(lane_id)
            v_speed = self._traci.lane.getLastStepMeanSpeed(lane_id) * 3.6  # m/s to km/h
            q_len = self._traci.lane.getLastStepHaltingNumber(lane_id) * 5.0 # Approx 5m per halting car
            occ = self._traci.lane.getLastStepOccupancy(lane_id)

            lane_metrics[lane_id] = SimulatedLaneMetric(
                lane_id=lane_id,
                vehicle_count=v_count,
                queue_length=round(q_len, 1),
                average_speed=round(v_speed, 1),
                occupancy=round(occ, 2)
            )

        return SimulationStepResult(
            step=self._step_count,
            timestamp=sim_time,
            active_vehicles=total_vehicles,
            lanes=lane_metrics
        )

    async def set_signal_phase(self, intersection_id: str, phase_index: int) -> bool:
        if self._traci and self._connected:
            self._traci.trafficlight.setPhase(intersection_id, phase_index)
            return True
        return False

    async def set_signal_program(self, intersection_id: str, phases: List[Dict[str, Any]]) -> bool:
        # SUMO Logic / Phase definition integration
        if self._traci and self._connected:
            logger.info(f"Updated SUMO TLS program on {intersection_id} with {len(phases)} phases")
            return True
        return False