import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False
    )

    plan_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("plans.id"),
        nullable=False
    )

    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    current_period_start: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    current_period_end: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    tenant = relationship(
        "Tenant",
        back_populates="subscriptions"
    )

    plan = relationship(
        "Plan",
        back_populates="subscriptions"
    )