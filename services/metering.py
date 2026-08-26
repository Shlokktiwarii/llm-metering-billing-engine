from uuid import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models.usage_event import UsageEvent


class MeterService:

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        tenant_id: UUID,
        metric_name: str,
        quantity: int,
        idempotency_key: str,
    ):
        event = UsageEvent(
            tenant_id=tenant_id,
            metric_name=metric_name,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )

        self.db.add(event)

        try:
            self.db.commit()
            self.db.refresh(event)

            return event, True # True means new event was created

        except IntegrityError:
            self.db.rollback()

            existing_event = (
                self.db.query(UsageEvent)
                .filter(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.idempotency_key == idempotency_key,
                )
                .first()
            )

            return existing_event, False # False means the event already existed