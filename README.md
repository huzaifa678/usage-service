# Usage Service

![Status - In Development](https://img.shields.io/badge/Status-In%20Development-yellow)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Airflow](https://img.shields.io/badge/Airflow-2.10-orange)

A Python-based data pipeline and AI service that ingests usage-charge events from Kafka, aggregates them into time-series metrics, and builds a **RAG (Retrieval-Augmented Generation)** knowledge base from usage data using LangChain, ChromaDB, and OpenAI embeddings. Orchestrated by **Apache Airflow**.

## Architecture

```mermaid
graph TD
    A["Kafka<br/>billing.usage-charge.created<br/>Avro + Schema Registry"] -->|Avro Events| B["🎯 Usage Service<br/>Apache Airflow 2.10"]

    B --> C["DAG: usage_kafka_ingestion<br/>Every 1 min · max 100 msgs/run"]
    C -->|Idempotent upsert| D["PostgreSQL<br/>usage_events table"]

    D -->|ExternalTaskSensor| E["DAG: usage_aggregation<br/>Waits for ingestion · Every 1 min"]
    E -->|Aggregate metrics| F["PostgreSQL<br/>usage_aggregates table"]

    D -->|ExternalTaskSensor| G["DAG: usage_rag_embedding<br/>Waits for aggregation · Every 1 min"]
    G -->|OpenAI Embeddings| H["ChromaDB<br/>Vector Store<br/>usage_events collection"]

    B --> J["🔁 Circuit Breaker<br/>pybreaker · tenacity retry"]
    B --> K["👁️ OpenTelemetry<br/>Traces · Logs · OTLP Export"]

    style A fill:#FF6B6B,stroke:#333,color:#fff,stroke-width:2px
    style B fill:#4ECDC4,stroke:#333,color:#fff,stroke-width:3px
    style C fill:#FFA07A,stroke:#333,color:#fff,stroke-width:2px
    style D fill:#6C63FF,stroke:#333,color:#fff,stroke-width:2px
    style E fill:#FFA07A,stroke:#333,color:#fff,stroke-width:2px
    style F fill:#6C63FF,stroke:#333,color:#fff,stroke-width:2px
    style G fill:#FFA07A,stroke:#333,color:#fff,stroke-width:2px
    style H fill:#95E1D3,stroke:#333,color:#333,stroke-width:2px
    style I fill:#FFE66D,stroke:#333,color:#333,stroke-width:2px
    style J fill:#FFD700,stroke:#333,color:#333,stroke-width:2px
    style K fill:#FF8B94,stroke:#333,color:#fff,stroke-width:2px
```

## Tech Stack

| Concern | Technology |
|---|---|
| Language | Python 3.11 |
| Orchestration | Apache Airflow 2.10 |
| Database | PostgreSQL (SQLAlchemy + Alembic) |
| Messaging | Confluent Kafka (Avro + Schema Registry) |
| AI / RAG | LangChain, LangChain-OpenAI, ChromaDB, sentence-transformers |
| LLM | OpenAI API |
| Resilience | pybreaker (circuit breaker), tenacity (retry) |
| Observability | OpenTelemetry (traces, logs, metrics) |
| Containerization | Docker Compose (Airflow cluster) |

## Features

- **Kafka ingestion** — consumes `billing.usage-charge.created` Avro events in batches (up to 100 per run), deserializes with Confluent Schema Registry, and persists to PostgreSQL idempotently
- **Usage aggregation** — aggregates raw events into time-bucketed metrics; runs only after ingestion completes (Airflow `ExternalTaskSensor`)
- **Vector embeddings** — encodes usage events into embeddings via OpenAI and stores them in ChromaDB for semantic search and RAG queries
- **FastAPI** — HTTP API for querying aggregated usage data and RAG endpoints
- **Circuit breaker** — pybreaker wraps external calls to prevent cascade failures
- **OpenTelemetry** — distributed tracing instrumented on FastAPI, SQLAlchemy, and HTTP requests

## Airflow DAGs

| DAG | Schedule | Description |
|---|---|---|
| `usage_kafka_ingestion` | `*/1 * * * *` | Polls Kafka, deserializes Avro events, writes to `usage_events` table |
| `usage_aggregation` | `*/1 * * * *` | Waits for ingestion DAG, then aggregates events into `usage_aggregates` |
| `usage_chroma_embedding_store` | Configurable | Generates OpenAI embeddings for usage events and upserts into ChromaDB |

## Project Structure

```
usage-service/
├── airflow/
│   ├── dags/
│   │   ├── usage_kafka_ingestion_dag.py      # Kafka → PostgreSQL
│   │   ├── usage_aggregation_dag.py          # Aggregation pipeline
│   │   └── usage_chroma_embedding_store.py   # Embedding pipeline
│   ├── consumer/
│   │   └── event_consume.py                  # Kafka consumer logic
│   ├── aggregation/
│   │   └── usage_aggregate.py                # Aggregation logic
│   ├── embed/                                # ChromaDB embedding logic
│   ├── avro/
│   │   └── usage_event.avsc                  # Avro schema
│   ├── models/
│   │   └── usage_event.py                    # SQLAlchemy model (Airflow)
│   ├── config/
│   │   └── airflow.cfg                       # Airflow configuration
│   ├── docker-compose.yaml                   # Full Airflow cluster
│   ├── Dockerfile                            # Airflow worker image
│   ├── Dockerfile.consumer                   # Consumer image
│   ├── Dockerfile.aggregation                # Aggregation image
│   └── Dockerfile.embed                      # Embedding image
├── models/
│   ├── usage_event.py                        # SQLAlchemy model
│   └── usage_aggregate.py                    # Aggregate model
├── observability/
│   └── tracing.py                            # OpenTelemetry setup
├── breaker/
│   └── pybreaker.py                          # Circuit breaker config
├── migrations/                               # Alembic migrations
│   └── versions/
│       └── 73ccf3578c56_create_usage_tables.py
├── config/                                   # App configuration
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
DATABASE_URL=postgresql://usage_user:usage_password@localhost:5435/usage_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
SCHEMA_REGISTRY_URL=http://localhost:9094

# OpenAI
OPENAI_API_KEY=sk-...

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
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
  "fields": [
    { "name": "usageChargeId", "type": "string" },
    { "name": "invoiceId", "type": "string" },
    { "name": "metric", "type": "string" },
    { "name": "quantity", "type": "double" },
    { "name": "unitPrice", "type": "bytes" },
    { "name": "totalPrice", "type": "bytes" },
    { "name": "createdAt", "type": "long" }
  ]
}
```

## RAG Pipeline

The `usage_chroma_embedding_store` DAG:

1. Queries unprocessed usage events from PostgreSQL (`embedding_processed = false`)
2. Generates embeddings using OpenAI's embedding model via LangChain
3. Upserts documents into ChromaDB with metadata (metric, quantity, timestamps)
4. Marks events as processed in PostgreSQL
5. Logs experiment metrics to MLflow

This enables semantic search over usage patterns and powers AI-driven analytics queries.

## Observability

OpenTelemetry is configured in `observability/tracing.py` and instruments:

- FastAPI request/response lifecycle
- SQLAlchemy queries
- Outbound HTTP requests

Traces are exported via OTLP to the configured collector endpoint.

## License

MIT
