from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.redis import redis_manager
from app.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "unhealthy"
    redis_status = "unhealthy"
    
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        pass

    try:
        if redis_manager.client:
            await redis_manager.client.ping()
            redis_status = "healthy"
    except Exception:
        pass

    return HealthResponse(
        status="ok" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        database=db_status,
        redis=redis_status
    )