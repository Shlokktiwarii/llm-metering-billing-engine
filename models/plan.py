from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    api_call_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    ai_token_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    razorpay_plan_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    tenants = relationship("Tenant", back_populates="plan")
    subscriptions = relationship(
        "Subscription",
        back_populates="plan"
    )