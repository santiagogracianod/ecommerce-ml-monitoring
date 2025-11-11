"""API routes for monitoring and reports."""
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.dependencies import (
    get_db,
    get_prediction_logger,
    get_evidently_service,
    get_alert_service
)
from src.services.prediction_logger import PredictionLoggerService
from src.services.evidently_service import EvidentlyMonitoringService
from src.services.alert_service import AlertService
from src.services.drift_analysis_service import get_drift_analysis_service, DriftAnalysisService
from src.services.rabbitmq_publisher import get_rabbitmq_publisher
from src.models.schemas import (
    GenerateReportRequest,
    UpdateReferenceDataRequest,
    MonitoringReport,
    DriftMetrics,
    PerformanceMetrics,
    DataQualityMetrics,
    DriftDegradationAnalysis
)
from src.models.database import MonitoringReportDB
from src.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.post("/reports/generate")
async def generate_report(
    request: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    pred_logger: PredictionLoggerService = Depends(get_prediction_logger),
    evidently_service: EvidentlyMonitoringService = Depends(get_evidently_service),
    alert_service: AlertService = Depends(get_alert_service),
) -> Dict[str, Any]:
    """Generate a monitoring report for a service."""
    try:
        # Calculate time window
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=request.time_window_hours)

        # Get predictions based on service
        if request.service_name == "search":
            predictions = await pred_logger.get_search_predictions(
                db, start_time, end_time
            )

            if len(predictions) < 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient data: only {len(predictions)} predictions found. Need at least 100."
                )

            # Run monitoring
            drift_metrics, quality_metrics, perf_metrics, report_path = \
                await evidently_service.monitor_search_service(db, predictions)

        elif request.service_name == "sentiment":
            predictions = await pred_logger.get_sentiment_predictions(
                db, start_time, end_time
            )

            if len(predictions) < 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient data: only {len(predictions)} predictions found. Need at least 100."
                )

            # Run monitoring
            drift_metrics, quality_metrics, perf_metrics, report_path = \
                await evidently_service.monitor_sentiment_service(db, predictions)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown service: {request.service_name}"
            )

        # Determine overall status
        status_level = "healthy"
        if drift_metrics.drift_detected or perf_metrics.error_rate > 0.05:
            status_level = "warning"
        if drift_metrics.drift_score > 0.5 or perf_metrics.error_rate > 0.1:
            status_level = "critical"

        # Generate recommendations
        recommendations = []
        if drift_metrics.drift_detected:
            recommendations.append(
                f"Data drift detected (score: {drift_metrics.drift_score:.3f}). "
                "Consider updating the reference dataset or retraining the model."
            )
        if perf_metrics.p95_latency_ms > 2000:
            recommendations.append(
                f"High latency detected (P95: {perf_metrics.p95_latency_ms:.0f}ms). "
                "Consider optimizing model inference or scaling infrastructure."
            )
        if quality_metrics.quality_score < 0.8:
            recommendations.append(
                f"Data quality issues detected (score: {quality_metrics.quality_score:.2f}). "
                "Review data validation and preprocessing pipelines."
            )

        # Save report to database
        report = MonitoringReportDB(
            report_type=request.report_type,
            service_name=request.service_name,
            time_window_start=start_time,
            time_window_end=end_time,
            drift_metrics=drift_metrics.dict() if drift_metrics else None,
            performance_metrics=perf_metrics.dict() if perf_metrics else None,
            data_quality_metrics=quality_metrics.dict() if quality_metrics else None,
            report_path=report_path if request.include_html else None,
            status=status_level,
            summary=f"Monitoring report for {request.service_name} service covering {request.time_window_hours} hours",
            recommendations=recommendations,
        )

        db.add(report)
        await db.commit()
        await db.refresh(report)

        # Check for alerts in background
        background_tasks.add_task(
            check_and_create_alerts,
            db,
            request.service_name,
            drift_metrics,
            perf_metrics,
            quality_metrics,
            alert_service
        )

        logger.info(
            "monitoring_report_generated",
            service=request.service_name,
            report_id=str(report.id),
            status=status_level
        )

        return {
            "status": "success",
            "report_id": str(report.id),
            "service_name": request.service_name,
            "time_window_hours": request.time_window_hours,
            "predictions_analyzed": len(predictions),
            "overall_status": status_level,
            "drift_detected": drift_metrics.drift_detected if drift_metrics else False,
            "drift_score": drift_metrics.drift_score if drift_metrics else 0.0,
            "performance": {
                "avg_latency_ms": perf_metrics.avg_latency_ms,
                "p95_latency_ms": perf_metrics.p95_latency_ms,
                "error_rate": perf_metrics.error_rate,
            } if perf_metrics else None,
            "data_quality_score": quality_metrics.quality_score if quality_metrics else 1.0,
            "report_path": report_path if request.include_html else None,
            "recommendations": recommendations,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_generate_report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )


