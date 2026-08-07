import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app, get_session


def _fake_session():
    yield None


app.dependency_overrides[get_session] = _fake_session
client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_aggregates_serializes_rows(monkeypatch):
    row = SimpleNamespace(
        customer_id="11111111-1111-1111-1111-111111111111",
        metric="api_calls",
        daily_total=Decimal("10"),
        monthly_total=Decimal("30"),
        rolling_avg=Decimal("7"),
        last_updated=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )
    monkeypatch.setattr(api_main, "_query_aggregates", lambda *a, **k: [row])

    response = client.get("/usage/aggregates", params={"metric": "api_calls"})

    assert response.status_code == 200
    body = response.json()
    assert body[0]["metric"] == "api_calls"
    assert float(body[0]["daily_total"]) == 10.0
    assert float(body[0]["rolling_avg"]) == 7.0


def test_search_returns_hits(monkeypatch):
    document = SimpleNamespace(
        page_content="Invoice ID: inv-1",
        metadata={"metric": "api_calls", "event_id": "ev-1"},
    )
    monkeypatch.setattr(api_main, "_semantic_search", lambda q, k: [(document, 0.12)])

    response = client.get("/usage/search", params={"q": "api usage", "k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "api usage"
    assert body["hits"][0]["metadata"]["metric"] == "api_calls"
    assert body["hits"][0]["score"] == pytest.approx(0.12)


def test_search_requires_query():
    response = client.get("/usage/search")
    assert response.status_code == 422
