"""Service for analyzing drift degradation over time."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import statistics

from src.models.database import MonitoringReportDB
from src.models.schemas import (
    DriftDegradationAnalysis,
    DriftTimePoint,
    FeatureDegradation
)
from src.services.threshold_config_service import get_threshold_config_service
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class DriftAnalysisService:
    """Service for analyzing drift degradation and trends."""

    async def analyze_drift_degradation(
        self,
        db: AsyncSession,
        service_name: str,
        hours: int = 168,  # Default: last 7 days
    ) -> DriftDegradationAnalysis:
        """
        Analyze drift degradation over time.

        Args:
            db: Database session
            service_name: Name of the service to analyze
            hours: Number of hours to analyze (default: 168 = 7 days)

        Returns:
            DriftDegradationAnalysis with comprehensive drift analysis
        """
        # Define time window
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get monitoring reports with drift metrics
        query = select(MonitoringReportDB).where(
            MonitoringReportDB.service_name == service_name,
            MonitoringReportDB.created_at >= start_time,
            MonitoringReportDB.created_at <= end_time,
            MonitoringReportDB.drift_metrics.isnot(None)
        ).order_by(MonitoringReportDB.created_at.asc())

        result = await db.execute(query)
        reports = result.scalars().all()

        if len(reports) < 2:
            # Insufficient data for trend analysis
            return await self._insufficient_data_analysis(
                db, service_name, hours, start_time, end_time
            )

        # Extract drift scores over time
        historical_scores = self._extract_historical_scores(reports)

        # Get current threshold
        threshold_service = get_threshold_config_service()
        threshold_config = await threshold_service.get_thresholds(db, service_name)

        # Calculate trend and degradation rate
        drift_trend, degradation_rate = self._calculate_trend(historical_scores)

        # Analyze feature-level degradation
        features_degradation = self._analyze_feature_degradation(reports)

        # Get top 3 most degraded features
        most_degraded = sorted(
            features_degradation,
            key=lambda f: abs(f.change_from_first),
            reverse=True
        )[:3]
        most_degraded_features = [f.feature_name for f in most_degraded]

        # Current state
        current_score = historical_scores[-1].drift_score
        current_detected = historical_scores[-1].drift_detected

        # Predict threshold breach
        projected_breach, hours_until = self._predict_threshold_breach(
            current_score,
            degradation_rate,
            threshold_config.drift_threshold
        )

        # Determine severity
        severity = self._determine_severity(
            current_score,
            drift_trend,
            degradation_rate,
            threshold_config.drift_threshold
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            current_score,
            drift_trend,
            degradation_rate,
            threshold_config.drift_threshold,
            projected_breach,
            most_degraded_features,
            features_degradation
        )

        logger.info(
            "drift_degradation_analyzed",
            service=service_name,
            reports_analyzed=len(reports),
            drift_trend=drift_trend,
            severity=severity
        )

        return DriftDegradationAnalysis(
            service_name=service_name,
            analysis_period_hours=hours,
            analysis_start=start_time,
            analysis_end=end_time,
            current_drift_score=current_score,
            current_drift_detected=current_detected,
            current_threshold=threshold_config.drift_threshold,
            drift_trend=drift_trend,
            degradation_rate_per_hour=degradation_rate,
            total_reports_analyzed=len(reports),
            historical_scores=historical_scores,
            features_degradation=features_degradation,
            most_degraded_features=most_degraded_features,
            projected_threshold_breach=projected_breach,
            hours_until_breach=hours_until,
            severity=severity,
            recommendations=recommendations
        )

    def _extract_historical_scores(
        self,
        reports: List[MonitoringReportDB]
    ) -> List[DriftTimePoint]:
        """Extract drift scores from reports."""
        scores = []
        for report in reports:
            if report.drift_metrics:
                scores.append(DriftTimePoint(
                    timestamp=report.created_at,
                    drift_score=report.drift_metrics.get('drift_score', 0.0),
                    drift_detected=report.drift_metrics.get('drift_detected', False)
                ))
        return scores

    def _calculate_trend(
        self,
        historical_scores: List[DriftTimePoint]
    ) -> Tuple[str, float]:
        """
        Calculate drift trend and degradation rate.

        Returns:
            Tuple of (trend, degradation_rate_per_hour)
        """
        if len(historical_scores) < 2:
            return "insufficient_data", 0.0

        scores = [point.drift_score for point in historical_scores]
        timestamps = [point.timestamp for point in historical_scores]

        # Calculate linear regression for trend
        first_score = scores[0]
        last_score = scores[-1]
        score_change = last_score - first_score

        # Calculate time difference in hours
        time_diff = (timestamps[-1] - timestamps[0]).total_seconds() / 3600

        if time_diff == 0:
            return "stable", 0.0

        # Degradation rate per hour
        degradation_rate = score_change / time_diff

        # Determine trend
        # Use threshold to determine if change is significant
        threshold = 0.001  # 0.1% change per hour is considered stable

        if abs(degradation_rate) < threshold:
            trend = "stable"
        elif degradation_rate > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return trend, degradation_rate

    def _analyze_feature_degradation(
        self,
        reports: List[MonitoringReportDB]
    ) -> List[FeatureDegradation]:
        """Analyze degradation for each feature."""
        if len(reports) < 2:
            return []

        # Collect feature drift scores over time
        feature_scores: Dict[str, List[float]] = {}

        for report in reports:
            if report.drift_metrics and 'drift_by_feature' in report.drift_metrics:
                drift_by_feature = report.drift_metrics['drift_by_feature']
                for feature, score in drift_by_feature.items():
                    if feature not in feature_scores:
                        feature_scores[feature] = []
                    feature_scores[feature].append(score)

        # Analyze each feature
        degradations = []
        for feature, scores in feature_scores.items():
            if len(scores) < 2:
                continue

            current_score = scores[-1]
            first_score = scores[0]
            previous_score = scores[-2] if len(scores) > 1 else first_score

            change_from_first = current_score - first_score
            change_from_previous = current_score - previous_score

            # Determine trend
            if abs(change_from_first) < 0.01:
                trend = "stable"
            elif change_from_first > 0:
                trend = "increasing"
            else:
                trend = "decreasing"

            # Determine severity
            abs_change = abs(change_from_first)
            if abs_change < 0.1:
                severity = "low"
            elif abs_change < 0.3:
                severity = "medium"
            else:
                severity = "high"

            degradations.append(FeatureDegradation(
                feature_name=feature,
                current_drift_score=current_score,
                change_from_first=change_from_first,
                change_from_previous=change_from_previous,
                trend=trend,
                severity=severity
            ))

        return degradations

    def _predict_threshold_breach(
        self,
        current_score: float,
        degradation_rate: float,
        threshold: float
    ) -> Tuple[Optional[datetime], Optional[float]]:
        """
        Predict when drift will breach threshold.

        Returns:
            Tuple of (breach_datetime, hours_until_breach)
        """
        if degradation_rate <= 0:
            # Drift is not increasing
            return None, None

        if current_score >= threshold:
            # Already breached
            return datetime.utcnow(), 0.0

        # Calculate hours until breach
        score_gap = threshold - current_score
        hours_until = score_gap / degradation_rate

        # Don't predict too far into the future (max 30 days)
        if hours_until > 720:  # 30 days
            return None, None

        breach_time = datetime.utcnow() + timedelta(hours=hours_until)

        return breach_time, hours_until

    def _determine_severity(
        self,
        current_score: float,
        drift_trend: str,
        degradation_rate: float,
        threshold: float
    ) -> str:
        """Determine overall severity level."""
        # Critical conditions
        if current_score >= threshold:
            return "critical"

        if drift_trend == "increasing" and degradation_rate > 0.01:
            # Increasing at more than 1% per hour
            if current_score > threshold * 0.8:
                return "critical"
            elif current_score > threshold * 0.6:
                return "warning"

        if current_score > threshold * 0.7:
            return "warning"

        return "healthy"

    def _generate_recommendations(
        self,
        current_score: float,
        drift_trend: str,
        degradation_rate: float,
        threshold: float,
        projected_breach: Optional[datetime],
        most_degraded_features: List[str],
        features_degradation: List[FeatureDegradation]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Current state
        if current_score >= threshold:
            recommendations.append(
                f"⚠️ CRITICAL: Drift score ({current_score:.3f}) has exceeded threshold ({threshold:.3f}). "
                "Immediate action required: retrain model or update reference data."
            )
        elif current_score > threshold * 0.8:
            recommendations.append(
                f"⚠️ WARNING: Drift score ({current_score:.3f}) is approaching threshold ({threshold:.3f}). "
                "Consider preparing for model retraining."
            )

        # Trend analysis
        if drift_trend == "increasing":
            if projected_breach and degradation_rate > 0:
                hours = (projected_breach - datetime.utcnow()).total_seconds() / 3600
                if hours < 24:
                    recommendations.append(
                        f"📈 Drift is increasing rapidly at {degradation_rate:.4f}/hour. "
                        f"Expected to breach threshold in ~{hours:.1f} hours. Urgent action needed."
                    )
                else:
                    days = hours / 24
                    recommendations.append(
                        f"📈 Drift is increasing at {degradation_rate:.4f}/hour. "
                        f"Expected to breach threshold in ~{days:.1f} days. Plan model update."
                    )
            else:
                recommendations.append(
                    f"📈 Drift is increasing at {degradation_rate:.4f}/hour. Monitor closely."
                )
        elif drift_trend == "stable":
            recommendations.append(
                "✅ Drift is stable. Model performance is consistent."
            )
        elif drift_trend == "decreasing":
            recommendations.append(
                "📉 Drift is decreasing. Model is adapting well to current data distribution."
            )

        # Feature-specific recommendations
        if most_degraded_features:
            high_severity_features = [
                f for f in features_degradation
                if f.severity == "high" and f.feature_name in most_degraded_features
            ]

            if high_severity_features:
                feature_names = ", ".join([f.feature_name for f in high_severity_features])
                recommendations.append(
                    f"🔍 Features with high degradation: {feature_names}. "
                    "Investigate data collection or preprocessing for these features."
                )

        # General recommendations
        if drift_trend == "increasing" and current_score > threshold * 0.5:
            recommendations.append(
                "💡 Consider: 1) Updating reference dataset, "
                "2) Retraining model with recent data, "
                "3) Adjusting drift threshold if business context has changed."
            )

        if not recommendations:
            recommendations.append(
                "✅ No immediate action required. Continue monitoring."
            )

        return recommendations

    async def _insufficient_data_analysis(
        self,
        db: AsyncSession,
        service_name: str,
        hours: int,
        start_time: datetime,
        end_time: datetime
    ) -> DriftDegradationAnalysis:
        """Return analysis for insufficient data case."""
        threshold_service = get_threshold_config_service()
        threshold_config = await threshold_service.get_thresholds(db, service_name)

        logger.warning(
            "insufficient_drift_data",
            service=service_name,
            hours=hours
        )

        return DriftDegradationAnalysis(
            service_name=service_name,
            analysis_period_hours=hours,
            analysis_start=start_time,
            analysis_end=end_time,
            current_drift_score=0.0,
            current_drift_detected=False,
            current_threshold=threshold_config.drift_threshold,
            drift_trend="insufficient_data",
            degradation_rate_per_hour=0.0,
            total_reports_analyzed=0,
            historical_scores=[],
            features_degradation=[],
            most_degraded_features=[],
            projected_threshold_breach=None,
            hours_until_breach=None,
            severity="healthy",
            recommendations=[
                f"⚠️ Insufficient data for analysis. Found less than 2 reports in the last {hours} hours.",
                "Generate monitoring reports to enable drift analysis.",
                f"Recommendation: Run 'POST /monitoring/reports/generate' for {service_name} service."
            ]
        )


# Singleton instance
_drift_analysis_service: Optional[DriftAnalysisService] = None


def get_drift_analysis_service() -> DriftAnalysisService:
    """Get singleton drift analysis service instance."""
    global _drift_analysis_service
    if _drift_analysis_service is None:
        _drift_analysis_service = DriftAnalysisService()
    return _drift_analysis_service
