import uuid
from datetime import datetime, timedelta, timezone

import pytest
from models.usage_event import UsageEvent
from services.metering import MeterService
from models.tenant import Tenant
from models.plan import Plan
from models.subscription import Subscription

from db.database import SessionLocal


def test_quota_is_enforced_atomically():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"atomic-{tenant_id}"

    try:
        # -------------------------------------------------
        # 1. Create test plan
        # -------------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Atomic Test",
            api_call_quota=10,
            ai_token_quota=100,
            price_cents=0,
        )

        db.add(plan)
        db.flush()

        # -------------------------------------------------
        # 2. Create test tenant
        # -------------------------------------------------

        tenant = Tenant(
            id=tenant_id,
            name="Atomic Quota Tenant",
            plan_id=plan_id,
            api_key_hash="atomic-test-key",
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

        # -------------------------------------------------
        # 4. Create metering service
        # -------------------------------------------------

        meter = MeterService(db)

        # -------------------------------------------------
        # 5. Record 7 API calls
        #
        # Quota = 10
        # Usage = 7
        # Expected = allowed
        # -------------------------------------------------

        event, created = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=7,
            idempotency_key="atomic-test-1",
        )

        assert created is True
        assert event.quantity == 7
        assert event.metric_name == "api_call"
        assert event.tenant_id == tenant_id

        # -------------------------------------------------
        # 6. Try to record another 5 API calls
        #
        # 7 + 5 = 12
        # Quota = 10
        # Expected = rejected
        # -------------------------------------------------

        with pytest.raises(
            ValueError,
            match="Usage quota exceeded",
        ):
            meter.record(
                tenant_id=tenant_id,
                metric_name="api_call",
                quantity=5,
                idempotency_key="atomic-test-2",
            )

        # -------------------------------------------------
        # 7. Verify only the first event exists
        # -------------------------------------------------

        events = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant_id,
            )
            .all()
        )

        assert len(events) == 1
        assert events[0].quantity == 7

    finally:
        # -------------------------------------------------
        # 8. Cleanup
        # -------------------------------------------------

        db.rollback()

        # Delete usage events first
        db.query(UsageEvent).filter(
            UsageEvent.tenant_id == tenant_id
        ).delete(synchronize_session=False)

        # Delete subscription
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id
            )
            .first()
        )

        if subscription is not None:
            db.delete(subscription)

        # Delete tenant
        tenant = (
            db.query(Tenant)
            .filter(
                Tenant.id == tenant_id
            )
            .first()
        )

        if tenant is not None:
            db.delete(tenant)

        # Delete test plan
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