import uuid

from services.billing import BillingService
from models.tenant import Tenant
from models.plan import Plan
from models.subscription import Subscription

from db.database import SessionLocal


def test_create_pro_subscription():
    db = SessionLocal()

    tenant_id = uuid.uuid4()

    try:
        # Create a test tenant
        tenant = Tenant(
            id=tenant_id,
            name="Subscription Test Tenant",
            plan_id="pro",
            api_key_hash="subscription-test-key",
        )

        db.add(tenant)

        # Create Pro plan if it doesn't already exist
        plan = db.query(Plan).filter(Plan.id == "pro").first()

        if plan is None:
            plan = Plan(
                id="pro",
                name="Pro",
                api_call_quota=10000,
                ai_token_quota=1000000,
                price_cents=49900,
            )

            db.add(plan)

        db.commit()

        # Create subscription
        billing = BillingService(db)

        subscription = billing.create_subscription(
            tenant_id=tenant_id,
            plan_id="pro",
        )

        # Verify
        assert subscription is not None
        assert subscription.tenant_id == tenant_id
        assert subscription.plan_id == "pro"
        assert subscription.status == "active"

        assert subscription.current_period_start is not None
        assert subscription.current_period_end is not None

        assert (
            subscription.current_period_end
            > subscription.current_period_start
        )

    finally:
        # Cleanup subscription
        db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).delete()

        # Cleanup tenant
        db.query(Tenant).filter(
            Tenant.id == tenant_id
        ).delete()

        db.commit()
        db.close()