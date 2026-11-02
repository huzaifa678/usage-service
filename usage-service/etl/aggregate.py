from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, tuple_, update
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


def _key_filter(keys: set | None):
    """tuple IN predicate restricting a query to the dirty (invoice_id, metric)
    keys, or None to aggregate every key (full refresh)."""
    if not keys:
        return None
    return tuple_(UsageEvent.invoice_id, UsageEvent.metric).in_(list(keys))


def _totals_since(session, period: str, keys: set | None) -> dict:
    stmt = (
        select(
            UsageEvent.invoice_id,
            UsageEvent.metric,
            func.coalesce(func.sum(UsageEvent.total_price), 0),
        )
        .where(UsageEvent.created_at >= func.date_trunc(period, func.now()))
        .group_by(UsageEvent.invoice_id, UsageEvent.metric)
    )
    key_filter = _key_filter(keys)
    if key_filter is not None:
        stmt = stmt.where(key_filter)
    rows = session.execute(stmt).all()
    return {(row[0], row[1]): row[2] for row in rows}


def _rolling_average(session, window_start: datetime, keys: set | None) -> dict:
    daily = (
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
    )
    key_filter = _key_filter(keys)
    if key_filter is not None:
        daily = daily.where(key_filter)
    daily_buckets = daily.subquery()
    rows = session.execute(
        select(
            daily_buckets.c.invoice_id,
            daily_buckets.c.metric,
            func.avg(daily_buckets.c.day_total),
        ).group_by(daily_buckets.c.invoice_id, daily_buckets.c.metric)
    ).all()
    return {(row[0], row[1]): row[2] for row in rows}


def _pending(session) -> tuple[list, set]:
    rows = session.execute(
        select(UsageEvent.id, UsageEvent.invoice_id, UsageEvent.metric).where(
            UsageEvent.processed.is_(False)
        )
    ).all()
    ids = [row[0] for row in rows]
    keys = {(row[1], row[2]) for row in rows}
    return ids, keys


def _mark_processed(session, ids: list) -> None:
    if ids:
        session.execute(
            update(UsageEvent).where(UsageEvent.id.in_(ids)).values(processed=True)
        )


class AggregateFilter(Filter):
    name = "aggregate"
    span_name = "usage.aggregate"

    def process(self) -> FilterResult:
        window_start = datetime.now(tz=timezone.utc) - timedelta(
            days=settings.rolling_window_days
        )

        with session_scope() as session:
            if settings.aggregate_full_refresh:
                # True-up mode: recompute every key's windows regardless of the
                # flag. Running on a slow cadence (e.g. an hourly/daily DAG) to
                # correct keys that went silent their daily/monthly totals are
                # only re-zeroed at a period boundary by a full refresh.
                pending_ids: list = []
                keys: set | None = None
            else:
                # Incremental: only recompute keys with new events since the last
                # run — O(keys touched) instead of O(window) every minute.
                pending_ids, keys = _pending(session)
                if not pending_ids:
                    return FilterResult(name=self.name, processed=0)

            daily = _totals_since(session, "day", keys)
            monthly = _totals_since(session, "month", keys)
            rolling = _rolling_average(session, window_start, keys)

            rows = _build_rows(daily, monthly, rolling)
            if not rows:
                # Dirty events fell outside every window; clear the flag so we
                # don't reprocess them forever.
                _mark_processed(session, pending_ids)
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
            _mark_processed(session, pending_ids)
            upserted = len(rows)

        aggregates_upserted_counter().add(upserted)
        return FilterResult(name=self.name, processed=upserted)


def aggregate_usage_events() -> FilterResult:
    return AggregateFilter().run()
