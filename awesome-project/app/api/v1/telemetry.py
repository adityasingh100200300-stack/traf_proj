from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse
from app.services.telemetry_service import TelemetryService
from app.websocket.manager import websocket_manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/telemetry/ingest",
    response_model=TelemetryIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest vision lane telemetry",
    description="Ingests vehicle counts, speeds, queue lengths, and occupancy metrics per lane."
)
async def ingest_telemetry(
    payload: TelemetryIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    return await TelemetryService.process_telemetry(payload=payload, db=db)

@router.websocket("/ws/traffic-stream/{intersection_id}")
async def traffic_stream(websocket: WebSocket, intersection_id: str):
    """
    Continuous real-time stream of traffic telemetry and congestion for a specific intersection.
    """
    await websocket_manager.connect(websocket, intersection_id)
    try:
        while True:
            # Keeps connection alive and handles incoming client pings
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, intersection_id)
    except Exception as e:
        logger.error(f"WebSocket error on intersection {intersection_id}: {e}")
        websocket_manager.disconnect(websocket, intersection_id)