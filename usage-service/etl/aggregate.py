from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from usage_common.config import settings
from usage_common.db import session_scope
from usage_common.models.usage_aggregate import UsageAggregate
from usage_common.models.usage_event import UsageEvent
from usage_common.observability.logger import get_logger
from usage_common.observability.metrics import aggregates_upserted_counter
from usage_common.pipeline import Filter, FilterResult

logger = get_logger(__name__)


def _build_rows(daily: dict, monthly: dict, rolling: dict) -> list[dict]:
    keys = set(daily) | set(monthly) | set(rolling)
    return [
        {
            "customer_id": customer_id,
            "metric": metric,
            "daily_total": daily.get((customer_id, metric), Decimal(0)),
            "monthly_total": monthly.get((customer_id, metric), Decimal(0)),
            "rolling_avg": rolling.get((customer_id, metric), Decimal(0)),
        }
        for customer_id, metric in keys
    ]


def _totals_since(session, period: str) -> dict:
    rows = session.execute(
        select(
            UsageEvent.invoice_id,
            UsageEvent.metric,
            func.coalesce(func.sum(UsageEvent.total_price), 0),
        )
        .where(UsageEvent.created_at >= func.date_trunc(period, func.now()))
        .group_by(UsageEvent.invoice_id, UsageEvent.metric)
    ).all()
    return {(row[0], row[1]): row[2] for row in rows}


def _rolling_average(session, window_start: datetime) -> dict:
    daily_buckets = (
        select(
            UsageEvent.invoice_id.label("invoice_id"),
            UsageEvent.metric.label("metric"),
            func.date_trunc("day", UsageEvent.created_at).label("day"),
            func.sum(UsageEvent.total_price).label("day_total"),
        )
        .where(UsageEvent.created_at >= window_start)
        .group_by(
            UsageEvent.invoice_id,
            UsageEvent.metric,
            func.date_trunc("day", UsageEvent.created_at),
        )
        .subquery()
    )
    rows = session.execute(
        select(
            daily_buckets.c.invoice_id,
            daily_buckets.c.metric,
            func.avg(daily_buckets.c.day_total),
        ).group_by(daily_buckets.c.invoice_id, daily_buckets.c.metric)
    ).all()
    return {(row[0], row[1]): row[2] for row in rows}


class AggregateFilter(Filter):
    name = "aggregate"
    span_name = "usage.aggregate"

    def process(self) -> FilterResult:
        window_start = datetime.now(tz=timezone.utc) - timedelta(
            days=settings.rolling_window_days
        )

        with session_scope() as session:
            daily = _totals_since(session, "day")
            monthly = _totals_since(session, "month")
            rolling = _rolling_average(session, window_start)

            rows = _build_rows(daily, monthly, rolling)
            if not rows:
                return FilterResult(name=self.name, processed=0)

            stmt = insert(UsageAggregate).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[UsageAggregate.customer_id, UsageAggregate.metric],
                set_={
                    "daily_total": stmt.excluded.daily_total,
                    "monthly_total": stmt.excluded.monthly_total,
                    "rolling_avg": stmt.excluded.rolling_avg,
                    "last_updated": func.now(),
                },
            )
            session.execute(stmt)
            upserted = len(rows)

        aggregates_upserted_counter().add(upserted)
        return FilterResult(name=self.name, processed=upserted)


def aggregate_usage_events() -> FilterResult:
    return AggregateFilter().run()
