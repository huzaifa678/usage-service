from sqlalchemy import TIMESTAMP, Column, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID

from usage_common.models import Base


class UsageAggregate(Base):
    __tablename__ = "usage_aggregates"

    customer_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    metric = Column(String(64), primary_key=True)
    daily_total = Column(Numeric(19, 4), nullable=False, default=0)
    monthly_total = Column(Numeric(19, 4), nullable=False, default=0)
    rolling_avg = Column(Numeric(19, 4), nullable=False, default=0)
    last_updated = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_usage_aggregates_customer_metric", "customer_id", "metric"),
        Index("ix_usage_aggregates_last_updated", "last_updated"),
    )
