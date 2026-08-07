from decimal import Decimal

from etl.aggregate import _build_rows


def test_build_rows_merges_keys_and_fills_defaults():
    daily = {("c1", "m1"): Decimal("10")}
    monthly = {("c1", "m1"): Decimal("30"), ("c2", "m2"): Decimal("5")}
    rolling = {("c1", "m1"): Decimal("7")}

    rows = _build_rows(daily, monthly, rolling)
    by_key = {(row["customer_id"], row["metric"]): row for row in rows}

    assert by_key[("c1", "m1")]["daily_total"] == Decimal("10")
    assert by_key[("c1", "m1")]["monthly_total"] == Decimal("30")
    assert by_key[("c1", "m1")]["rolling_avg"] == Decimal("7")

    assert by_key[("c2", "m2")]["daily_total"] == Decimal(0)
    assert by_key[("c2", "m2")]["monthly_total"] == Decimal("5")
    assert by_key[("c2", "m2")]["rolling_avg"] == Decimal(0)


def test_build_rows_empty_inputs():
    assert _build_rows({}, {}, {}) == []
