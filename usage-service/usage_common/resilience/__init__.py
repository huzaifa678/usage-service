import logging

import pybreaker
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from usage_common.config import settings
from usage_common.observability.logger import get_logger

logger = get_logger(__name__)

kafka_breaker = pybreaker.CircuitBreaker(
    fail_max=settings.breaker_fail_max,
    reset_timeout=settings.breaker_reset_timeout,
    name="kafka",
)

database_breaker = pybreaker.CircuitBreaker(
    fail_max=settings.breaker_fail_max,
    reset_timeout=settings.breaker_reset_timeout,
    name="database",
)

embedding_breaker = pybreaker.CircuitBreaker(
    fail_max=settings.breaker_fail_max,
    reset_timeout=settings.breaker_reset_timeout,
    name="embedding",
)


def with_retry(exceptions=(Exception,), attempts: int | None = None):
    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts or settings.retry_max_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