async def check_and_create_alerts(
    db: AsyncSession,
    service_name: str,
    drift_metrics: DriftMetrics,
    perf_metrics: PerformanceMetrics,
    quality_metrics: DataQualityMetrics,
    alert_service: AlertService,
):
    """Background task to check metrics and create alerts."""
    try:
        # Check drift
        if drift_metrics:
            await alert_service.check_drift_alerts(db, service_name, drift_metrics)

        # Check performance
        if perf_metrics:
            await alert_service.check_performance_alerts(db, service_name, perf_metrics)

        # Check data quality
        if quality_metrics:
            await alert_service.check_data_quality_alerts(db, service_name, quality_metrics)

    except Exception as e:
        logger.error("failed_to_check_alerts", error=str(e))


@router.get("/reports")
async def list_reports(
    service_name: str = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List monitoring reports."""
    try:
        query = select(MonitoringReportDB).order_by(
            MonitoringReportDB.created_at.desc()
        )

        if service_name:
            query = query.where(MonitoringReportDB.service_name == service_name)

        query = query.limit(limit)

        result = await db.execute(query)
        reports = result.scalars().all()

        return {
            "total": len(reports),
            "reports": [
                {
                    "id": str(report.id),
                    "service_name": report.service_name,
                    "report_type": report.report_type,
                    "status": report.status,
                    "created_at": report.created_at.isoformat(),
                    "time_window": {
                        "start": report.time_window_start.isoformat(),
                        "end": report.time_window_end.isoformat(),
                    },
                    "summary": report.summary,
                }
                for report in reports
            ]
        }

    except Exception as e:
        logger.error("failed_to_list_reports", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list reports: {str(e)}"
        )


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific monitoring report."""
    try:
        query = select(MonitoringReportDB).where(MonitoringReportDB.id == report_id)
        result = await db.execute(query)
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )

        return {
            "id": str(report.id),
            "service_name": report.service_name,
            "report_type": report.report_type,
            "status": report.status,
            "created_at": report.created_at.isoformat(),
            "time_window": {
                "start": report.time_window_start.isoformat(),
                "end": report.time_window_end.isoformat(),
            },
            "summary": report.summary,
            "drift_metrics": report.drift_metrics,
            "performance_metrics": report.performance_metrics,
            "data_quality_metrics": report.data_quality_metrics,
            "recommendations": report.recommendations,
            "report_path": report.report_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_get_report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get report: {str(e)}"
        )


@router.post("/reference-data/update")
async def update_reference_data(
    request: UpdateReferenceDataRequest,
    db: AsyncSession = Depends(get_db),
    pred_logger: PredictionLoggerService = Depends(get_prediction_logger),
    evidently_service: EvidentlyMonitoringService = Depends(get_evidently_service),
) -> Dict[str, Any]:
    """Update reference dataset for a service."""
    try:
        if not request.use_recent_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only recent data sampling is currently supported"
            )

        # Get recent predictions
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=request.hours_to_sample)

        if request.service_name == "search":
            predictions = await pred_logger.get_search_predictions(
                db, start_time, end_time
            )
            df = evidently_service._search_predictions_to_df(predictions)
        else:
            predictions = await pred_logger.get_sentiment_predictions(
                db, start_time, end_time
            )
            df = evidently_service._sentiment_predictions_to_df(predictions)

        if len(df) < request.min_samples:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient samples: {len(df)} < {request.min_samples}"
            )

        # Save reference data
        success = await evidently_service.save_reference_data(
            db, request.service_name, df
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save reference data"
            )

        logger.info(
            "reference_data_updated",
            service=request.service_name,
            num_samples=len(df)
        )

        return {
            "status": "success",
            "service_name": request.service_name,
            "num_samples": len(df),
            "time_window_hours": request.hours_to_sample,
            "message": "Reference data updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_update_reference_data", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update reference data: {str(e)}"
        )


