import uuid
from datetime import datetime, timedelta, timezone

from db.database import SessionLocal
from models.plan import Plan
from models.tenant import Tenant
from models.subscription import Subscription
from models.usage_event import UsageEvent
from services.metering import MeterService


def test_duplicate_idempotency_key_creates_one_event():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    idempotency_key = "test-key-123"
    plan_id = "test-plan"

    try:
        # -------------------------------------------------
        # 1. Create a test plan
        # -------------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Test Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        # -------------------------------------------------
        # 2. Create a test tenant
        # -------------------------------------------------

        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            plan_id=plan_id,
            api_key_hash="test-api-key-hash-123",
        )

        db.add(tenant)
        db.commit()

        # -------------------------------------------------
        # 3. Create an active subscription
        # -------------------------------------------------

        now = datetime.now(timezone.utc)

        subscription = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            status="active",
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),
        )

        db.add(subscription)
        db.commit()

        # -------------------------------------------------
        # 4. Create MeterService
        # -------------------------------------------------

        meter = MeterService(db)

        # -------------------------------------------------
        # 5. First request
        # -------------------------------------------------

        event1, created1 = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=1,
            idempotency_key=idempotency_key,
        )

        # -------------------------------------------------
        # 6. Same request again
        # -------------------------------------------------

        event2, created2 = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=1,
            idempotency_key=idempotency_key,
        )

        # -------------------------------------------------
        # 7. Assertions
        # -------------------------------------------------

        assert created1 is True
        assert created2 is False

        # Both requests returned the same event
        assert event1.id == event2.id

        # Only one event exists
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
        # Clean up usage events
        db.query(UsageEvent).filter(
            UsageEvent.tenant_id == tenant_id
        ).delete()

        # Clean up subscription
        db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).delete()

        # Clean up tenant
        db.query(Tenant).filter(
            Tenant.id == tenant_id
        ).delete()

        # Clean up plan
        db.query(Plan).filter(
            Plan.id == plan_id
        ).delete()

        db.commit()
        db.close()