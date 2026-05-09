"""Service for logging predictions from ML services."""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from src.models.database import SearchPrediction, SentimentPrediction
from src.models.schemas import SearchPredictionLog, SentimentPredictionLog
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class PredictionLoggerService:
    """Service for logging and retrieving prediction data."""

    async def log_search_prediction(
        self,
        db: AsyncSession,
        prediction: SearchPredictionLog
    ) -> SearchPrediction:
        """Log a search/embedding prediction."""
        try:
            # Calculate embedding statistics if embedding is provided
            embedding_stats = {}
            if prediction.embedding:
                embedding_array = np.array(prediction.embedding)
                embedding_stats = {
                    "embedding_norm": float(np.linalg.norm(embedding_array)),
                    "embedding_mean": float(np.mean(embedding_array)),
                    "embedding_std": float(np.std(embedding_array)),
                }

            db_prediction = SearchPrediction(
                id=prediction.id,
                timestamp=prediction.timestamp,
                query=prediction.query,
                query_length=prediction.query_length,
                embedding_norm=embedding_stats.get("embedding_norm"),
                embedding_mean=embedding_stats.get("embedding_mean"),
                embedding_std=embedding_stats.get("embedding_std"),
                num_results=prediction.num_results,
                top_score=prediction.top_score,
                avg_score=prediction.avg_score,
                category_filter=prediction.category_filter,
                price_min=prediction.price_min,
                price_max=prediction.price_max,
                latency_ms=prediction.latency_ms,
                model_latency_ms=prediction.model_latency_ms,
                error=prediction.error,
            )

            db.add(db_prediction)
            await db.commit()
            await db.refresh(db_prediction)

            logger.info(
                "search_prediction_logged",
                prediction_id=str(prediction.id),
                query_length=prediction.query_length,
                num_results=prediction.num_results,
            )

            return db_prediction

        except Exception as e:
            logger.error("error_logging_search_prediction", error=str(e))
            await db.rollback()
            raise

    async def log_sentiment_prediction(
        self,
        db: AsyncSession,
        prediction: SentimentPredictionLog
    ) -> SentimentPrediction:
        """Log a sentiment analysis prediction."""
        try:
            db_prediction = SentimentPrediction(
                id=prediction.id,
                timestamp=prediction.timestamp,
                text=prediction.text,
                text_length=prediction.text_length,
                language=prediction.language,
                predicted_sentiment=prediction.predicted_sentiment,
                confidence=prediction.confidence,
                primary_score=prediction.primary_score,
                all_scores=prediction.all_scores,
                product_id=prediction.product_id,
                user_id=prediction.user_id,
                rating=prediction.rating,
                latency_ms=prediction.latency_ms,
                error=prediction.error,
            )

            db.add(db_prediction)
            await db.commit()
            await db.refresh(db_prediction)

            logger.info(
                "sentiment_prediction_logged",
                prediction_id=str(prediction.id),
                sentiment=prediction.predicted_sentiment,
                confidence=prediction.confidence,
            )

            return db_prediction

        except Exception as e:
            logger.error("error_logging_sentiment_prediction", error=str(e))
            await db.rollback()
            raise

    async def get_search_predictions(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None,
    ) -> List[SearchPrediction]:
        """Get search predictions within a time window."""
        query = select(SearchPrediction).where(
            and_(
                SearchPrediction.timestamp >= start_time,
                SearchPrediction.timestamp <= end_time,
            )
        ).order_by(SearchPrediction.timestamp.desc())

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_sentiment_predictions(
        self,
        db: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None,
    ) -> List[SentimentPrediction]:
        """Get sentiment predictions within a time window."""
        query = select(SentimentPrediction).where(
            and_(
                SentimentPrediction.timestamp >= start_time,
                SentimentPrediction.timestamp <= end_time,
            )
        ).order_by(SentimentPrediction.timestamp.desc())

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_search_stats(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get search prediction statistics."""
        start_time = datetime.utcnow() - timedelta(hours=hours)

        # Count predictions
        count_query = select(func.count(SearchPrediction.id)).where(
            SearchPrediction.timestamp >= start_time
        )
        total_count = await db.scalar(count_query)

        # Average latency
        avg_latency_query = select(func.avg(SearchPrediction.latency_ms)).where(
            SearchPrediction.timestamp >= start_time
        )
        avg_latency = await db.scalar(avg_latency_query)

        # Error count
        error_count_query = select(func.count(SearchPrediction.id)).where(
            and_(
                SearchPrediction.timestamp >= start_time,
                SearchPrediction.error.isnot(None),
            )
        )
        error_count = await db.scalar(error_count_query)

        return {
            "total_predictions": total_count or 0,
            "avg_latency_ms": float(avg_latency) if avg_latency else None,
            "error_count": error_count or 0,
            "error_rate": (error_count / total_count) if total_count else 0,
            "time_window_hours": hours,
        }

    async def get_sentiment_stats(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Get sentiment prediction statistics."""
        start_time = datetime.utcnow() - timedelta(hours=hours)

        # Count predictions
        count_query = select(func.count(SentimentPrediction.id)).where(
            SentimentPrediction.timestamp >= start_time
        )
        total_count = await db.scalar(count_query)

        # Average latency
        avg_latency_query = select(func.avg(SentimentPrediction.latency_ms)).where(
            SentimentPrediction.timestamp >= start_time
        )
        avg_latency = await db.scalar(avg_latency_query)

        # Error count
        error_count_query = select(func.count(SentimentPrediction.id)).where(
            and_(
                SentimentPrediction.timestamp >= start_time,
                SentimentPrediction.error.isnot(None),
            )
        )
        error_count = await db.scalar(error_count_query)

        # Sentiment distribution
        sentiment_dist_query = select(
            SentimentPrediction.predicted_sentiment,
            func.count(SentimentPrediction.id)
        ).where(
            SentimentPrediction.timestamp >= start_time
        ).group_by(SentimentPrediction.predicted_sentiment)

        sentiment_dist = await db.execute(sentiment_dist_query)
        sentiment_counts = {row[0]: row[1] for row in sentiment_dist}

        return {
            "total_predictions": total_count or 0,
            "avg_latency_ms": float(avg_latency) if avg_latency else None,
            "error_count": error_count or 0,
            "error_rate": (error_count / total_count) if total_count else 0,
            "sentiment_distribution": sentiment_counts,
            "time_window_hours": hours,
        }

    async def cleanup_old_predictions(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> Dict[str, int]:
        """Clean up predictions older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Delete old search predictions
        search_delete_query = SearchPrediction.__table__.delete().where(
            SearchPrediction.timestamp < cutoff_date
        )
        search_result = await db.execute(search_delete_query)

        # Delete old sentiment predictions
        sentiment_delete_query = SentimentPrediction.__table__.delete().where(
            SentimentPrediction.timestamp < cutoff_date
        )
        sentiment_result = await db.execute(sentiment_delete_query)

        await db.commit()

        deleted_counts = {
            "search_predictions_deleted": search_result.rowcount,
            "sentiment_predictions_deleted": sentiment_result.rowcount,
        }

        logger.info(
            "old_predictions_cleaned_up",
            days=days,
            **deleted_counts
        )

        return deleted_counts
