from langchain_core.documents import Document

from usage_common.config import settings
from usage_common.db import session_scope
from usage_common.models.usage_event import UsageEvent
from usage_common.observability.logger import get_logger
from usage_common.observability.metrics import events_embedded_counter
from usage_common.pipeline import Filter, FilterResult
from usage_common.resilience import embedding_breaker, with_retry

logger = get_logger(__name__)


def _to_document(event: UsageEvent) -> Document:
    content = (
        f"Invoice ID: {event.invoice_id}\n"
        f"Metric: {event.metric}\n"
        f"Quantity: {event.quantity}\n"
        f"Unit Price: {event.unit_price}\n"
        f"Total Price: {event.total_price}\n"
        f"Created At: {event.created_at}"
    )
    return Document(
        page_content=content,
        metadata={
            "event_id": str(event.id),
            "invoice_id": str(event.invoice_id),
            "metric": event.metric,
            "quantity": int(event.quantity),
            "total_price": float(event.total_price),
            "created_at": event.created_at.isoformat(),
        },
    )


@with_retry()
def _store_documents(documents, ids) -> None:
    from usage_common.rag.vector_store import get_vector_store

    get_vector_store().add_documents(documents, ids=ids)


class EmbedFilter(Filter):
    name = "embed"
    span_name = "usage.embed"

    def process(self) -> FilterResult:
        with session_scope() as session:
            events = (
                session.query(UsageEvent)
                .filter_by(embedding_processed=False)
                .limit(settings.embedding_batch_size)
                .all()
            )

            if not events:
                return FilterResult(name=self.name, processed=0)

            documents = [_to_document(event) for event in events]
            ids = [str(event.id) for event in events]

            embedding_breaker.call(_store_documents, documents, ids)

            for event in events:
                event.embedding_processed = True

            embedded = len(events)

        events_embedded_counter().add(embedded)
        return FilterResult(name=self.name, processed=embedded)


def process_embeddings() -> FilterResult:
    return EmbedFilter().run()
