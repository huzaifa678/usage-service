import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

from etl.embed import _to_document


def test_to_document_builds_content_and_metadata():
    event = SimpleNamespace(
        id="ev-1",
        invoice_id="inv-1",
        metric="api_calls",
        quantity=10,
        unit_price=Decimal("0.50"),
        total_price=Decimal("5.00"),
        created_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )

    document = _to_document(event)

    assert "api_calls" in document.page_content
    assert "inv-1" in document.page_content
    assert document.metadata["event_id"] == "ev-1"
    assert document.metadata["invoice_id"] == "inv-1"
    assert document.metadata["metric"] == "api_calls"
    assert document.metadata["quantity"] == 10
    assert document.metadata["total_price"] == 5.0
