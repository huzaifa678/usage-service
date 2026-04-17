from sqlalchemy import Column, String, BigInteger, Numeric, Boolean, TIMESTAMP, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from . import Base
import uuid

class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), nullable=False)
    metric = Column(String(64), nullable=False)
    quantity = Column(BigInteger, nullable=False)
    unit_price = Column(Numeric(19,4), nullable=False)
    total_price = Column(Numeric(19,4), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    processed = Column(Boolean, nullable=False, default=False)
    embedding_processed = Column(Boolean, nullable=False, server_default=text("false")
)
