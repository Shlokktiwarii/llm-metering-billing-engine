from datetime import datetime

from sqlalchemy import Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ProcessedWebhookEvent(Base):
    __tablename__ = "processed_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True
    )

    event_type: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )