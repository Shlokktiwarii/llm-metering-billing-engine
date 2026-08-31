import uuid
from datetime import datetime, timedelta, timezone

from db.database import SessionLocal
from models.plan import Plan
from models.tenant import Tenant
from models.subscription import Subscription
from models.usage_event import UsageEvent
from services.billing import BillingService


def test_ai_token_cost_rollup():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"cost-test-plan-{uuid.uuid4()}"

    try:
        # ---------------------------------------------------------
        # Create plan
        # ---------------------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Cost Test Plan",
            api_call_quota=1000,
            ai_token_quota=100000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        # ---------------------------------------------------------
        # Create tenant
        # ---------------------------------------------------------

        tenant = Tenant(
            id=tenant_id,
            name="Cost Test Tenant",
            plan_id=plan_id,
            api_key_hash="cost-test-api-key",
        )

        db.add(tenant)
        db.commit()

        # ---------------------------------------------------------
        # Create active subscription
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # Create AI token usage
        # ---------------------------------------------------------

        db.add_all([
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="ai_token",
                token_category="input",
                quantity=1000,
                idempotency_key="cost-test-input",
            ),
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="ai_token",
                token_category="cached_input",
                quantity=500,
                idempotency_key="cost-test-cached",
            ),
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="ai_token",
                token_category="output",
                quantity=2000,
                idempotency_key="cost-test-output",
            ),
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="ai_token",
                token_category="reasoning",
                quantity=500,
                idempotency_key="cost-test-reasoning",
            ),
        ])

        db.commit()

        # ---------------------------------------------------------
        # Calculate billing usage
        # ---------------------------------------------------------

        billing = BillingService(db)

        usage = billing.get_current_usage(tenant_id)

        # ---------------------------------------------------------
        # Verify total AI token usage
        # ---------------------------------------------------------

        assert usage["ai_tokens"] == 4000

        # ---------------------------------------------------------
        # Verify cost
        #
        # 1000 input        × 1 = 1000
        # 500 cached input  × 0 =    0
        # 2000 output       × 2 = 4000
        # 500 reasoning     × 2 = 1000
        #
        # Total = 6000
        # ---------------------------------------------------------

        assert usage["ai_token_cost"] == 6000

        # ---------------------------------------------------------
        # Verify token breakdown
        # ---------------------------------------------------------

        assert usage["token_breakdown"] == {
            "input": 1000,
            "cached_input": 500,
            "output": 2000,
            "reasoning": 500,
        }

    finally:
        # ---------------------------------------------------------
        # Cleanup
        # ---------------------------------------------------------

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