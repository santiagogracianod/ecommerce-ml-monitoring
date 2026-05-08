"""RabbitMQ publisher for ML monitoring alerts."""
import json
from datetime import datetime
from typing import Dict, Any, Optional
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from src.core.config import get_settings
from src.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RabbitMQPublisher:
    """Publisher for sending alerts to RabbitMQ."""

    def __init__(self):
        self.connection = None
        self.channel = None
        self._setup_connection()

    def _setup_connection(self) -> None:
        """Setup connection to RabbitMQ."""
        if not settings.rabbitmq_enabled:
            logger.info("rabbitmq_disabled", message="RabbitMQ is disabled in settings")
            return

        try:
            # Configure credentials
            credentials = pika.PlainCredentials(
                settings.rabbitmq_user,
                settings.rabbitmq_password
            )

            # Configure connection parameters
            parameters = pika.ConnectionParameters(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )

            # Establish connection
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare queue (durable for message persistence)
            self.channel.queue_declare(
                queue=settings.rabbitmq_queue_name,
                durable=True
            )

            logger.info(
                "rabbitmq_connected",
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                queue=settings.rabbitmq_queue_name
            )

        except AMQPConnectionError as e:
            logger.error(
                "rabbitmq_connection_error",
                error=str(e),
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port
            )
            self.connection = None
            self.channel = None
        except Exception as e:
            logger.error("rabbitmq_setup_error", error=str(e))
            self.connection = None
            self.channel = None

    def publish_drift_alert(
        self,
        service_name: str,
        drift_score: float,
        drift_by_feature: Dict[str, float],
        severity: str,
        threshold: float,
        alert_id: Optional[str] = None,
        additional_metrics: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Publish a data drift alert to RabbitMQ.

        Args:
            service_name: Name of the service where drift was detected
            drift_score: Overall drift score
            drift_by_feature: Drift scores per feature
            severity: Alert severity (warning, critical)
            threshold: Drift threshold that was exceeded
            alert_id: Optional alert ID from database
            additional_metrics: Optional additional metrics to include

        Returns:
            True if published successfully, False otherwise
        """
        message = {
            "event_type": "data_drift_detected",
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "alert_id": alert_id,
            "severity": severity,
            "metrics": {
                "drift_score": drift_score,
                "drift_threshold": threshold,
                "drift_by_feature": drift_by_feature,
            }
        }

        if additional_metrics:
            message["metrics"].update(additional_metrics)

        return self._publish_message(message)

    def publish_performance_alert(
        self,
        service_name: str,
        alert_type: str,
        severity: str,
        metrics: Dict[str, Any],
        alert_id: Optional[str] = None,
    ) -> bool:
        """
        Publish a performance alert to RabbitMQ.

        Args:
            service_name: Name of the service
            alert_type: Type of alert (performance, error)
            severity: Alert severity
            metrics: Performance metrics
            alert_id: Optional alert ID from database

        Returns:
            True if published successfully, False otherwise
        """
        message = {
            "event_type": f"{alert_type}_alert",
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "alert_id": alert_id,
            "severity": severity,
            "metrics": metrics,
        }

        return self._publish_message(message)

    def publish_data_quality_alert(
        self,
        service_name: str,
        severity: str,
        quality_score: float,
        issues: Dict[str, Any],
        alert_id: Optional[str] = None,
    ) -> bool:
        """
        Publish a data quality alert to RabbitMQ.

        Args:
            service_name: Name of the service
            severity: Alert severity
            quality_score: Overall quality score
            issues: Dictionary of quality issues
            alert_id: Optional alert ID from database

        Returns:
            True if published successfully, False otherwise
        """
        message = {
            "event_type": "data_quality_alert",
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "alert_id": alert_id,
            "severity": severity,
            "metrics": {
                "quality_score": quality_score,
                "issues": issues,
            }
        }

        return self._publish_message(message)

    def _publish_message(self, message: Dict[str, Any]) -> bool:
        """
        Publish a message to RabbitMQ.

        Args:
            message: Message dictionary to publish

        Returns:
            True if published successfully, False otherwise
        """
        if not settings.rabbitmq_enabled:
            logger.debug("rabbitmq_disabled", message="RabbitMQ is disabled")
            return False

        if not self.channel or not self.connection or self.connection.is_closed:
            logger.warning("rabbitmq_not_connected", message="Attempting to reconnect")
            self._setup_connection()

        if not self.channel:
            logger.error("rabbitmq_publish_failed", reason="No active channel")
            return False

        try:
            # Convert message to JSON
            message_body = json.dumps(message, default=str)

            # Publish message (delivery_mode=2 makes the message persistent)
            self.channel.basic_publish(
                exchange='',
                routing_key=settings.rabbitmq_queue_name,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json',
                    timestamp=int(datetime.utcnow().timestamp()),
                )
            )

            logger.info(
                "rabbitmq_message_published",
                event_type=message.get("event_type"),
                service_name=message.get("service_name"),
                queue=settings.rabbitmq_queue_name
            )

            return True

        except AMQPChannelError as e:
            logger.error("rabbitmq_channel_error", error=str(e))
            self.channel = None
            return False
        except Exception as e:
            logger.error("rabbitmq_publish_error", error=str(e))
            return False

    def close(self) -> None:
        """Close RabbitMQ connection."""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("rabbitmq_connection_closed")
        except Exception as e:
            logger.error("rabbitmq_close_error", error=str(e))

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Singleton instance
_rabbitmq_publisher: Optional[RabbitMQPublisher] = None


def get_rabbitmq_publisher() -> RabbitMQPublisher:
    """Get singleton RabbitMQ publisher instance."""
    global _rabbitmq_publisher
    if _rabbitmq_publisher is None:
        _rabbitmq_publisher = RabbitMQPublisher()
    return _rabbitmq_publisher
