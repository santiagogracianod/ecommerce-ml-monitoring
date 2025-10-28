"""Application configuration."""
import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = "E-commerce ML Monitoring Service"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8003

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/monitoring.db"

    # Storage Paths
    reference_data_path: str = "./data/reference"
    reports_path: str = "./data/reports"
    logs_path: str = "./data/logs"

    # ML Services URLs
    search_service_url: str = "http://localhost:8000"
    sentiment_service_url: str = "http://localhost:8002"
    comments_service_url: str = "http://localhost:8001"
    products_service_url: str = "http://localhost:8000"

    # Monitoring Configuration
    enable_drift_monitoring: bool = True
    enable_performance_monitoring: bool = True
    enable_data_quality_monitoring: bool = True

    # Report Generation Schedule (cron format)
    drift_report_cron: str = "0 */6 * * *"  # Every 6 hours
    performance_report_cron: str = "0 */1 * * *"  # Every hour

    # Alert Thresholds
    drift_threshold: float = 0.3
    confidence_drop_threshold: float = 0.1
    latency_threshold_ms: int = 2000
    error_rate_threshold: float = 0.05

    # Prometheus
    prometheus_enabled: bool = True
    prometheus_port: int = 9090

    # InfluxDB
    influxdb_enabled: bool = False
    influxdb_url: Optional[str] = None
    influxdb_token: Optional[str] = None
    influxdb_org: Optional[str] = None
    influxdb_bucket: Optional[str] = None

    # S3/MinIO Storage
    s3_enabled: bool = False
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"

    # Slack Alerts
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#ml-alerts"

    # Data Retention
    prediction_log_retention_days: int = 30
    report_retention_days: int = 90

    # Batch Processing
    batch_size: int = 1000
    max_embedding_samples: int = 10000

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "protected_namespaces": ("settings_",)
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
