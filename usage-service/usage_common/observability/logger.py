import logging

from opentelemetry.instrumentation.logging import LoggingInstrumentor

LOG_FORMAT = (
    "%(asctime)s %(levelname)s [%(name)s] "
    "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(message)s"
)

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return

    LoggingInstrumentor().instrument(set_logging_format=True, log_level=level)
    logging.basicConfig(level=level, format=LOG_FORMAT)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
