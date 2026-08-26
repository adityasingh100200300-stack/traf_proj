from fastapi import APIRouter
from app.api.v1 import health, telemetry, signals, simulation, emergency

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(telemetry.router, tags=["Telemetry"])
api_router.include_router(signals.router, tags=["Signals"])
api_router.include_router(simulation.router, tags=["Simulation"])
api_router.include_router(emergency.router, tags=["Emergency"])