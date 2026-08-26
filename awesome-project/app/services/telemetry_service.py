import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse
from app.models.traffic import TrafficTelemetry
from app.core.redis import redis_manager
from app.websocket.manager import websocket_manager

logger = logging.getLogger(__name__)

class TelemetryService:
    # Configurable weights for normalized congestion score (0–100)
    WEIGHT_QUEUE = 0.45
    WEIGHT_OCCUPANCY = 0.35
    WEIGHT_SPEED_REDUCTION = 0.20
    FREE_FLOW_SPEED_KMH = 50.0
    MAX_EXPECTED_QUEUE = 50.0  # units or meters for saturation baseline

    @classmethod
    def calculate_congestion_score(cls, lanes: list) -> float:
        """
        Calculates a deterministic normalized congestion score (0 to 100)
        based on queue density, occupancy, and speed reduction relative to free-flow.
        """
        if not lanes:
            return 0.0

        total_score = 0.0
        for lane in lanes:
            # 1. Queue component (0.0 to 1.0)
            queue_factor = min(lane.queue_length / cls.MAX_EXPECTED_QUEUE, 1.0)
            
            # 2. Occupancy component (0.0 to 1.0)
            occupancy_factor = min(max(lane.occupancy, 0.0), 1.0)
            
            # 3. Speed reduction component (0.0 to 1.0)
            speed_ratio = max(lane.average_speed, 0.0) / cls.FREE_FLOW_SPEED_KMH
            speed_factor = max(1.0 - min(speed_ratio, 1.0), 0.0)

            lane_score = (
                (cls.WEIGHT_QUEUE * queue_factor) +
                (cls.WEIGHT_OCCUPANCY * occupancy_factor) +
                (cls.WEIGHT_SPEED_REDUCTION * speed_factor)
            ) * 100.0

            total_score += lane_score

        avg_congestion = total_score / len(lanes)
        return round(min(max(avg_congestion, 0.0), 100.0), 2)

    @classmethod
    async def process_telemetry(
        cls, 
        payload: TelemetryIngestRequest, 
        db: AsyncSession
    ) -> TelemetryIngestResponse:
        """
        Persists high-frequency lane telemetry to the database,
        computes congestion score, caches latest state to Redis,
        and broadcasts live data over WebSockets.
        """
        # 1. Calculate Congestion Score
        congestion_score = cls.calculate_congestion_score(payload.lanes)

        # 2. Persist to Database (Timescale/Postgres) if available
        try:
            db_records = [
                TrafficTelemetry(
                    timestamp=payload.timestamp,
                    intersection_id=payload.intersection_id,
                    lane_id=lane.lane_id,
                    vehicle_count=lane.vehicle_count,
                    average_speed=lane.average_speed,
                    queue_length=lane.queue_length,
                    occupancy=lane.occupancy
                )
                for lane in payload.lanes
            ]
            db.add_all(db_records)
            await asyncio.wait_for(db.commit(), timeout=0.5)
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.warning(f"Database persistence skipped (DB unavailable or timed out): {e}")
            # Non-blocking for live broadcast in prototype mode

        # 3. Prepare payload dictionary
        traffic_data = {
            lane.lane_id: {
                "vehicles": lane.vehicle_count,
                "speed": lane.average_speed,
                "queue": lane.queue_length,
                "occupancy": lane.occupancy,
                "classes": lane.vehicle_classes or {}
            }
            for lane in payload.lanes
        }

        live_state: Dict[str, Any] = {
            "type": "traffic_update",
            "intersection_id": payload.intersection_id,
            "timestamp": payload.timestamp.isoformat(),
            "congestion_score": congestion_score,
            "traffic": traffic_data
        }

        # 4. Cache latest snapshot in Redis and Publish to channel
        redis_key = f"traffic:{payload.intersection_id}"
        await redis_manager.set_state(redis_key, live_state, expire=3600)
        await redis_manager.publish_event(redis_key, live_state)

        # 5. Broadcast to connected WebSocket clients for this intersection
        await websocket_manager.broadcast_to_intersection(
            intersection_id=payload.intersection_id,
            message=json.dumps(live_state)
        )

        return TelemetryIngestResponse(
            status="success",
            intersection_id=payload.intersection_id,
            processed_lanes=len(payload.lanes),
            congestion_score=congestion_score,
            timestamp=payload.timestamp
        )