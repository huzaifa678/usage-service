import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _psycopg3_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://usage_user:usage_password@localhost:5435/usage_db",
        )
    )

    kafka_bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    schema_registry_url: str = field(
        default_factory=lambda: os.getenv(
            "SCHEMA_REGISTRY_URL", "http://localhost:9094"
        )
    )
    kafka_group_id: str = field(
        default_factory=lambda: os.getenv("KAFKA_GROUP_ID", "usage-service")
    )
    kafka_topic: str = field(
        default_factory=lambda: os.getenv("KAFKA_TOPIC", "billing.usage-charge.created")
    )
    kafka_dlq_topic: str = field(
        default_factory=lambda: os.getenv(
            "KAFKA_DLQ_TOPIC", "billing.usage-charge.created.DLT"
        )
    )
    kafka_max_messages: int = field(
        default_factory=lambda: int(os.getenv("KAFKA_MAX_MESSAGES", "100"))
    )
    kafka_poll_timeout: float = field(
        default_factory=lambda: float(os.getenv("KAFKA_POLL_TIMEOUT", "1.0"))
    )
    avro_schema_path: str = field(
        default_factory=lambda: os.getenv(
            "AVRO_SCHEMA_PATH", "/opt/airflow/avro/usage_event.avsc"
        )
    )

    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    pgvector_collection: str = field(
        default_factory=lambda: os.getenv("PGVECTOR_COLLECTION", "usage_events")
    )
    embedding_batch_size: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_BATCH_SIZE", "200"))
    )

    rolling_window_days: int = field(
        default_factory=lambda: int(os.getenv("ROLLING_WINDOW_DAYS", "7"))
    )

    otel_endpoint: str = field(
        default_factory=lambda: os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:43180"
        )
    )
    otel_service_name: str = field(
        default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "usage-service")
    )

    breaker_fail_max: int = field(
        default_factory=lambda: int(os.getenv("BREAKER_FAIL_MAX", "5"))
    )
    breaker_reset_timeout: int = field(
        default_factory=lambda: int(os.getenv("BREAKER_RESET_TIMEOUT", "30"))
    )
    retry_max_attempts: int = field(
        default_factory=lambda: int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    )

    @property
    def pgvector_url(self) -> str:
        return _psycopg3_url(self.database_url)


settings = Settings()
