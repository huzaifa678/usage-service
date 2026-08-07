# Usage Service

![Status - In Development](https://img.shields.io/badge/Status-In%20Development-yellow)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Airflow](https://img.shields.io/badge/Airflow-2.10-orange)

A Python-based data pipeline and AI service that ingests usage-charge events from Kafka, aggregates them into time-series metrics, and builds a **RAG (Retrieval-Augmented Generation)** knowledge base from usage data using LangChain, **pgvector**, and OpenAI embeddings. Orchestrated by **Apache Airflow**, with a **FastAPI** query layer and full OpenTelemetry traces, logs, and metrics exported to the Grafana stack.

## Architecture

```mermaid
graph TD
    A["Kafka<br/>billing.usage-charge.created<br/>Avro + Schema Registry"] -->|Avro Events| B["🎯 Usage Service<br/>Apache Airflow 2.10"]

    B --> C["DAG: usage_kafka_ingestion<br/>Every 1 min · max 100 msgs/run"]
    C -->|Idempotent upsert| D["PostgreSQL<br/>usage_events table"]

    D -->|ExternalTaskSensor| E["DAG: usage_aggregation<br/>Waits for ingestion · Every 1 min"]
    E -->|Aggregate metrics| F["PostgreSQL<br/>usage_aggregates table"]

    D -->|ExternalTaskSensor| G["DAG: usage_rag_embedding<br/>Waits for aggregation · Every 1 min"]
    G -->|OpenAI Embeddings| H["PostgreSQL + pgvector<br/>Vector Store<br/>usage_events collection"]

    C -->|Poison / business-logic errors| L["Kafka DLQ<br/>billing.usage-charge.created.DLT"]

    B --> J["🔁 Circuit Breaker<br/>pybreaker · tenacity retry"]
    B --> K["👁️ OpenTelemetry<br/>Traces · Logs · Metrics · OTLP → Grafana"]

    style A fill:#FF6B6B,stroke:#333,color:#fff,stroke-width:2px
    style B fill:#4ECDC4,stroke:#333,color:#fff,stroke-width:3px
    style C fill:#FFA07A,stroke:#333,color:#fff,stroke-width:2px
    style D fill:#6C63FF,stroke:#333,color:#fff,stroke-width:2px
    style E fill:#FFA07A,stroke:#333,color:#fff,stroke-width:2px
    style F fill:#6C63FF,stroke:#333,color:#fff,stroke-width:2px
    style G fill:#FFA07A,stroke:#333,color:#fff,stroke-width:2px
    style H fill:#95E1D3,stroke:#333,color:#333,stroke-width:2px
    style J fill:#FFD700,stroke:#333,color:#333,stroke-width:2px
    style K fill:#FF8B94,stroke:#333,color:#fff,stroke-width:2px
    style L fill:#FF6B6B,stroke:#333,color:#fff,stroke-width:2px
```

## Tech Stack

| Concern | Technology |
|---|---|
| Language | Python 3.11 |
| Orchestration | Apache Airflow 2.10 |
| Database | PostgreSQL (SQLAlchemy + Alembic) |
| Messaging | Confluent Kafka (Avro + Schema Registry) |
| AI / RAG | LangChain, LangChain-OpenAI, langchain-postgres (pgvector), sentence-transformers |
| Vector store | PostgreSQL + pgvector |
| LLM | OpenAI API |
| API | FastAPI + Uvicorn |
| Resilience | pybreaker (circuit breaker), tenacity (retry), Kafka DLQ |
| Observability | OpenTelemetry (traces, logs, metrics) → Grafana stack (Tempo / Loki / Mimir) |
| Containerization | Docker Compose (Airflow cluster) |

## Features

- **Kafka ingestion** — consumes `billing.usage-charge.created` Avro events in batches (up to 100 per run), deserializes with Confluent Schema Registry, and persists to PostgreSQL idempotently
- **Dead-letter queue** — a poison message or per-record business-logic error is routed to the `billing.usage-charge.created.DLT` topic (with the exception and origin offset in the headers) so one bad record never blocks the batch
- **Usage aggregation** — idempotent recompute of daily/monthly totals and a trailing rolling average per customer and metric; runs only after ingestion completes (Airflow `ExternalTaskSensor`)
- **Vector embeddings** — encodes usage events into embeddings via OpenAI and upserts them into PostgreSQL + pgvector for semantic search and RAG queries
- **FastAPI** — HTTP API for querying aggregated usage data and RAG semantic search
- **Resilience** — pybreaker circuit breakers and tenacity retries wrap Kafka, database, and embedding calls
- **OpenTelemetry** — traces, logs, and metrics instrumented on the ETL stages, FastAPI, and SQLAlchemy, exported via OTLP to the Grafana stack

## Airflow DAGs

| DAG | Schedule | Description |
|---|---|---|
| `usage_kafka_ingestion` | `*/1 * * * *` | Polls Kafka, deserializes Avro events, writes to `usage_events` table |
| `usage_aggregation` | `*/1 * * * *` | Waits for ingestion DAG, then recomputes `usage_aggregates` |
| `usage_rag_embedding` | `*/1 * * * *` | Waits for aggregation, generates OpenAI embeddings and upserts into pgvector |

## Project Structure

```
usage-service/
├── usage_common/                             # shared package (single source of truth)
│   ├── config/                               # env-driven settings
│   ├── db/                                   # SQLAlchemy engine + session scope
│   ├── models/                               # UsageEvent, UsageAggregate
│   ├── resilience/                           # pybreaker breakers + tenacity retry
│   ├── pipeline/                             # Filter ABC + FilterResult + Pipeline
│   ├── observability/
│   │   ├── tracing.py                        # OTel traces/logs/metrics provider setup
│   │   ├── metrics.py                        # OTel counters + tracer accessors
│   │   └── logger.py                         # logging config (format + instrumentation)
│   └── rag/
│       └── vector_store.py                   # pgvector (PGVector) factory
├── etl/                                      # ETL stages as pipes-and-filters
│   ├── ingest.py                             # IngestFilter: Kafka → PostgreSQL + DLQ
│   ├── aggregate.py                          # AggregateFilter: idempotent recompute
│   ├── embed.py                              # EmbedFilter: usage events → pgvector
│   └── pipeline.py                           # composes the three filters in-process
├── api/
│   └── main.py                               # FastAPI app (aggregates + RAG search)
├── main.py                                   # uvicorn entrypoint (exposes api app)
├── airflow/
│   ├── dags/
│   │   ├── usage_kafka_ingestion_dag.py
│   │   ├── usage_aggregation_dag.py
│   │   └── usage_rag_embedding_dag.py
│   ├── avro/usage_event.avsc                 # Avro schema
│   ├── config/airflow.cfg
│   ├── docker-compose.yaml                   # Full Airflow cluster
│   ├── Dockerfile                            # Airflow worker image
│   ├── Dockerfile.consumer                   # Standalone consumer image
│   ├── Dockerfile.aggregation                # Standalone aggregation image
│   └── Dockerfile.embed                      # Standalone embedding image
├── migrations/                               # Alembic migrations
│   └── versions/
│       ├── 73ccf3578c56_create_usage_tables.py
│       └── a1b2c3d4e5f6_enable_pgvector_extension.py
├── tests/                                    # ETL unit tests + FastAPI integration tests
├── requirements.txt
├── alembic.ini
└── .env
```

## Getting Started

### Prerequisites

- Python 3.11
- Docker & Docker Compose
- PostgreSQL
- Kafka + Confluent Schema Registry
- OpenAI API key
- (Optional) MLflow tracking server

### Environment Variables

Create a `.env` file in `usage-service/airflow/`:

```env
# Database
DATABASE_URL=postgresql+psycopg2://usage_user:usage_password@localhost:5435/usage_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
SCHEMA_REGISTRY_URL=http://localhost:9094
KAFKA_TOPIC=billing.usage-charge.created
KAFKA_DLQ_TOPIC=billing.usage-charge.created.DLT

# OpenAI / pgvector RAG
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
PGVECTOR_COLLECTION=usage_events

# OpenTelemetry (base OTLP HTTP endpoint; /v1/{traces,logs,metrics} are appended)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=usage-service
```

### Run with Docker Compose (Recommended)

The Airflow cluster (scheduler, webserver, worker, Redis, PostgreSQL) is fully defined in `airflow/docker-compose.yaml`:

```bash
cd usage-service/airflow

# Initialize the Airflow database
docker compose up airflow-init

# Start all services
docker compose up -d

# Airflow UI: http://localhost:8080
# Default credentials: airflow / airflow
```

### Run Locally (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI
uvicorn main:app --host 0.0.0.0 --port 8083 --reload
```

### Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1
```

## Kafka Event Schema

The service consumes `billing.usage-charge.created` events with the following Avro schema (`airflow/avro/usage_event.avsc`):

```json
{
  "type": "record",
  "name": "UsageChargeCreated",
  "namespace": "com.project.billing_service.avro",
  "fields": [
    { "name": "usageChargeId", "type": { "type": "string", "logicalType": "uuid" } },
    { "name": "invoiceId", "type": { "type": "string", "logicalType": "uuid" } },
    { "name": "metric", "type": "string" },
    { "name": "quantity", "type": "long" },
    { "name": "unitPrice", "type": { "type": "bytes", "logicalType": "decimal", "precision": 10, "scale": 2 } },
    { "name": "totalPrice", "type": { "type": "bytes", "logicalType": "decimal", "precision": 10, "scale": 2 } },
    { "name": "createdAt", "type": { "type": "long", "logicalType": "timestamp-millis" } }
  ]
}
```

Decimal and timestamp logical types are decoded by fastavro automatically, so the consumer receives `Decimal` and timezone-aware `datetime` values directly.

## Dead-Letter Queue

The ingestion consumer deserializes and persists one record at a time. If a record fails — malformed Avro or a per-record business-logic/mapping error — it is published to `KAFKA_DLQ_TOPIC` (`billing.usage-charge.created.DLT`) with headers capturing `error`, `error_type`, and the origin topic/partition/offset, and ingestion continues. A single poison message never blocks the batch, and offsets are only committed once the batch has been persisted.

## RAG Pipeline

The `usage_rag_embedding` DAG:

1. Queries unprocessed usage events from PostgreSQL (`embedding_processed = false`)
2. Generates embeddings using OpenAI's embedding model via LangChain
3. Upserts documents into PostgreSQL + pgvector keyed by event id (idempotent) with metadata (metric, quantity, timestamps)
4. Marks events as processed in PostgreSQL

Semantic search is exposed over HTTP at `GET /usage/search?q=...&k=...`, powering AI-driven analytics queries.

## Pipeline (pipes-and-filters)

The ETL is structured as **pipes-and-filters**: each stage is a `Filter` ([`usage_common/pipeline/`](usage-service/usage_common/pipeline/__init__.py)) — `IngestFilter`, `AggregateFilter`, `EmbedFilter` — and the **pipes are durable stores** (Kafka topic → `usage_events` → `usage_aggregates` / pgvector), so every stage is independently restartable and idempotent.

The `Filter` base class owns the uniform lifecycle (observability init, span, timing, metrics, structured `FilterResult`); each filter implements only `process()`, and the pure transforms (`_to_usage_event`, `_build_rows`, `_to_document`) stay separate and unit-testable. Airflow is the pump across DAG tasks; for a single-process run the same filters compose via `etl.pipeline.build_pipeline().run()`.

## API

FastAPI app ([`api/main.py`](usage-service/api/main.py)), run with `uvicorn main:app`:

| Endpoint | Description |
|---|---|
| `GET /health` | Liveness probe |
| `GET /usage/aggregates?customer_id=&metric=` | Query recomputed usage aggregates |
| `GET /usage/search?q=&k=` | pgvector semantic search over usage events |

Database and embedding calls are wrapped with pybreaker circuit breakers and tenacity retries.

## Observability

OpenTelemetry is configured in [`usage_common/observability/tracing.py`](usage-service/usage_common/observability/tracing.py) and emits **traces, logs, and metrics** over OTLP/HTTP to the Grafana stack (Tempo / Loki / Mimir). Instrumented surfaces:

- ETL stages — each run is a span (`usage.ingest.batch`, `usage.aggregate`, `usage.embed`) with counters in [`usage_common/observability/metrics.py`](usage-service/usage_common/observability/metrics.py) (`usage.events.ingested`, `usage.events.dead_lettered`, `usage.aggregates.upserted`, `usage.events.embedded`)
- FastAPI request/response lifecycle
- SQLAlchemy queries

The exporter targets `OTEL_EXPORTER_OTLP_ENDPOINT`; the `/v1/{traces,logs,metrics}` paths are appended automatically.

## Testing

```bash
pip install -r requirements.txt
pytest
```

- **Unit tests** ([`tests/test_etl_*`](usage-service/tests)) cover the ETL pure logic: Avro record mapping and decimal/timestamp coercion, DLQ header construction, aggregate row-building, and embedding document mapping.
- **Integration tests** ([`tests/test_api.py`](usage-service/tests/test_api.py)) drive the FastAPI app through `TestClient` with dependency overrides, covering health, aggregate serialization, semantic-search response shape, and request validation.

## License

MIT
## Security & Guardrails

Container supply-chain guardrails run in CI and locally — see [`policy/README.md`](policy/README.md).

- **Dockerfile Policy as Code** — OPA/Rego via `conftest` (`policy/docker/`): hard-gates unpinned/`:latest` base images, `USER root` final stages, and `ADD <remote-url>`; warns on missing `USER`/`HEALTHCHECK`, tag-not-digest, `apt` without `--no-install-recommends`, etc.
- **Checkov** — Dockerfile + secret scanning (baseline/report mode).
- **Trivy** — image scanning **before push** in the build pipeline (fail-closed on fixable CRITICAL/HIGH), plus `trivy fs` (deps) and `trivy config` (misconfig) on PRs. Complements source-level scanning (e.g. SonarQube).

```bash
./scripts/guardrails.sh   # conftest + checkov + trivy (skips tools not installed)
```

CI: [`.github/workflows/security.yml`](.github/workflows/security.yml) (PR gate) + the Trivy image scan wired into the build workflow.
