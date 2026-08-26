from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class LaneMetricAggregate(BaseModel):
    lane_id: str
    total_vehicles: int
    average_speed: float
    average_queue: float
    peak_queue: float

class AnalyticsHistoryResponse(BaseModel):
    intersection_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_records: int
    average_congestion_score: float
    lane_metrics: List[LaneMetricAggregate]