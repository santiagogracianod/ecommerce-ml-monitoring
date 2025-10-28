"""Evidently AI monitoring service for drift detection and data quality."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import json

import pandas as pd
import numpy as np
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset, RegressionPreset
from evidently.metrics import (
    DatasetDriftMetric,
    DatasetMissingValuesMetric,
    ColumnDriftMetric,
    ColumnSummaryMetric,
)
from evidently.test_suite import TestSuite
from evidently.tests import (
    TestNumberOfColumnsWithMissingValues,
    TestNumberOfRowsWithMissingValues,
    TestShareOfOutRangeValues,
)

from sqlalchemy.ext.asyncio import AsyncSession
from src.models.database import SearchPrediction, SentimentPrediction, ReferenceDataDB
from src.models.schemas import DriftMetrics, DataQualityMetrics, PerformanceMetrics
from src.core.config import get_settings
from src.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class EvidentlyMonitoringService:
    """Service for ML monitoring using Evidently AI."""

    def __init__(self):
        self.reference_path = Path(settings.reference_data_path)
        self.reports_path = Path(settings.reports_path)

        # Create directories if they don't exist
        self.reference_path.mkdir(parents=True, exist_ok=True)
        self.reports_path.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # SEARCH SERVICE MONITORING
    # ========================================================================

    async def monitor_search_service(
        self,
        db: AsyncSession,
        current_predictions: List[SearchPrediction],
        reference_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[DriftMetrics, DataQualityMetrics, PerformanceMetrics, str]:
        """
        Monitor search service for drift and data quality.
        Returns: (drift_metrics, quality_metrics, performance_metrics, report_path)
        """
        # Convert predictions to DataFrame
        current_df = self._search_predictions_to_df(current_predictions)

        # Load or create reference data
        if reference_df is None:
            reference_df = await self._load_reference_data(db, "search")
            if reference_df is None:
                logger.warning("No reference data found for search service")
                # Use current data as reference for first run
                reference_df = current_df.head(len(current_df) // 2)
                current_df = current_df.tail(len(current_df) // 2)

        # Define column mapping
        column_mapping = ColumnMapping(
            numerical_features=['query_length', 'num_results', 'top_score',
                              'avg_score', 'latency_ms', 'embedding_norm'],
            categorical_features=['category_filter'],
            target=None,
        )

        # Generate drift report
        drift_metrics = self._detect_drift(reference_df, current_df, column_mapping)

        # Generate data quality report
        quality_metrics = self._assess_data_quality(current_df)

        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(current_df)

        # Generate and save HTML report
        report_path = await self._generate_html_report(
            reference_df, current_df, column_mapping, "search"
        )

        return drift_metrics, quality_metrics, performance_metrics, report_path

    def _search_predictions_to_df(self, predictions: List[SearchPrediction]) -> pd.DataFrame:
        """Convert search predictions to DataFrame."""
        data = []
        for pred in predictions:
            data.append({
                'timestamp': pred.timestamp,
                'query_length': pred.query_length,
                'embedding_norm': pred.embedding_norm,
                'embedding_mean': pred.embedding_mean,
                'embedding_std': pred.embedding_std,
                'num_results': pred.num_results,
                'top_score': pred.top_score or 0.0,
                'avg_score': pred.avg_score or 0.0,
                'category_filter': pred.category_filter or 'none',
                'latency_ms': pred.latency_ms,
                'model_latency_ms': pred.model_latency_ms or 0.0,
                'has_error': 1 if pred.error else 0,
            })
        return pd.DataFrame(data)

    # ========================================================================
    # SENTIMENT SERVICE MONITORING
    # ========================================================================

    async def monitor_sentiment_service(
        self,
        db: AsyncSession,
        current_predictions: List[SentimentPrediction],
        reference_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[DriftMetrics, DataQualityMetrics, PerformanceMetrics, str]:
        """
        Monitor sentiment service for drift and data quality.
        Returns: (drift_metrics, quality_metrics, performance_metrics, report_path)
        """
        # Convert predictions to DataFrame
        current_df = self._sentiment_predictions_to_df(current_predictions)

        # Load or create reference data
        if reference_df is None:
            reference_df = await self._load_reference_data(db, "sentiment")
            if reference_df is None:
                logger.warning("No reference data found for sentiment service")
                # Use current data as reference for first run
                reference_df = current_df.head(len(current_df) // 2)
                current_df = current_df.tail(len(current_df) // 2)

        # Define column mapping
        column_mapping = ColumnMapping(
            numerical_features=['text_length', 'primary_score', 'latency_ms',
                              'positive_score', 'negative_score', 'neutral_score'],
            categorical_features=['predicted_sentiment', 'confidence', 'language'],
            target='predicted_sentiment',
        )

        # Generate drift report
        drift_metrics = self._detect_drift(reference_df, current_df, column_mapping)

        # Generate data quality report
        quality_metrics = self._assess_data_quality(current_df)

        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(current_df)

        # Generate and save HTML report
        report_path = await self._generate_html_report(
            reference_df, current_df, column_mapping, "sentiment"
        )

        return drift_metrics, quality_metrics, performance_metrics, report_path

    def _sentiment_predictions_to_df(self, predictions: List[SentimentPrediction]) -> pd.DataFrame:
        """Convert sentiment predictions to DataFrame."""
        data = []
        for pred in predictions:
            all_scores = pred.all_scores if isinstance(pred.all_scores, dict) else {}
            data.append({
                'timestamp': pred.timestamp,
                'text_length': pred.text_length,
                'language': pred.language or 'unknown',
                'predicted_sentiment': pred.predicted_sentiment,
                'confidence': pred.confidence,
                'primary_score': pred.primary_score,
                'positive_score': all_scores.get('positive', 0.0),
                'negative_score': all_scores.get('negative', 0.0),
                'neutral_score': all_scores.get('neutral', 0.0),
                'latency_ms': pred.latency_ms,
                'has_error': 1 if pred.error else 0,
                'rating': pred.rating or 0,
            })
        return pd.DataFrame(data)

    # ========================================================================
    # CORE MONITORING FUNCTIONS
    # ========================================================================

    def _detect_drift(
        self,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        column_mapping: ColumnMapping,
    ) -> DriftMetrics:
        """Detect data drift using Evidently."""
        try:
            # Create and run drift report
            report = Report(metrics=[
                DatasetDriftMetric(),
            ])

            report.run(
                reference_data=reference_df,
                current_data=current_df,
                column_mapping=column_mapping
            )

            # Extract metrics
            result = report.as_dict()
            dataset_drift = result['metrics'][0]['result']

            drift_detected = dataset_drift.get('dataset_drift', False)
            drift_score = dataset_drift.get('drift_share', 0.0)

            # Get drift by feature
            drift_by_feature = {}
            if 'drift_by_columns' in dataset_drift:
                for col, col_drift in dataset_drift['drift_by_columns'].items():
                    if isinstance(col_drift, dict):
                        drift_by_feature[col] = col_drift.get('drift_score', 0.0)

            return DriftMetrics(
                drift_detected=drift_detected,
                drift_score=drift_score,
                drift_by_feature=drift_by_feature,
                threshold=settings.drift_threshold,
            )

        except Exception as e:
            logger.error("error_detecting_drift", error=str(e))
            return DriftMetrics(
                drift_detected=False,
                drift_score=0.0,
                drift_by_feature={},
                threshold=settings.drift_threshold,
            )

    def _assess_data_quality(self, df: pd.DataFrame) -> DataQualityMetrics:
        """Assess data quality."""
        try:
            total_rows = len(df)
            missing_values = df.isnull().sum().sum()
            missing_percentage = (missing_values / (total_rows * len(df.columns))) * 100

            # Check for duplicates
            duplicates = df.duplicated().sum()

            # Check for out of range values (simplified)
            out_of_range = 0
            if 'latency_ms' in df.columns:
                out_of_range += (df['latency_ms'] < 0).sum()
                out_of_range += (df['latency_ms'] > 60000).sum()  # > 1 minute

            # Calculate quality score (0-1)
            quality_score = 1.0
            quality_score -= min(missing_percentage / 100, 0.3)  # Max 30% penalty
            quality_score -= min(duplicates / total_rows, 0.2)  # Max 20% penalty
            quality_score -= min(out_of_range / total_rows, 0.2)  # Max 20% penalty
            quality_score = max(quality_score, 0.0)

            return DataQualityMetrics(
                missing_values_count=int(missing_values),
                missing_values_percentage=float(missing_percentage),
                duplicates_count=int(duplicates),
                out_of_range_count=int(out_of_range),
                quality_score=float(quality_score),
            )

        except Exception as e:
            logger.error("error_assessing_data_quality", error=str(e))
            return DataQualityMetrics(
                missing_values_count=0,
                missing_values_percentage=0.0,
                duplicates_count=0,
                out_of_range_count=0,
                quality_score=1.0,
            )

    def _calculate_performance_metrics(self, df: pd.DataFrame) -> PerformanceMetrics:
        """Calculate performance metrics from DataFrame."""
        try:
            latencies = df['latency_ms'].values
            total_requests = len(df)
            error_count = df['has_error'].sum() if 'has_error' in df.columns else 0

            return PerformanceMetrics(
                avg_latency_ms=float(np.mean(latencies)),
                p50_latency_ms=float(np.percentile(latencies, 50)),
                p95_latency_ms=float(np.percentile(latencies, 95)),
                p99_latency_ms=float(np.percentile(latencies, 99)),
                max_latency_ms=float(np.max(latencies)),
                total_requests=int(total_requests),
                error_count=int(error_count),
                error_rate=float(error_count / total_requests) if total_requests > 0 else 0.0,
            )

        except Exception as e:
            logger.error("error_calculating_performance_metrics", error=str(e))
            return PerformanceMetrics(
                avg_latency_ms=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                max_latency_ms=0.0,
                total_requests=0,
                error_count=0,
                error_rate=0.0,
            )

    async def _generate_html_report(
        self,
        reference_df: pd.DataFrame,
        current_df: pd.DataFrame,
        column_mapping: ColumnMapping,
        service_name: str,
    ) -> str:
        """Generate and save HTML report using Evidently."""
        try:
            # Create comprehensive report
            report = Report(metrics=[
                DataDriftPreset(),
                DataQualityPreset(),
            ])

            report.run(
                reference_data=reference_df,
                current_data=current_df,
                column_mapping=column_mapping
            )

            # Save HTML report
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            report_filename = f"{service_name}_report_{timestamp}.html"
            report_path = self.reports_path / report_filename

            report.save_html(str(report_path))

            logger.info(
                "html_report_generated",
                service=service_name,
                path=str(report_path)
            )

            return str(report_path)

        except Exception as e:
            logger.error("error_generating_html_report", error=str(e))
            return ""

    # ========================================================================
    # REFERENCE DATA MANAGEMENT
    # ========================================================================

    async def _load_reference_data(
        self,
        db: AsyncSession,
        service_name: str,
    ) -> Optional[pd.DataFrame]:
        """Load reference data for a service."""
        try:
            # Query reference data metadata from DB
            from sqlalchemy import select
            query = select(ReferenceDataDB).where(
                ReferenceDataDB.service_name == service_name,
                ReferenceDataDB.is_active == True
            )
            result = await db.execute(query)
            ref_data = result.scalar_one_or_none()

            if not ref_data:
                return None

            # Load DataFrame from file
            file_path = Path(ref_data.file_path)
            if not file_path.exists():
                logger.warning("reference_data_file_not_found", path=str(file_path))
                return None

            df = pd.read_parquet(file_path)
            logger.info(
                "reference_data_loaded",
                service=service_name,
                num_samples=len(df)
            )
            return df

        except Exception as e:
            logger.error("error_loading_reference_data", error=str(e))
            return None

    async def save_reference_data(
        self,
        db: AsyncSession,
        service_name: str,
        df: pd.DataFrame,
    ) -> bool:
        """Save reference data for a service."""
        try:
            # Save DataFrame to parquet
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{service_name}_reference_{timestamp}.parquet"
            file_path = self.reference_path / filename

            df.to_parquet(file_path, index=False)

            # Calculate statistics
            statistics = {
                'num_samples': len(df),
                'num_features': len(df.columns),
                'columns': list(df.columns),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'numerical_stats': df.describe().to_dict(),
            }

            # Save metadata to database
            from sqlalchemy import update
            # Deactivate old reference data
            update_query = update(ReferenceDataDB).where(
                ReferenceDataDB.service_name == service_name
            ).values(is_active=False)
            await db.execute(update_query)

            # Create new reference data entry
            ref_data = ReferenceDataDB(
                service_name=service_name,
                num_samples=len(df),
                features=list(df.columns),
                statistics=statistics,
                file_path=str(file_path),
                is_active=True,
            )
            db.add(ref_data)
            await db.commit()

            logger.info(
                "reference_data_saved",
                service=service_name,
                num_samples=len(df),
                path=str(file_path)
            )

            return True

        except Exception as e:
            logger.error("error_saving_reference_data", error=str(e))
            await db.rollback()
            return False
