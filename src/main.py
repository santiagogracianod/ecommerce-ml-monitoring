"""Main FastAPI application for ML Monitoring Service."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import get_settings
from src.core.logging_config import setup_logging, get_logger
from src.storage.database import init_db, close_db, get_db
from src.api.routes import predictions, monitoring, alerts, search_health
from src.services.threshold_config_service import get_threshold_config_service
from src.services.search_health_monitor import get_search_health_monitor

from .monitoring.prometheus_middleware import PrometheusMiddleware, metrics_response

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Application lifespan events."""
    # Startup
    logger.info("starting_ml_monitoring_service", version=settings.app_version)
    setup_logging()

    # Initialize database
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise

    # Initialize default threshold configuration
    try:
        async for db in get_db():
            threshold_service = get_threshold_config_service()
            await threshold_service.initialize_default_config(db)
            logger.info("threshold_config_initialized")
            break  # Only need one iteration
    except Exception as e:
        logger.error("threshold_config_initialization_failed", error=str(e))
        # Don't raise - service can still work with settings defaults

    # Start search health monitoring
    try:
        search_monitor = get_search_health_monitor()
        search_monitor.start_monitoring()
        logger.info("search_health_monitoring_started")
    except Exception as e:
        logger.error("search_health_monitoring_start_failed", error=str(e))
        # Don't raise - service can still work without health monitoring

    yield

    # Shutdown
    logger.info("shutting_down_ml_monitoring_service")

    # Stop search health monitoring
    try:
        search_monitor = get_search_health_monitor()
        await search_monitor.stop_monitoring()
        logger.info("search_health_monitoring_stopped")
    except Exception as e:
        logger.error("search_health_monitoring_stop_failed", error=str(e))
    try:
        await close_db()
        logger.info("database_connections_closed")
    except Exception as e:
        logger.error("database_shutdown_failed", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "ML Monitoring Service using Evidently AI for monitoring "
        "machine learning models in production. Tracks data drift, "
        "model performance, and data quality for search and sentiment services."
    ),
    lifespan=lifespan,
    docs_url=f"{settings.api_v1_prefix}/docs",
    redoc_url=f"{settings.api_v1_prefix}/redoc",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics middleware
app.add_middleware(PrometheusMiddleware, service_name="ml-monitoring-service")

# Include routers
app.include_router(predictions.router, prefix=settings.api_v1_prefix)
app.include_router(monitoring.router, prefix=settings.api_v1_prefix)
app.include_router(alerts.router, prefix=settings.api_v1_prefix)
app.include_router(search_health.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.app_env,
        "docs": f"{settings.api_v1_prefix}/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        }
    )


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return metrics_response()


@app.get(f"{settings.api_v1_prefix}/info")
async def service_info():
    """Service information and available endpoints."""
    return {
        "service": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        },
        "monitoring": {
            "search_service": settings.search_service_url,
            "sentiment_service": settings.sentiment_service_url,
        },
        "features": {
            "drift_monitoring": settings.enable_drift_monitoring,
            "performance_monitoring": settings.enable_performance_monitoring,
            "data_quality_monitoring": settings.enable_data_quality_monitoring,
            "prometheus_enabled": settings.prometheus_enabled,
            "slack_alerts": settings.slack_enabled,
        },
        "endpoints": {
            "log_predictions": {
                "search": f"{settings.api_v1_prefix}/predictions/search",
                "sentiment": f"{settings.api_v1_prefix}/predictions/sentiment",
            },
            "monitoring": {
                "generate_report": f"{settings.api_v1_prefix}/monitoring/reports/generate",
                "list_reports": f"{settings.api_v1_prefix}/monitoring/reports",
                "update_reference": f"{settings.api_v1_prefix}/monitoring/reference-data/update",
            },
            "alerts": {
                "list": f"{settings.api_v1_prefix}/alerts",
                "acknowledge": f"{settings.api_v1_prefix}/alerts/{{alert_id}}/acknowledge",
                "resolve": f"{settings.api_v1_prefix}/alerts/{{alert_id}}/resolve",
            },
        },
        "documentation": {
            "swagger_ui": f"{settings.api_v1_prefix}/docs",
            "redoc": f"{settings.api_v1_prefix}/redoc",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
