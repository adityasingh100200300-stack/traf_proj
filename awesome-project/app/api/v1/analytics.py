from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.schemas.analytics import AnalyticsHistoryResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter()

@router.get(
    "/analytics/history",
    response_model=AnalyticsHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query historical traffic performance",
    description="Fetches aggregated vehicle counts, average speeds, and queue trends over time."
)
async def get_analytics_history(
    intersection_id: str = Query(..., description="Target intersection ID"),
    start_time: Optional[datetime] = Query(None, description="Start ISO timestamp"),
    end_time: Optional[datetime] = Query(None, description="End ISO timestamp"),
    lane_id: Optional[str] = Query(None, description="Filter by specific lane"),
    db: AsyncSession = Depends(get_db)
):
    return await AnalyticsService.get_history(
        intersection_id=intersection_id,
        start_time=start_time,
        end_time=end_time,
        lane_id=lane_id,
        db=db
    )