import os
from datetime import datetime
from decimal import Decimal
from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.usage_event import UsageEvent

load_dotenv()

def decimal_deserializer(obj, ctx):
    if isinstance(obj, bytes):
        unscaled = int.from_bytes(obj, byteorder='big', signed=True)
        return Decimal(unscaled) / (10 ** 2)
    return obj


def consume_kafka_batch():
    schema_registry_conf = {
        "url": os.getenv("SCHEMA_REGISTRY_URL")
    }

    schema_registry_client = SchemaRegistryClient(schema_registry_conf)

    with open("/opt/airflow/avro/usage_event.avsc", "r") as f:
        avro_schema_str = f.read()

    avro_deserializer = AvroDeserializer(
        schema_registry_client=schema_registry_client,
        schema_str=avro_schema_str,
        from_dict=decimal_deserializer
    )

    consumer_conf = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
        "group.id": "usage-service",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "value.deserializer": avro_deserializer,
    }

    consumer = DeserializingConsumer(consumer_conf)
    consumer.subscribe(["billing.usage-charge.created"])

    engine = create_engine(os.getenv("DATABASE_URL"))
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    max_messages = 100
    processed = 0

    try:
        while processed < max_messages:
            msg = consumer.poll(1.0)

            if msg is None:
                break

            if msg.error():
                print(f"Kafka error: {msg.error()}")
                continue

            event = msg.value()

            usage_event = UsageEvent(
                id=event["usageChargeId"],
                invoice_id=event["invoiceId"],
                metric=event["metric"],
                quantity=event["quantity"],
                unit_price=event["unitPrice"],
                total_price=event["totalPrice"],
                created_at=datetime.fromtimestamp(
                    event["createdAt"] / 1000
                ),
                embedding_processed=False
            )

            db.merge(usage_event)  # idempotent insert
            processed += 1

        db.commit()

        consumer.commit()

        print(f"Processed {processed} messages")

    except Exception as e:
        db.rollback()
        raise e

    finally:
        db.close()
        consumer.close()
