import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=lambda: f"tenant-{uuid.uuid4().hex[:8]}"
    )

    plan_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("plans.id"),
        nullable=False,
        default="free"
    )

    api_key_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        default=lambda: f"api-key-{uuid.uuid4().hex}"
    )

    razorpay_customer_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    plan = relationship(
        "Plan",
        back_populates="tenants"
    )

    subscriptions = relationship(
        "Subscription",
        back_populates="tenant"
    )

    usage_events = relationship(
        "UsageEvent",
        back_populates="tenant"
    )