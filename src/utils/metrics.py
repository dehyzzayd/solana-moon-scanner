"""Prometheus metrics for monitoring system performance."""

from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from .config import get_config
from .logger import get_logger


logger = get_logger(__name__)


# Counters
tokens_scanned = Counter(
    "moon_scanner_tokens_scanned_total",
    "Total number of tokens scanned"
)

tokens_alerted = Counter(
    "moon_scanner_tokens_alerted_total",
    "Total number of tokens that triggered alerts",
    ["dex"]
)

alerts_sent = Counter(
    "moon_scanner_alerts_sent_total",
    "Total number of alerts sent",
    ["channel", "status"]
)

rpc_requests = Counter(
    "moon_scanner_rpc_requests_total",
    "Total number of RPC requests",
    ["provider", "method", "status"]
)

validation_checks = Counter(
    "moon_scanner_validation_checks_total",
    "Total number of validation checks performed",
    ["check_type", "result"]
)

errors = Counter(
    "moon_scanner_errors_total",
    "Total number of errors encountered",
    ["error_type", "component"]
)

# Gauges
active_monitors = Gauge(
    "moon_scanner_active_monitors",
    "Number of active DEX monitors"
)

tokens_in_memory = Gauge(
    "moon_scanner_tokens_in_memory",
    "Number of tokens currently being tracked in memory"
)

websocket_connections = Gauge(
    "moon_scanner_websocket_connections",
    "Number of active websocket connections"
)

last_scan_timestamp = Gauge(
    "moon_scanner_last_scan_timestamp",
    "Timestamp of the last successful scan"
)

# Histograms
moon_score_distribution = Histogram(
    "moon_scanner_moon_score_distribution",
    "Distribution of MoonScore values",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

rpc_request_duration = Histogram(
    "moon_scanner_rpc_request_duration_seconds",
    "Duration of RPC requests in seconds",
    ["provider", "method"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

token_processing_duration = Histogram(
    "moon_scanner_token_processing_duration_seconds",
    "Duration of token processing in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

alert_delivery_duration = Histogram(
    "moon_scanner_alert_delivery_duration_seconds",
    "Duration of alert delivery in seconds",
    ["channel"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)


class MetricsServer:
    """Prometheus metrics server manager."""
    
    def __init__(self):
        self.config = get_config()
        self.server_started = False
    
    def start(self) -> None:
        """Start Prometheus metrics server."""
        if not self.config.prometheus_enabled:
            logger.info("Prometheus metrics disabled")
            return
        
        if self.server_started:
            logger.warning("Metrics server already started")
            return
        
        try:
            start_http_server(self.config.prometheus_port)
            self.server_started = True
            logger.info(f"Prometheus metrics server started on port {self.config.prometheus_port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            raise
    
    def is_enabled(self) -> bool:
        """Check if metrics are enabled."""
        return self.config.prometheus_enabled


# Global metrics server instance
_metrics_server: Optional[MetricsServer] = None


def get_metrics_server() -> MetricsServer:
    """Get or create global metrics server instance."""
    global _metrics_server
    if _metrics_server is None:
        _metrics_server = MetricsServer()
    return _metrics_server


def start_metrics_server() -> None:
    """Start the global metrics server."""
    server = get_metrics_server()
    server.start()
