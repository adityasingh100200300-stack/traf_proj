import datetime
import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class VisionTelemetryPublisher:
    def __init__(self, api_url: str = "http://127.0.0.1:8000/api/v1/telemetry/ingest"):
        self.api_url = api_url

    def publish_frame_metrics(self, intersection_id: str, lanes: List[Dict[str, Any]]) -> bool:
        payload = {
            "intersection_id": intersection_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "lanes": lanes
        }
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.post(self.api_url, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to push telemetry to API: {e}")
            return False