import uuid
from datetime import datetime, timedelta, timezone

from db.database import SessionLocal
from models.plan import Plan
from models.tenant import Tenant
from models.subscription import Subscription
from models.usage_event import UsageEvent
from services.billing import BillingService


def test_get_current_usage():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"test-plan-{uuid.uuid4()}"

    try:
        # Create plan
        plan = Plan(
            id=plan_id,
            name="Test Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        # Create tenant
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            plan_id=plan_id,
            api_key_hash="test-api-key",
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

        # Add usage events
        db.add_all([
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="api_call",
                quantity=10,
                idempotency_key="billing-test-api-1",
            ),
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="api_call",
                quantity=20,
                idempotency_key="billing-test-api-2",
            ),
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="ai_token",
                token_category="input",
                quantity=500,
                idempotency_key="billing-test-token-1",
            ),
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="ai_token",
                token_category="cached_input",
                quantity=1000,
                idempotency_key="billing-test-token-2",
            ),
        ])

        db.commit()

        # Test BillingService
        billing = BillingService(db)

        usage = billing.get_current_usage(tenant_id)

        # Verify totals
        assert usage["api_calls"] == 30
        assert usage["ai_tokens"] == 1500

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