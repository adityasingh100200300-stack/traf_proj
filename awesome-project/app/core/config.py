from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "ITMS Backend"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/traffic_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    DEBUG: bool = False
    
    # Simulation Settings
    SIMULATION_MODE: str = "mock"  # "mock" or "traci"
    SUMO_BINARY: str = "sumo"      # "sumo" or "sumo-gui"
    SUMO_CONFIG: Optional[str] = None
    SUMO_PORT: int = 8813

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()