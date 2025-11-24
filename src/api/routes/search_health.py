"""Search service health monitoring endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.core.logging_config import get_logger
from src.services.search_health_monitor import get_search_health_monitor

logger = get_logger(__name__)
router = APIRouter(prefix="/search-health", tags=["Search Health Monitoring"])


@router.get("/status")
async def get_search_services_status():
    """
    Get current health status of all search services.

    Returns status of semantic-search and traditional-search services,
    including health status, failure counts, and last check times.
    """
    try:
        monitor = get_search_health_monitor()
        status = monitor.get_status()

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "data": status
            }
        )

    except Exception as e:
        logger.error("get_search_services_status_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get search services status: {str(e)}"
        )


@router.post("/start-monitoring")
async def start_monitoring():
    """
    Start the background health monitoring for search services.

    This will begin periodic health checks of semantic-search and
    traditional-search services, automatically triggering failover
    alerts when a service becomes unhealthy.
    """
    try:
        monitor = get_search_health_monitor()
        monitor.start_monitoring()

        from src.core.config import get_settings
        settings = get_settings()

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Search health monitoring started",
                "monitoring_config": {
                    "check_interval_seconds": settings.health_check_interval,
                    "max_failures_threshold": settings.health_check_max_failures,
                    "monitored_services": list(monitor.services.keys())
                }
            }
        )

    except Exception as e:
        logger.error("start_monitoring_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start monitoring: {str(e)}"
        )


@router.post("/stop-monitoring")
async def stop_monitoring():
    """
    Stop the background health monitoring for search services.

    This will stop the periodic health checks.
    """
    try:
        monitor = get_search_health_monitor()
        await monitor.stop_monitoring()

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Search health monitoring stopped"
            }
        )

    except Exception as e:
        logger.error("stop_monitoring_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop monitoring: {str(e)}"
        )


@router.post("/trigger-check")
async def trigger_manual_check():
    """
    Manually trigger a health check of all search services.

    This performs an immediate health check without waiting for
    the next scheduled check.
    """
    try:
        monitor = get_search_health_monitor()

        results = {}
        for service_name, service in monitor.services.items():
            is_healthy = await monitor.check_service_health(service)
            results[service_name] = {
                "is_healthy": is_healthy,
                "url": service.url,
                "consecutive_failures": service.consecutive_failures,
                "last_error": service.last_error,
            }

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Manual health check completed",
                "results": results
            }
        )

    except Exception as e:
        logger.error("trigger_manual_check_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger manual check: {str(e)}"
        )