# ============================================================================
# DRIFT DEGRADATION ANALYSIS
# ============================================================================

@router.get("/drift/analysis", response_model=DriftDegradationAnalysis)
async def analyze_drift_degradation(
    service_name: str,
    hours: int = 168,  # Default: last 7 days
    db: AsyncSession = Depends(get_db),
) -> DriftDegradationAnalysis:
    """
    Analyze drift degradation over time for a service.

    This endpoint provides comprehensive drift analysis including:
    - **Trend analysis**: Is drift increasing, decreasing, or stable?
    - **Degradation rate**: How fast is drift changing (per hour)?
    - **Feature-level analysis**: Which features are drifting most?
    - **Predictions**: When will drift breach the threshold?
    - **Recommendations**: Actionable steps to take

    Args:
        service_name: Name of the service to analyze (search or sentiment)
        hours: Number of hours to analyze (default: 168 = 7 days, max: 720 = 30 days)
        db: Database session

    Returns:
        Comprehensive drift degradation analysis

    Example:
        ```bash
        # Analyze last 7 days
        curl "http://localhost:8003/api/v1/monitoring/drift/analysis?service_name=search"

        # Analyze last 24 hours
        curl "http://localhost:8003/api/v1/monitoring/drift/analysis?service_name=search&hours=24"
        ```

    Response includes:
        - Current drift state and threshold
        - Historical drift scores over time
        - Trend (increasing/decreasing/stable)
        - Degradation rate per hour
        - Feature-level degradation analysis
        - Prediction of when threshold will be breached
        - Severity level and actionable recommendations
    """
    try:
        # Validate service name
        if service_name not in ["search", "sentiment"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid service_name: {service_name}. Must be 'search' or 'sentiment'."
            )

        # Validate hours range
        if hours < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hours must be at least 1"
            )
        if hours > 720:  # 30 days
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hours cannot exceed 720 (30 days)"
            )

        # Get drift analysis service
        drift_service = get_drift_analysis_service()

        # Perform analysis
        analysis = await drift_service.analyze_drift_degradation(
            db=db,
            service_name=service_name,
            hours=hours
        )

        logger.info(
            "drift_analysis_completed",
            service=service_name,
            hours=hours,
            trend=analysis.drift_trend,
            severity=analysis.severity
        )

        # Publish to RabbitMQ if drift exceeds threshold
        if analysis.current_drift_score > analysis.current_threshold:
            try:
                rabbitmq_publisher = get_rabbitmq_publisher()

                # Build feature degradation dict for the message
                drift_by_feature = {}
                for feature_deg in analysis.features_degradation:
                    drift_by_feature[feature_deg.feature_name] = feature_deg.current_drift_score

                # Publish drift degradation alert
                success = rabbitmq_publisher.publish_drift_alert(
                    service_name=service_name,
                    drift_score=analysis.current_drift_score,
                    drift_by_feature=drift_by_feature,
                    severity=analysis.severity,
                    threshold=analysis.current_threshold,
                    additional_metrics={
                        "drift_trend": analysis.drift_trend,
                        "degradation_rate_per_hour": analysis.degradation_rate_per_hour,
                        "hours_until_breach": analysis.hours_until_breach,
                        "projected_threshold_breach": analysis.projected_threshold_breach.isoformat() if analysis.projected_threshold_breach else None,
                        "total_reports_analyzed": analysis.total_reports_analyzed,
                        "most_degraded_features": analysis.most_degraded_features,
                        "analysis_type": "degradation_analysis"
                    }
                )

                if success:
                    logger.info(
                        "drift_analysis_alert_published_to_rabbitmq",
                        service=service_name,
                        drift_score=analysis.current_drift_score,
                        threshold=analysis.current_threshold
                    )
                else:
                    logger.warning(
                        "failed_to_publish_drift_analysis_to_rabbitmq",
                        service=service_name
                    )

            except Exception as e:
                logger.error(
                    "error_publishing_drift_analysis_to_rabbitmq",
                    error=str(e),
                    service=service_name
                )
                # Don't fail the analysis if RabbitMQ publish fails

        return analysis

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_analyze_drift", error=str(e), service=service_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze drift degradation: {str(e)}"
        )
