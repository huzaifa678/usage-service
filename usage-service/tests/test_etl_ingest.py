import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from etl.ingest import _publish_to_dlq, _to_created_at, _to_decimal, _to_usage_event


def test_to_decimal_handles_decimal_and_scalars():
    assert _to_decimal(Decimal("1.50")) == Decimal("1.50")
    assert _to_decimal("2.5") == Decimal("2.5")
    assert _to_decimal(3) == Decimal("3")


def test_to_created_at_passes_through_datetime():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    assert _to_created_at(now) is now


def test_to_created_at_converts_epoch_millis():
    assert _to_created_at(0) == dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def test_to_usage_event_maps_and_coerces_fields():
    record = {
        "usageChargeId": "11111111-1111-1111-1111-111111111111",
        "invoiceId": "22222222-2222-2222-2222-222222222222",
        "metric": "api_calls",
        "quantity": 10,
        "unitPrice": Decimal("0.50"),
        "totalPrice": Decimal("5.00"),
        "createdAt": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    }

    event = _to_usage_event(record)

    assert event.metric == "api_calls"
    assert event.quantity == 10
    assert event.unit_price == Decimal("0.50")
    assert event.total_price == Decimal("5.00")
    assert event.embedding_processed is False
    assert event.processed is False


def test_publish_to_dlq_produces_with_error_headers():
    producer = MagicMock()
    msg = SimpleNamespace(
        key=lambda: b"key",
        value=lambda: b"payload",
        topic=lambda: "billing.usage-charge.created",
        partition=lambda: 3,
        offset=lambda: 42,
    )

    _publish_to_dlq(producer, msg, ValueError("boom"))

    producer.produce.assert_called_once()
    kwargs = producer.produce.call_args.kwargs
    assert kwargs["value"] == b"payload"
    assert kwargs["key"] == b"key"
    header_keys = {key for key, _ in kwargs["headers"]}
    assert {
        "error",
        "error_type",
        "origin_topic",
        "origin_partition",
        "origin_offset",
    } <= header_keys
