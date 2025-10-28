"""API dependencies."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.database import get_db as get_db_session
from src.services.prediction_logger import PredictionLoggerService
from src.services.evidently_service import EvidentlyMonitoringService
from src.services.alert_service import AlertService


# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async for session in get_db_session():
        yield session


# Service dependencies
def get_prediction_logger() -> PredictionLoggerService:
    """Get prediction logger service."""
    return PredictionLoggerService()


def get_evidently_service() -> EvidentlyMonitoringService:
    """Get Evidently monitoring service."""
    return EvidentlyMonitoringService()


def get_alert_service() -> AlertService:
    """Get alert service."""
    return AlertService()
