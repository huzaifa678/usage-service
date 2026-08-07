import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from usage_common.observability.logger import get_logger
from usage_common.observability.metrics import tracer
from usage_common.observability.tracing import setup_observability

logger = get_logger(__name__)


@dataclass
class FilterResult:
    name: str
    processed: int = 0
    metrics: dict = field(default_factory=dict)


class Filter(ABC):
    name: str = "filter"
    span_name: str = "usage.filter"

    @abstractmethod
    def process(self) -> FilterResult: ...

    def run(self) -> FilterResult:
        setup_observability()
        with tracer().start_as_current_span(self.span_name) as span:
            start = time.perf_counter()
            result = self.process()
            elapsed_ms = (time.perf_counter() - start) * 1000

            span.set_attribute("usage.filter", result.name)
            span.set_attribute("usage.processed", result.processed)
            for key, value in result.metrics.items():
                span.set_attribute(f"usage.{key}", value)

            logger.info(
                "Filter %s complete processed=%s metrics=%s elapsed_ms=%.1f",
                result.name,
                result.processed,
                result.metrics,
                elapsed_ms,
            )
            return result


class Pipeline:
    def __init__(self, *filters: Filter):
        self._filters = filters

    def run(self) -> list[FilterResult]:
        return [stage.run() for stage in self._filters]
