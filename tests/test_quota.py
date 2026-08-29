import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
import pytest

from db.database import SessionLocal
from models.plan import Plan
from models.tenant import Tenant
from models.subscription import Subscription
from models.usage_event import UsageEvent
from services.metering import MeterService


def test_api_call_quota_boundary():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"quota-test-{uuid.uuid4()}"

    try:
        # Create a test plan with a 1000 API-call quota
        plan = Plan(
            id=plan_id,
            name="Quota Test Plan",
            api_call_quota=1000,
            ai_token_quota=100000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Quota Test Tenant",
            plan_id=plan_id,
            api_key_hash="quota-test-key",
        )

        db.add(tenant)
        db.commit()

        # Create active subscription
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

        # Add 999 existing API calls
        existing_event = UsageEvent(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=999,
            idempotency_key="quota-existing-999",
        )

        db.add(existing_event)
        db.commit()

        meter = MeterService(db)

        # 999 + 1 = 1000 → should be allowed

        event, created = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=1,
            idempotency_key="quota-test-1000",
        )

        assert created is True
        assert event.quantity == 1

        # 1000 + 1 = 1001 → should be rejected

        with pytest.raises(ValueError, match="Usage quota exceeded"):
            meter.record(
                tenant_id=tenant_id,
                metric_name="api_call",
                quantity=1,
                idempotency_key="quota-test-1001",
            )
        # Verify total usage is exactly 1000

        total_usage = (
          db.query(func.sum(UsageEvent.quantity))
          .filter(
           UsageEvent.tenant_id == tenant_id,
           UsageEvent.metric_name == "api_call",
        )
    .scalar()
)
        assert total_usage == 1000

    finally:
        db.query(UsageEvent).filter(
            UsageEvent.tenant_id == tenant_id
        ).delete()

        db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).delete()

        db.query(Tenant).filter(
            Tenant.id == tenant_id
        ).delete()

        db.query(Plan).filter(
            Plan.id == plan_id
        ).delete()

        db.commit()
        db.close()