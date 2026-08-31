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


def test_change_subscription_plan_updates_active_subscription():
    db = SessionLocal()
    tenant_id = uuid.uuid4()
    current_plan_id = f"starter-{uuid.uuid4()}"
    new_plan_id = f"pro-{uuid.uuid4()}"

    try:
        tenant = Tenant(
            id=tenant_id,
            name="Plan Change Tenant",
            plan_id=current_plan_id,
            api_key_hash=f"plan-change-{uuid.uuid4()}",
        )
        db.add(tenant)

        for plan_id, plan_name in [
            (current_plan_id, "Starter"),
            (new_plan_id, "Pro"),
        ]:
            if db.query(Plan).filter(Plan.id == plan_id).first() is None:
                db.add(
                    Plan(
                        id=plan_id,
                        name=plan_name,
                        api_call_quota=1000 if plan_id == current_plan_id else 10000,
                        ai_token_quota=10000 if plan_id == current_plan_id else 1000000,
                        price_cents=0 if plan_id == current_plan_id else 49900,
                    )
                )

        db.commit()

        billing = BillingService(db)
        subscription = billing.create_subscription(
            tenant_id=tenant_id,
            plan_id=current_plan_id,
        )

        updated = billing.change_subscription_plan(
            tenant_id=tenant_id,
            new_plan_id=new_plan_id,
        )

        assert updated is not None
        assert updated.plan_id == new_plan_id
        assert updated.status == "active"

        persisted = (
            db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            )
            .first()
        )
        assert persisted is not None
        assert persisted.plan_id == new_plan_id

    finally:
        db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id
        ).delete(synchronize_session=False)
        db.query(Tenant).filter(
            Tenant.id == tenant_id
        ).delete(synchronize_session=False)
        db.query(Plan).filter(
            Plan.id.in_([current_plan_id, new_plan_id])
        ).delete(synchronize_session=False)
        db.commit()
        db.close()