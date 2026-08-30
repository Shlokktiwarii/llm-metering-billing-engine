import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from services.metering import MeterService
from models.tenant import Tenant
from models.plan import Plan
from models.subscription import Subscription
from models.usage_event import UsageEvent

from db.database import SessionLocal


def test_idempotency_does_not_consume_quota_twice():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"idempotency-{tenant_id}"

    try:
        # -------------------------------------------------
        # 1. Create test plan
        # -------------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Idempotency Test",
            api_call_quota=10,
            ai_token_quota=100,
            price_cents=0,
        )

        db.add(plan)
        db.flush()

        # -------------------------------------------------
        # 2. Create tenant
        # -------------------------------------------------

        tenant = Tenant(
            id=tenant_id,
            name="Idempotency Test Tenant",
            plan_id=plan_id,
            api_key_hash="idempotency-test-key",
        )

        db.add(tenant)
        db.flush()

        # -------------------------------------------------
        # 3. Create active subscription
        # -------------------------------------------------

        now = datetime.now(timezone.utc)

        subscription = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_id=plan_id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

        db.add(subscription)
        db.commit()

        meter = MeterService(db)

        # -------------------------------------------------
        # 4. First request
        # -------------------------------------------------

        event1, created1 = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=7,
            idempotency_key="same-request",
        )

        assert created1 is True
        assert event1.quantity == 7

        # -------------------------------------------------
        # 5. Retry SAME request
        # -------------------------------------------------

        event2, created2 = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=7,
            idempotency_key="same-request",
        )

        # Should return the original event
        assert created2 is False
        assert event2.id == event1.id

        # -------------------------------------------------
        # 6. Verify quota was not consumed twice
        # -------------------------------------------------

        total_usage = (
            db.query(
                func.coalesce(
                    func.sum(UsageEvent.quantity),
                    0,
                )
            )
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.metric_name == "api_call",
            )
            .scalar()
        )

        assert total_usage == 7

    finally:
        db.rollback()

        db.query(UsageEvent).filter(
            UsageEvent.tenant_id == tenant_id
        ).delete(synchronize_session=False)

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id
            )
            .first()
        )

        if subscription is not None:
            db.delete(subscription)

        tenant = (
            db.query(Tenant)
            .filter(
                Tenant.id == tenant_id
            )
            .first()
        )

        if tenant is not None:
            db.delete(tenant)

        plan = (
            db.query(Plan)
            .filter(
                Plan.id == plan_id
            )
            .first()
        )

        if plan is not None:
            db.delete(plan)

        db.commit()
        db.close()