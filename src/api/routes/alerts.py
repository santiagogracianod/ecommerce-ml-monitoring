"""API routes for alerts management."""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, get_alert_service
from src.services.alert_service import AlertService
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    service_name: str = None,
    resolved: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    alert_service: AlertService = Depends(get_alert_service),
) -> Dict[str, Any]:
    """List alerts."""
    try:
        # Get active alerts
        alerts = await alert_service.get_active_alerts(db, service_name)

        # Filter by resolved status if needed
        if not resolved:
            alerts = [a for a in alerts if not a.resolved]

        # Limit results
        alerts = alerts[:limit]

        return {
            "total": len(alerts),
            "alerts": [
                {
                    "id": str(alert.id),
                    "service_name": alert.service_name,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "acknowledged": alert.acknowledged,
                    "resolved": alert.resolved,
                    "metrics": alert.metrics,
                }
                for alert in alerts
            ]
        }

    except Exception as e:
        logger.error("failed_to_list_alerts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alerts: {str(e)}"
        )


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = "user",
    db: AsyncSession = Depends(get_db),
    alert_service: AlertService = Depends(get_alert_service),
) -> Dict[str, Any]:
    """Acknowledge an alert."""
    try:
        alert = await alert_service.acknowledge_alert(db, alert_id, acknowledged_by)

        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        return {
            "status": "success",
            "alert_id": str(alert.id),
            "acknowledged": alert.acknowledged,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "acknowledged_by": alert.acknowledged_by,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_acknowledge_alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert: {str(e)}"
        )


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolved_by: str = "user",
    db: AsyncSession = Depends(get_db),
    alert_service: AlertService = Depends(get_alert_service),
) -> Dict[str, Any]:
    """Resolve an alert."""
    try:
        alert = await alert_service.resolve_alert(db, alert_id, resolved_by)

        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        return {
            "status": "success",
            "alert_id": str(alert.id),
            "resolved": alert.resolved,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "resolved_by": alert.resolved_by,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_resolve_alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert: {str(e)}"
        )


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific alert."""
    try:
        from sqlalchemy import select
        from src.models.database import AlertDB

        query = select(AlertDB).where(AlertDB.id == alert_id)
        result = await db.execute(query)
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        return {
            "id": str(alert.id),
            "service_name": alert.service_name,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "acknowledged": alert.acknowledged,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "acknowledged_by": alert.acknowledged_by,
            "resolved": alert.resolved,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "resolved_by": alert.resolved_by,
            "metrics": alert.metrics,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_get_alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert: {str(e)}"
        )
