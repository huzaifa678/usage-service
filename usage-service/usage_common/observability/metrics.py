from functools import lru_cache

from opentelemetry import metrics, trace


@lru_cache(maxsize=1)
def _meter() -> metrics.Meter:
    return metrics.get_meter("usage-service")


@lru_cache(maxsize=1)
def tracer() -> trace.Tracer:
    return trace.get_tracer("usage-service")


@lru_cache(maxsize=1)
def events_ingested_counter() -> metrics.Counter:
    return _meter().create_counter(
        "usage.events.ingested",
        unit="1",
        description="Usage-charge events persisted from Kafka",
    )


@lru_cache(maxsize=1)
def events_dead_lettered_counter() -> metrics.Counter:
    return _meter().create_counter(
        "usage.events.dead_lettered",
        unit="1",
        description="Usage-charge events routed to the dead-letter topic",
    )


@lru_cache(maxsize=1)
def aggregates_upserted_counter() -> metrics.Counter:
    return _meter().create_counter(
        "usage.aggregates.upserted",
        unit="1",
        description="Usage aggregate rows recomputed and upserted",
    )


@lru_cache(maxsize=1)
def events_embedded_counter() -> metrics.Counter:
    return _meter().create_counter(
        "usage.events.embedded",
        unit="1",
        description="Usage events embedded into pgvector",
    )
