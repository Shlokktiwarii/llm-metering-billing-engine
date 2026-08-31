import uuid
from datetime import datetime, timedelta, timezone

import pytest

from db.database import SessionLocal
from models.plan import Plan
from models.subscription import Subscription
from models.tenant import Tenant
from services.billing import BillingService


def test_renew_subscription():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"renew-{tenant_id}"

    try:
        # ---------------------------------------------
        # 1. Create plan
        # ---------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Renewal Test",
            api_call_quota=100,
            ai_token_quota=1000,
            price_cents=0,
        )

        db.add(plan)
        db.flush()

        # ---------------------------------------------
        # 2. Create tenant
        # ---------------------------------------------

        tenant = Tenant(
            id=tenant_id,
            name="Renewal Test Tenant",
            plan_id=plan_id,
            api_key_hash="renewal-test-key",
        )

        db.add(tenant)
        db.flush()

        # ---------------------------------------------
        # 3. Create expired active subscription
        # ---------------------------------------------

        old_start = datetime.now(timezone.utc) - timedelta(days=30)
        old_end = datetime.now(timezone.utc) - timedelta(seconds=1)

        subscription = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_id=plan_id,
            status="active",
            current_period_start=old_start,
            current_period_end=old_end,
        )

        db.add(subscription)
        db.commit()

        old_period_end = subscription.current_period_end

        # ---------------------------------------------
        # 4. Renew
        # ---------------------------------------------

        billing = BillingService(db)

        renewed = billing.renew_subscription(
            tenant_id=tenant_id,
        )

        # ---------------------------------------------
        # 5. Verify
        # ---------------------------------------------

        assert renewed.status == "active"

        assert (
            renewed.current_period_start
            == old_period_end
        )

        assert (
            renewed.current_period_end
            == old_period_end + timedelta(days=30)
        )

    finally:
        db.rollback()

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