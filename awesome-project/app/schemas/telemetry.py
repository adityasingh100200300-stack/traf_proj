from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional, Dict

class LaneTelemetryInput(BaseModel):
    lane_id: str = Field(..., description="Unique lane identifier, e.g., 'north_left'")
    vehicle_count: int = Field(..., ge=0, description="Detected vehicle count in lane")
    average_speed: float = Field(..., ge=0.0, description="Average speed in km/h")
    queue_length: float = Field(..., ge=0.0, description="Queue length in meters or vehicle units")
    occupancy: float = Field(..., ge=0.0, le=1.0, description="Lane occupancy percentage (0.0 to 1.0)")
    vehicle_classes: Optional[Dict[str, int]] = Field(default=None, description="Class breakdown e.g. {'car': 10, 'bus': 2}")

class TelemetryIngestRequest(BaseModel):
    intersection_id: str = Field(..., min_length=1, description="Unique intersection identifier")
    timestamp: datetime = Field(..., description="ISO 8601 observation timestamp")
    lanes: List[LaneTelemetryInput] = Field(..., min_length=1, description="List of lane telemetry metrics")
    frame_number: Optional[int] = Field(default=None, ge=0, description="Video frame index")
    video_time_seconds: Optional[float] = Field(default=None, ge=0.0, description="Playback timestamp in seconds")
    total_duration_seconds: Optional[float] = Field(default=None, ge=0.0, description="Total video duration in seconds")
    video_timestamp: Optional[str] = Field(default=None, description="Formatted playback timestamp MM:SS / MM:SS")
    feed_status: Optional[str] = Field(default="ACTIVE", description="Camera feed health: ACTIVE or OFFLINE")
    failsafe_active: Optional[bool] = Field(default=False, description="Whether fallback fixed-time protocol is engaged")
    failsafe_message: Optional[str] = Field(default=None, description="Reason for failsafe protocol engagement")

    model_config = {
        "json_schema_extra": {
            "example": {
                "intersection_id": "INT-001",
                "timestamp": "2026-08-25T12:30:00Z",
                "lanes": [
                    {
                        "lane_id": "north_left",
                        "vehicle_count": 18,
                        "average_speed": 21.4,
                        "queue_length": 12.0,
                        "occupancy": 0.72,
                        "vehicle_classes": {"car": 15, "bus": 3}
                    },
                    {
                        "lane_id": "east_straight",
                        "vehicle_count": 31,
                        "average_speed": 14.8,
                        "queue_length": 24.0,
                        "occupancy": 0.89,
                        "vehicle_classes": {"car": 28, "truck": 3}
                    }
                ]
            }
        }
    }

class TelemetryIngestResponse(BaseModel):
    status: str
    intersection_id: str
    processed_lanes: int
    congestion_score: float
    timestamp: datetime