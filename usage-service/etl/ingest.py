from datetime import datetime, timezone
from decimal import Decimal

from confluent_kafka import Consumer, KafkaError, Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import MessageField, SerializationContext

from usage_common.config import settings
from usage_common.db import SessionLocal
from usage_common.models.usage_event import UsageEvent
from usage_common.observability.logger import get_logger
from usage_common.observability.metrics import (
    events_dead_lettered_counter,
    events_ingested_counter,
)
from usage_common.pipeline import Filter, FilterResult
from usage_common.resilience import kafka_breaker, with_retry

logger = get_logger(__name__)


@with_retry()
def _build_deserializer() -> AvroDeserializer:
    client = SchemaRegistryClient({"url": settings.schema_registry_url})
    with open(settings.avro_schema_path, "r") as handle:
        schema_str = handle.read()
    return AvroDeserializer(schema_registry_client=client, schema_str=schema_str)


def _build_consumer() -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def _build_dlq_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})


def _to_created_at(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _to_usage_event(record: dict) -> UsageEvent:
    return UsageEvent(
        id=str(record["usageChargeId"]),
        invoice_id=str(record["invoiceId"]),
        metric=record["metric"],
        quantity=int(record["quantity"]),
        unit_price=_to_decimal(record["unitPrice"]),
        total_price=_to_decimal(record["totalPrice"]),
        created_at=_to_created_at(record["createdAt"]),
        embedding_processed=False,
        processed=False,
    )


def _publish_to_dlq(producer: Producer, msg, error: Exception) -> None:
    headers = [
        ("error", str(error).encode("utf-8")),
        ("error_type", type(error).__name__.encode("utf-8")),
        ("origin_topic", (msg.topic() or "").encode("utf-8")),
        ("origin_partition", str(msg.partition()).encode("utf-8")),
        ("origin_offset", str(msg.offset()).encode("utf-8")),
        ("failed_at", datetime.now(tz=timezone.utc).isoformat().encode("utf-8")),
    ]
    producer.produce(
        topic=settings.kafka_dlq_topic,
        key=msg.key(),
        value=msg.value(),
        headers=headers,
    )
    producer.poll(0)
    logger.error(
        "Routed poison message to DLQ topic=%s origin_offset=%s error=%s",
        settings.kafka_dlq_topic,
        msg.offset(),
        error,
    )


class IngestFilter(Filter):
    name = "ingest"
    span_name = "usage.ingest.batch"

    def process(self) -> FilterResult:
        deserializer = _build_deserializer()
        consumer = _build_consumer()
        dlq_producer = _build_dlq_producer()
        kafka_breaker.call(consumer.subscribe, [settings.kafka_topic])

        session = SessionLocal()
        processed = 0
        dead_lettered = 0

        try:
            while processed + dead_lettered < settings.kafka_max_messages:
                msg = consumer.poll(settings.kafka_poll_timeout)

                if msg is None:
                    break

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        break
                    logger.error("Kafka transport error: %s", msg.error())
                    continue

                try:
                    record = deserializer(
                        msg.value(),
                        SerializationContext(msg.topic(), MessageField.VALUE),
                    )
                    session.merge(_to_usage_event(record))
                    processed += 1
                except Exception as exc:
                    _publish_to_dlq(dlq_producer, msg, exc)
                    dead_lettered += 1

            session.commit()
            consumer.commit()
            dlq_producer.flush(10)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            consumer.close()

        events_ingested_counter().add(processed)
        events_dead_lettered_counter().add(dead_lettered)
        return FilterResult(
            name=self.name,
            processed=processed,
            metrics={"dead_lettered": dead_lettered},
        )


def consume_kafka_batch() -> FilterResult:
    return IngestFilter().run()
