"""add usage_events indexes

Indexes the columns the ETL filters/groups on. Before this, usage_events had
only its primary key on `id`, so every aggregate run (date_trunc range scans +
GROUP BY on invoice_id/metric) and the embed stage's `embedding_processed`
lookup were sequential scans whose cost grew with the table.

Created CONCURRENTLY: the table is written every minute by the ingest DAG, so a
plain CREATE INDEX would take an ACCESS EXCLUSIVE lock and block ingestion while
the index builds. CONCURRENTLY cannot run inside a transaction, hence the
autocommit block.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-10-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # Range scans on `created_at` (_totals_since / _rolling_average window).
        op.create_index(
            "ix_usage_events_created_at",
            "usage_events",
            ["created_at"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        # Covers the GROUP BY (invoice_id, metric) over a created_at window.
        op.create_index(
            "ix_usage_events_invoice_metric_created",
            "usage_events",
            ["invoice_id", "metric", "created_at"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        # Partial index for the embed stage's `embedding_processed = false` batch
        # pick: stays small because processed rows drop out of the index.
        op.create_index(
            "ix_usage_events_unembedded",
            "usage_events",
            ["created_at"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
            postgresql_where="embedding_processed = false",
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_usage_events_unembedded",
            table_name="usage_events",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_usage_events_invoice_metric_created",
            table_name="usage_events",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_usage_events_created_at",
            table_name="usage_events",
            postgresql_concurrently=True,
            if_exists=True,
        )
