"""
Reusable Prometheus metrics middleware for FastAPI applications.
Drop this file into any FastAPI service to enable metrics collection.
"""

from time import perf_counter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status", "service"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "service"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0),
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect Prometheus metrics from a FastAPI app."""

    def __init__(self, app, service_name: str = "unknown"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = request.url.path
        start = perf_counter()

        response = await call_next(request)

        duration = perf_counter() - start
        REQUEST_COUNT.labels(
            method=method,
            path=path,
            status=response.status_code,
            service=self.service_name,
        ).inc()
        REQUEST_LATENCY.labels(
            method=method,
            path=path,
            service=self.service_name,
        ).observe(duration)

        return response


def metrics_response() -> Response:
    """Generate Prometheus metrics response."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
