"""Search services health monitoring."""
import asyncio
from datetime import datetime
from typing import Dict, Optional
import httpx

from src.core.config import get_settings
from src.core.logging_config import get_logger
from src.services.rabbitmq_publisher import get_rabbitmq_publisher

settings = get_settings()
logger = get_logger(__name__)


class SearchServiceStatus:
    """Track health status of a search service."""

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.is_healthy = True
        self.consecutive_failures = 0
        self.last_check_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.last_failure_time: Optional[datetime] = None
        self.last_error: Optional[str] = None


class SearchHealthMonitor:
    """Monitor health of search services and trigger failover on failures."""

    def __init__(self):
        self.services: Dict[str, SearchServiceStatus] = {
            settings.semantic_search_name: SearchServiceStatus(
                settings.semantic_search_name,
                settings.semantic_search_url
            ),
            settings.traditional_search_name: SearchServiceStatus(
                settings.traditional_search_name,
                settings.traditional_search_url
            ),
        }
        self.monitoring_task: Optional[asyncio.Task] = None
        self.rabbitmq_publisher = get_rabbitmq_publisher()
        self._stop_monitoring = False

    async def check_service_health(self, service: SearchServiceStatus) -> bool:
        """
        Check if a service is healthy by calling its health endpoint.

        Args:
            service: Service status object to check

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=settings.health_check_timeout) as client:
                response = await client.get(f"{service.url}/api/v1/health")

                service.last_check_time = datetime.utcnow()

                if response.status_code == 200:
                    data = response.json()
                    # Check if the response indicates the service is healthy
                    is_healthy = data.get("status") in ["ok", "healthy", "up"]

                    if is_healthy:
                        service.last_success_time = datetime.utcnow()
                        service.consecutive_failures = 0
                        service.last_error = None

                        # If service was down and is now up, log recovery
                        if not service.is_healthy:
                            logger.info(
                                "search_service_recovered",
                                service=service.name,
                                url=service.url
                            )

                        service.is_healthy = True
                        return True

                return False

        except httpx.TimeoutException:
            service.last_error = "Health check timeout"
            logger.warning(
                "search_service_timeout",
                service=service.name,
                url=service.url,
                timeout=settings.health_check_timeout
            )
            return False

        except httpx.ConnectError:
            service.last_error = "Connection refused"
            logger.warning(
                "search_service_connection_error",
                service=service.name,
                url=service.url
            )
            return False

        except Exception as e:
            service.last_error = str(e)
            logger.error(
                "search_service_health_check_error",
                service=service.name,
                url=service.url,
                error=str(e)
            )
            return False

    async def handle_service_failure(self, failed_service: SearchServiceStatus):
        """
        Handle service failure by notifying API Gateway to switch to backup.

        Args:
            failed_service: The service that has failed
        """
        # Get the backup service
        backup_service = None
        for name, service in self.services.items():
            if name != failed_service.name and service.is_healthy:
                backup_service = service
                break

        if not backup_service:
            logger.critical(
                "no_healthy_search_service",
                failed_service=failed_service.name,
                message="No healthy backup service available!"
            )
            # Send critical alert even without backup
            self._send_failover_alert(
                failed_service=failed_service,
                backup_service=None,
                severity="critical"
            )
            return

        # Log the failover decision
        logger.warning(
            "search_service_failover_triggered",
            failed_service=failed_service.name,
            backup_service=backup_service.name,
            consecutive_failures=failed_service.consecutive_failures,
            last_error=failed_service.last_error
        )

        # Send failover alert to RabbitMQ
        self._send_failover_alert(
            failed_service=failed_service,
            backup_service=backup_service,
            severity="high"
        )

    def _send_failover_alert(
        self,
        failed_service: SearchServiceStatus,
        backup_service: Optional[SearchServiceStatus],
        severity: str
    ):
        """
        Send failover alert to RabbitMQ for API Gateway to process.

        Args:
            failed_service: Service that failed
            backup_service: Service to failover to (None if no backup available)
            severity: Alert severity level
        """
        message = {
            "event_type": "search_service_failover",
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "failed_service": {
                "name": failed_service.name,
                "url": failed_service.url,
                "consecutive_failures": failed_service.consecutive_failures,
                "last_error": failed_service.last_error,
                "last_failure_time": failed_service.last_failure_time.isoformat() if failed_service.last_failure_time else None,
            },
            "backup_service": {
                "name": backup_service.name,
                "url": backup_service.url,
                "is_healthy": backup_service.is_healthy,
            } if backup_service else None,
            "action_required": "switch_to_backup" if backup_service else "all_services_down",
        }

        # Use the existing performance alert method
        success = self.rabbitmq_publisher.publish_performance_alert(
            service_name="search-health-monitor",
            alert_type="search_service_failover",
            severity=severity,
            metrics={
                "failed_service": message["failed_service"],
                "backup_service": message["backup_service"],
                "action_required": message["action_required"],
            }
        )

        if success:
            logger.info(
                "failover_alert_sent",
                failed_service=failed_service.name,
                backup_service=backup_service.name if backup_service else None
            )
        else:
            logger.error(
                "failover_alert_failed",
                failed_service=failed_service.name,
                backup_service=backup_service.name if backup_service else None
            )

    async def monitor_loop(self):
        """Main monitoring loop that checks services periodically."""
        logger.info(
            "search_health_monitoring_started",
            interval=settings.health_check_interval,
            max_failures=settings.health_check_max_failures,
            services=list(self.services.keys())
        )

        while not self._stop_monitoring:
            try:
                # Check all services
                for service_name, service in self.services.items():
                    is_healthy = await self.check_service_health(service)

                    if not is_healthy:
                        service.consecutive_failures += 1
                        service.last_failure_time = datetime.utcnow()

                        logger.warning(
                            "search_service_health_check_failed",
                            service=service_name,
                            consecutive_failures=service.consecutive_failures,
                            max_failures=settings.health_check_max_failures,
                            last_error=service.last_error
                        )

                        # Trigger failover if max failures reached
                        if service.consecutive_failures >= settings.health_check_max_failures:
                            if service.is_healthy:  # Only trigger once when transitioning to unhealthy
                                service.is_healthy = False
                                await self.handle_service_failure(service)

                # Wait for next check interval
                await asyncio.sleep(settings.health_check_interval)

            except asyncio.CancelledError:
                logger.info("search_health_monitoring_cancelled")
                break
            except Exception as e:
                logger.error(
                    "search_health_monitoring_error",
                    error=str(e)
                )
                await asyncio.sleep(settings.health_check_interval)

    def start_monitoring(self):
        """Start the background monitoring task."""
        if self.monitoring_task is None or self.monitoring_task.done():
            self._stop_monitoring = False
            self.monitoring_task = asyncio.create_task(self.monitor_loop())
            logger.info("search_health_monitoring_task_started")
        else:
            logger.warning("search_health_monitoring_already_running")

    async def stop_monitoring(self):
        """Stop the background monitoring task."""
        self._stop_monitoring = True
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("search_health_monitoring_task_stopped")

    def get_status(self) -> Dict:
        """
        Get current status of all monitored services.

        Returns:
            Dictionary with status of all services
        """
        return {
            "monitoring_active": self.monitoring_task is not None and not self.monitoring_task.done(),
            "check_interval": settings.health_check_interval,
            "max_failures_threshold": settings.health_check_max_failures,
            "services": {
                name: {
                    "name": service.name,
                    "url": service.url,
                    "is_healthy": service.is_healthy,
                    "consecutive_failures": service.consecutive_failures,
                    "last_check_time": service.last_check_time.isoformat() if service.last_check_time else None,
                    "last_success_time": service.last_success_time.isoformat() if service.last_success_time else None,
                    "last_failure_time": service.last_failure_time.isoformat() if service.last_failure_time else None,
                    "last_error": service.last_error,
                }
                for name, service in self.services.items()
            }
        }


# Singleton instance
_search_health_monitor: Optional[SearchHealthMonitor] = None


def get_search_health_monitor() -> SearchHealthMonitor:
    """Get singleton search health monitor instance."""
    global _search_health_monitor
    if _search_health_monitor is None:
        _search_health_monitor = SearchHealthMonitor()
    return _search_health_monitor
