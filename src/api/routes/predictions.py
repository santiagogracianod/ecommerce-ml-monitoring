"""API routes for logging predictions."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, get_prediction_logger
from src.services.prediction_logger import PredictionLoggerService
from src.models.schemas import SearchPredictionLog, SentimentPredictionLog
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/search", status_code=status.HTTP_201_CREATED)
async def log_search_prediction(
    prediction: SearchPredictionLog,
    db: AsyncSession = Depends(get_db),
    logger_service: PredictionLoggerService = Depends(get_prediction_logger),
) -> Dict[str, Any]:
    """Log a search/embedding prediction."""
    try:
        db_prediction = await logger_service.log_search_prediction(db, prediction)
        return {
            "status": "success",
            "prediction_id": str(db_prediction.id),
            "message": "Search prediction logged successfully"
        }
    except Exception as e:
        logger.error("failed_to_log_search_prediction", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log prediction: {str(e)}"
        )


@router.post("/sentiment", status_code=status.HTTP_201_CREATED)
async def log_sentiment_prediction(
    prediction: SentimentPredictionLog,
    db: AsyncSession = Depends(get_db),
    logger_service: PredictionLoggerService = Depends(get_prediction_logger),
) -> Dict[str, Any]:
    """Log a sentiment analysis prediction."""
    try:
        db_prediction = await logger_service.log_sentiment_prediction(db, prediction)
        return {
            "status": "success",
            "prediction_id": str(db_prediction.id),
            "message": "Sentiment prediction logged successfully"
        }
    except Exception as e:
        logger.error("failed_to_log_sentiment_prediction", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log prediction: {str(e)}"
        )


@router.get("/search/stats")
async def get_search_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    logger_service: PredictionLoggerService = Depends(get_prediction_logger),
) -> Dict[str, Any]:
    """Get search prediction statistics."""
    try:
        stats = await logger_service.get_search_stats(db, hours=hours)
        return stats
    except Exception as e:
        logger.error("failed_to_get_search_stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/sentiment/stats")
async def get_sentiment_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    logger_service: PredictionLoggerService = Depends(get_prediction_logger),
) -> Dict[str, Any]:
    """Get sentiment prediction statistics."""
    try:
        stats = await logger_service.get_sentiment_stats(db, hours=hours)
        return stats
    except Exception as e:
        logger.error("failed_to_get_sentiment_stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )
