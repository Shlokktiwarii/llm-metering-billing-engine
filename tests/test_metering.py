import uuid

from docker import models
from models.tenant import Tenant
from db.database import SessionLocal
from models.usage_event import UsageEvent
from services.metering import MeterService


def test_duplicate_idempotency_key_creates_one_event():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    tenant = Tenant(id=tenant_id)
    db.add(tenant)
    db.commit()
    idempotency_key = "test-key-123"

    try:
        meter = MeterService(db)

        # First request
        event1, created1 = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=1,
            idempotency_key=idempotency_key,
        )

        # Retry of the exact same request
        event2, created2 = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=1,

            idempotency_key=idempotency_key,
        )

        # First request created an event
        assert created1 is True

        # Second request was recognized as a duplicate
        assert created2 is False

        # Both requests point to the same database event
        assert event1.id == event2.id

        # Only ONE event exists
        count = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
            .count()
        )

        assert count == 1

    finally:
        db.query(UsageEvent).filter(
            UsageEvent.tenant_id == tenant_id
        ).delete()

        db.commit()
        db.close()