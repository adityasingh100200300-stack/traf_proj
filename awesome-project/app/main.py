from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis import redis_manager
from app.websocket.manager import websocket_manager
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_manager.connect()
    yield
    # Shutdown
    await redis_manager.disconnect()

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route direct top-level WebSocket requests (used by frontend)
@app.websocket("/ws/traffic-stream/{intersection_id}")
async def root_traffic_stream(websocket: WebSocket, intersection_id: str):
    await websocket_manager.connect(websocket, intersection_id)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, intersection_id)
    except Exception as e:
        logger.error(f"WebSocket error on intersection {intersection_id}: {e}")
        websocket_manager.disconnect(websocket, intersection_id)

app.include_router(api_router, prefix="/api/v1")