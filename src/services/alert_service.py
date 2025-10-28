"""Alert service for ML monitoring."""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from src.models.database import AlertDB
from src.models.schemas import Alert, DriftMetrics, PerformanceMetrics, DataQualityMetrics
from src.core.config import get_settings
from src.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class AlertService:
    """Service for managing and sending alerts."""

    async def create_alert(
        self,
        db: AsyncSession,
        service_name: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metrics: Dict[str, Any],
    ) -> AlertDB:
        """Create a new alert."""
        try:
            alert = AlertDB(
                service_name=service_name,
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                metrics=metrics,
            )

            db.add(alert)
            await db.commit()
            await db.refresh(alert)

            logger.info(
                "alert_created",
                alert_id=str(alert.id),
                service=service_name,
                type=alert_type,
                severity=severity
            )

            # Send alert notification
            await self._send_alert_notification(alert)

            return alert

        except Exception as e:
            logger.error("error_creating_alert", error=str(e))
            await db.rollback()
            raise

    async def check_drift_alerts(
        self,
        db: AsyncSession,
        service_name: str,
        drift_metrics: DriftMetrics,
    ) -> Optional[AlertDB]:
        """Check drift metrics and create alert if threshold exceeded."""
        if not drift_metrics.drift_detected:
            return None

        if drift_metrics.drift_score < settings.drift_threshold:
            return None

        # Determine severity
        severity = "critical" if drift_metrics.drift_score > 0.5 else "warning"

        # Create alert
        title = f"Data Drift Detected - {service_name.upper()}"
        message = (
            f"Data drift detected in {service_name} service. "
            f"Drift score: {drift_metrics.drift_score:.3f} "
            f"(threshold: {drift_metrics.drift_threshold:.3f})"
        )

        return await self.create_alert(
            db=db,
            service_name=service_name,
            alert_type="drift",
            severity=severity,
            title=title,
            message=message,
            metrics={
                "drift_score": drift_metrics.drift_score,
                "drift_by_feature": drift_metrics.drift_by_feature,
                "threshold": drift_metrics.drift_threshold,
            }
        )

    async def check_performance_alerts(
        self,
        db: AsyncSession,
        service_name: str,
        perf_metrics: PerformanceMetrics,
    ) -> List[AlertDB]:
        """Check performance metrics and create alerts if thresholds exceeded."""
        alerts = []

        # Check latency
        if perf_metrics.p95_latency_ms > settings.latency_threshold_ms:
            severity = "critical" if perf_metrics.p95_latency_ms > settings.latency_threshold_ms * 2 else "warning"

            alert = await self.create_alert(
                db=db,
                service_name=service_name,
                alert_type="performance",
                severity=severity,
                title=f"High Latency - {service_name.upper()}",
                message=(
                    f"P95 latency is {perf_metrics.p95_latency_ms:.0f}ms "
                    f"(threshold: {settings.latency_threshold_ms}ms)"
                ),
                metrics={
                    "p95_latency_ms": perf_metrics.p95_latency_ms,
                    "p99_latency_ms": perf_metrics.p99_latency_ms,
                    "avg_latency_ms": perf_metrics.avg_latency_ms,
                }
            )
            alerts.append(alert)

        # Check error rate
        if perf_metrics.error_rate > settings.error_rate_threshold:
            severity = "critical" if perf_metrics.error_rate > settings.error_rate_threshold * 2 else "warning"

            alert = await self.create_alert(
                db=db,
                service_name=service_name,
                alert_type="error",
                severity=severity,
                title=f"High Error Rate - {service_name.upper()}",
                message=(
                    f"Error rate is {perf_metrics.error_rate:.2%} "
                    f"(threshold: {settings.error_rate_threshold:.2%})"
                ),
                metrics={
                    "error_rate": perf_metrics.error_rate,
                    "error_count": perf_metrics.error_count,
                    "total_requests": perf_metrics.total_requests,
                }
            )
            alerts.append(alert)

        return alerts

    async def check_data_quality_alerts(
        self,
        db: AsyncSession,
        service_name: str,
        quality_metrics: DataQualityMetrics,
    ) -> Optional[AlertDB]:
        """Check data quality metrics and create alert if issues found."""
        if quality_metrics.quality_score >= 0.8:
            return None

        severity = "critical" if quality_metrics.quality_score < 0.6 else "warning"

        issues = []
        if quality_metrics.missing_values_percentage > 10:
            issues.append(f"{quality_metrics.missing_values_percentage:.1f}% missing values")
        if quality_metrics.duplicates_count > 0:
            issues.append(f"{quality_metrics.duplicates_count} duplicates")
        if quality_metrics.out_of_range_count > 0:
            issues.append(f"{quality_metrics.out_of_range_count} out-of-range values")

        message = f"Data quality issues detected: {', '.join(issues)}"

        return await self.create_alert(
            db=db,
            service_name=service_name,
            alert_type="data_quality",
            severity=severity,
            title=f"Data Quality Issues - {service_name.upper()}",
            message=message,
            metrics={
                "quality_score": quality_metrics.quality_score,
                "missing_values_percentage": quality_metrics.missing_values_percentage,
                "duplicates_count": quality_metrics.duplicates_count,
                "out_of_range_count": quality_metrics.out_of_range_count,
            }
        )

    async def get_active_alerts(
        self,
        db: AsyncSession,
        service_name: Optional[str] = None,
    ) -> List[AlertDB]:
        """Get all active (unresolved) alerts."""
        query = select(AlertDB).where(AlertDB.resolved == False)

        if service_name:
            query = query.where(AlertDB.service_name == service_name)

        query = query.order_by(AlertDB.timestamp.desc())

        result = await db.execute(query)
        return result.scalars().all()

    async def acknowledge_alert(
        self,
        db: AsyncSession,
        alert_id: str,
        acknowledged_by: str = "system",
    ) -> Optional[AlertDB]:
        """Acknowledge an alert."""
        try:
            query = update(AlertDB).where(
                AlertDB.id == alert_id
            ).values(
                acknowledged=True,
                acknowledged_at=datetime.utcnow(),
                acknowledged_by=acknowledged_by,
            )

            await db.execute(query)
            await db.commit()

            # Fetch updated alert
            result = await db.execute(
                select(AlertDB).where(AlertDB.id == alert_id)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("error_acknowledging_alert", error=str(e))
            await db.rollback()
            return None

    async def resolve_alert(
        self,
        db: AsyncSession,
        alert_id: str,
        resolved_by: str = "system",
    ) -> Optional[AlertDB]:
        """Resolve an alert."""
        try:
            query = update(AlertDB).where(
                AlertDB.id == alert_id
            ).values(
                resolved=True,
                resolved_at=datetime.utcnow(),
                resolved_by=resolved_by,
            )

            await db.execute(query)
            await db.commit()

            # Fetch updated alert
            result = await db.execute(
                select(AlertDB).where(AlertDB.id == alert_id)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("error_resolving_alert", error=str(e))
            await db.rollback()
            return None

    async def _send_alert_notification(self, alert: AlertDB) -> None:
        """Send alert notification via configured channels."""
        # Send to Slack if enabled
        if settings.slack_enabled and settings.slack_webhook_url:
            await self._send_slack_notification(alert)

        # Add other notification channels here (email, PagerDuty, etc.)

    async def _send_slack_notification(self, alert: AlertDB) -> None:
        """Send alert to Slack."""
        try:
            # Color coding by severity
            color = "#ff0000" if alert.severity == "critical" else "#ffa500"

            payload = {
                "channel": settings.slack_channel,
                "username": "ML Monitoring Bot",
                "icon_emoji": ":rotating_light:",
                "attachments": [{
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Service",
                            "value": alert.service_name,
                            "short": True
                        },
                        {
                            "title": "Severity",
                            "value": alert.severity.upper(),
                            "short": True
                        },
                        {
                            "title": "Alert Type",
                            "value": alert.alert_type,
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": alert.timestamp.isoformat(),
                            "short": True
                        }
                    ],
                    "footer": "ML Monitoring Service",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.slack_webhook_url,
                    json=payload,
                    timeout=5.0
                )

                if response.status_code == 200:
                    logger.info("slack_notification_sent", alert_id=str(alert.id))
                else:
                    logger.warning(
                        "slack_notification_failed",
                        alert_id=str(alert.id),
                        status_code=response.status_code
                    )

        except Exception as e:
            logger.error("error_sending_slack_notification", error=str(e))
