import datetime
import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class VisionTelemetryPublisher:
    def __init__(self, api_url: str = "http://127.0.0.1:8000/api/v1/telemetry/ingest"):
        self.api_url = api_url
        self.client = httpx.Client(timeout=3.0)

    def publish_frame_metrics(
        self, 
        intersection_id: str, 
        lanes: List[Dict[str, Any]],
        frame_number: int = None,
        video_time_seconds: float = None,
        total_duration_seconds: float = None,
        video_timestamp: str = None,
        feed_status: str = "ACTIVE",
        failsafe_active: bool = False,
        failsafe_message: str = None
    ) -> bool:
        payload = {
            "intersection_id": intersection_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "lanes": lanes,
            "frame_number": frame_number,
            "video_time_seconds": round(video_time_seconds, 2) if video_time_seconds is not None else None,
            "total_duration_seconds": round(total_duration_seconds, 2) if total_duration_seconds is not None else None,
            "video_timestamp": video_timestamp,
            "feed_status": feed_status,
            "failsafe_active": failsafe_active,
            "failsafe_message": failsafe_message
        }
        try:
            res = self.client.post(self.api_url, json=payload)
            return res.status_code == 200
        except Exception as e:
            logger.debug(f"Failed to post telemetry: {e}")
            return False

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass