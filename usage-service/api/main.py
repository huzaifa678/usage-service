from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional

from fastapi import Depends, FastAPI, Query
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from pydantic import BaseModel
from sqlalchemy.orm import Session

from usage_common.config import settings
from usage_common.db import SessionLocal, engine
from usage_common.models.usage_aggregate import UsageAggregate
from usage_common.observability.logger import get_logger
from usage_common.observability.tracing import setup_observability
from usage_common.resilience import database_breaker, embedding_breaker, with_retry

logger = get_logger(__name__)


class AggregateResponse(BaseModel):
    customer_id: str
    metric: str
    daily_total: Decimal
    monthly_total: Decimal
    rolling_avg: Decimal
    last_updated: Optional[str] = None


class SearchHit(BaseModel):
    content: str
    metadata: dict
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_observability(settings.otel_service_name)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    yield


app = FastAPI(title="Usage Service API", version="0.1.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@with_retry()
def _query_aggregates(
    session: Session, customer_id: Optional[str], metric: Optional[str]
) -> list[UsageAggregate]:
    query = session.query(UsageAggregate)
    if customer_id:
        query = query.filter(UsageAggregate.customer_id == customer_id)
    if metric:
        query = query.filter(UsageAggregate.metric == metric)
    return query.order_by(UsageAggregate.last_updated.desc()).limit(500).all()


@with_retry()
def _semantic_search(query: str, k: int):
    from usage_common.rag.vector_store import get_vector_store

    return get_vector_store().similarity_search_with_score(query, k=k)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/usage/aggregates", response_model=list[AggregateResponse])
def get_aggregates(
    customer_id: Optional[str] = Query(default=None),
    metric: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> list[AggregateResponse]:
    rows = database_breaker.call(_query_aggregates, session, customer_id, metric)
    return [
        AggregateResponse(
            customer_id=str(row.customer_id),
            metric=row.metric,
            daily_total=row.daily_total,
            monthly_total=row.monthly_total,
            rolling_avg=row.rolling_avg,
            last_updated=row.last_updated.isoformat() if row.last_updated else None,
        )
        for row in rows
    ]


@app.get("/usage/search", response_model=SearchResponse)
def search_usage(
    q: str = Query(min_length=1),
    k: int = Query(default=5, ge=1, le=50),
) -> SearchResponse:
    results = embedding_breaker.call(_semantic_search, q, k)
    hits = [
        SearchHit(
            content=document.page_content,
            metadata=document.metadata,
            score=float(score),
        )
        for document, score in results
    ]
    return SearchResponse(query=q, hits=hits)
