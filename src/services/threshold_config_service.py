"""Dynamic alert threshold configuration service."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import AlertThresholdConfigDB
from src.models.schemas import AlertThresholdResponse, UpdateAlertThresholdRequest
from src.core.config import get_settings
from src.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class ThresholdConfigService:
    """Service for managing dynamic alert threshold configuration."""

    def __init__(self):
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache for 60 seconds

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid."""
        if self._cache is None or self._cache_timestamp is None:
            return False

        elapsed = datetime.utcnow() - self._cache_timestamp
        return elapsed.total_seconds() < self._cache_ttl_seconds

    async def get_thresholds(
        self,
        db: AsyncSession,
        service_name: Optional[str] = None
    ) -> AlertThresholdResponse:
        """
        Get current alert thresholds.

        Args:
            db: Database session
            service_name: Optional service name to get service-specific overrides

        Returns:
            AlertThresholdResponse with current thresholds
        """
        # Check cache first
        if self._is_cache_valid() and self._cache is not None:
            logger.debug("threshold_config_from_cache")
            config = self._cache
        else:
            # Load from database
            config = await self._load_from_db(db)

            # Update cache
            self._cache = config
            self._cache_timestamp = datetime.utcnow()
            logger.debug("threshold_config_cached")

        # Apply service-specific overrides if requested
        if service_name and config.get("service_overrides"):
            service_override = config["service_overrides"].get(service_name, {})
            if service_override:
                logger.info(
                    "applying_service_override",
                    service_name=service_name,
                    overrides=service_override
                )
                # Merge overrides with defaults
                merged_config = {**config}
                merged_config.update(service_override)
                config = merged_config

        return AlertThresholdResponse(
            drift_threshold=config["drift_threshold"],
            confidence_drop_threshold=config["confidence_drop_threshold"],
            latency_threshold_ms=config["latency_threshold_ms"],
            error_rate_threshold=config["error_rate_threshold"],
            service_overrides=config.get("service_overrides"),
            updated_at=config["updated_at"],
            updated_by=config.get("updated_by")
        )

    async def _load_from_db(self, db: AsyncSession) -> Dict[str, Any]:
        """Load threshold configuration from database."""
        try:
            # Get active configuration
            query = select(AlertThresholdConfigDB).where(
                AlertThresholdConfigDB.is_active == True
            ).order_by(AlertThresholdConfigDB.updated_at.desc())

            result = await db.execute(query)
            config_db = result.scalar_one_or_none()

            if not config_db:
                logger.warning("no_active_threshold_config_found")
                # Return default values from settings
                return {
                    "drift_threshold": settings.drift_threshold,
                    "confidence_drop_threshold": settings.confidence_drop_threshold,
                    "latency_threshold_ms": settings.latency_threshold_ms,
                    "error_rate_threshold": settings.error_rate_threshold,
                    "service_overrides": None,
                    "updated_at": datetime.utcnow(),
                    "updated_by": "system_defaults"
                }

            logger.info(
                "threshold_config_loaded_from_db",
                drift_threshold=config_db.drift_threshold,
                latency_threshold_ms=config_db.latency_threshold_ms
            )

            return {
                "drift_threshold": config_db.drift_threshold,
                "confidence_drop_threshold": config_db.confidence_drop_threshold,
                "latency_threshold_ms": config_db.latency_threshold_ms,
                "error_rate_threshold": config_db.error_rate_threshold,
                "service_overrides": config_db.service_overrides,
                "updated_at": config_db.updated_at,
                "updated_by": config_db.updated_by
            }

        except Exception as e:
            logger.error("error_loading_threshold_config", error=str(e))
            # Return defaults on error
            return {
                "drift_threshold": settings.drift_threshold,
                "confidence_drop_threshold": settings.confidence_drop_threshold,
                "latency_threshold_ms": settings.latency_threshold_ms,
                "error_rate_threshold": settings.error_rate_threshold,
                "service_overrides": None,
                "updated_at": datetime.utcnow(),
                "updated_by": "error_fallback"
            }

    async def update_thresholds(
        self,
        db: AsyncSession,
        request: UpdateAlertThresholdRequest
    ) -> AlertThresholdResponse:
        """
        Update alert thresholds.

        Args:
            db: Database session
            request: Update request with new threshold values

        Returns:
            Updated AlertThresholdResponse
        """
        try:
            # Get current active config
            query = select(AlertThresholdConfigDB).where(
                AlertThresholdConfigDB.is_active == True
            )
            result = await db.execute(query)
            current_config = result.scalar_one_or_none()

            # Prepare new values (only update provided fields)
            new_values = {}
            if request.drift_threshold is not None:
                new_values["drift_threshold"] = request.drift_threshold
            if request.confidence_drop_threshold is not None:
                new_values["confidence_drop_threshold"] = request.confidence_drop_threshold
            if request.latency_threshold_ms is not None:
                new_values["latency_threshold_ms"] = request.latency_threshold_ms
            if request.error_rate_threshold is not None:
                new_values["error_rate_threshold"] = request.error_rate_threshold
            if request.service_overrides is not None:
                new_values["service_overrides"] = request.service_overrides
            if request.description is not None:
                new_values["description"] = request.description

            new_values["updated_by"] = request.updated_by
            new_values["updated_at"] = datetime.utcnow()

            if current_config:
                # Update existing config
                update_query = update(AlertThresholdConfigDB).where(
                    AlertThresholdConfigDB.id == current_config.id
                ).values(**new_values)

                await db.execute(update_query)
                await db.commit()

                logger.info(
                    "threshold_config_updated",
                    updated_by=request.updated_by,
                    changes=new_values
                )
            else:
                # Create new config
                new_config = AlertThresholdConfigDB(
                    drift_threshold=request.drift_threshold or settings.drift_threshold,
                    confidence_drop_threshold=request.confidence_drop_threshold or settings.confidence_drop_threshold,
                    latency_threshold_ms=request.latency_threshold_ms or settings.latency_threshold_ms,
                    error_rate_threshold=request.error_rate_threshold or settings.error_rate_threshold,
                    service_overrides=request.service_overrides,
                    description=request.description,
                    updated_by=request.updated_by,
                    is_active=True
                )
                db.add(new_config)
                await db.commit()

                logger.info(
                    "threshold_config_created",
                    created_by=request.updated_by
                )

            # Invalidate cache to force reload
            self._cache = None
            self._cache_timestamp = None
            logger.info("threshold_cache_invalidated")

            # Return updated config
            return await self.get_thresholds(db)

        except Exception as e:
            logger.error("error_updating_threshold_config", error=str(e))
            await db.rollback()
            raise

    async def initialize_default_config(self, db: AsyncSession) -> None:
        """
        Initialize default threshold configuration if none exists.

        Args:
            db: Database session
        """
        try:
            # Check if config exists
            query = select(AlertThresholdConfigDB).where(
                AlertThresholdConfigDB.is_active == True
            )
            result = await db.execute(query)
            existing_config = result.scalar_one_or_none()

            if existing_config:
                logger.info("threshold_config_already_exists")
                return

            # Create default config from settings
            default_config = AlertThresholdConfigDB(
                drift_threshold=settings.drift_threshold,
                confidence_drop_threshold=settings.confidence_drop_threshold,
                latency_threshold_ms=settings.latency_threshold_ms,
                error_rate_threshold=settings.error_rate_threshold,
                description="Default configuration from settings",
                updated_by="system_init",
                is_active=True
            )

            db.add(default_config)
            await db.commit()

            logger.info(
                "default_threshold_config_initialized",
                drift_threshold=settings.drift_threshold,
                latency_threshold_ms=settings.latency_threshold_ms
            )

        except Exception as e:
            logger.error("error_initializing_threshold_config", error=str(e))
            await db.rollback()

    def invalidate_cache(self) -> None:
        """Manually invalidate the cache."""
        self._cache = None
        self._cache_timestamp = None
        logger.info("threshold_cache_manually_invalidated")


# Singleton instance
_threshold_config_service: Optional[ThresholdConfigService] = None


def get_threshold_config_service() -> ThresholdConfigService:
    """Get singleton threshold config service instance."""
    global _threshold_config_service
    if _threshold_config_service is None:
        _threshold_config_service = ThresholdConfigService()
    return _threshold_config_service
