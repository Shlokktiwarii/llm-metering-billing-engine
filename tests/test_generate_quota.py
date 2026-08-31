import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func

from core.security import generate_api_key, hash_api_key
from db.database import SessionLocal
from main import app
from models.plan import Plan
from models.subscription import Subscription
from models.tenant import Tenant
from models.usage_event import UsageEvent


client = TestClient(app)


def test_generate_endpoint_quota_boundary():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"quota-endpoint-plan-{uuid.uuid4()}"

    raw_api_key = generate_api_key()

    try:
        # ---------------------------------------------------------
        # Create plan with quota = 1000 API calls
        # ---------------------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Quota Endpoint Test Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        # ---------------------------------------------------------
        # Create tenant
        # ---------------------------------------------------------

        tenant = Tenant(
            id=tenant_id,
            name="Quota Endpoint Test Tenant",
            plan_id=plan_id,
            api_key_hash=hash_api_key(raw_api_key),
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
        # Add 999 existing API calls
        # ---------------------------------------------------------

        db.add(
            UsageEvent(
                tenant_id=tenant_id,
                metric_name="api_call",
                quantity=999,
                idempotency_key=f"quota-existing-{uuid.uuid4()}",
            )
        )

        db.commit()

        # ---------------------------------------------------------
        # Request #1
        #
        # 999 + 1 = 1000
        #
        # Exactly at quota should succeed.
        # ---------------------------------------------------------

        boundary_key = f"quota-boundary-{uuid.uuid4()}"

        response = client.post(
            "/generate/",
            params={
                "quantity": 1,
            },
            headers={
                "X-API-Key": raw_api_key,
                "Idempotency-Key": boundary_key,
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["quantity"] == 1
        assert data["idempotent"] is False

        # ---------------------------------------------------------
        # Request #2
        #
        # 1000 + 1 = 1001
        #
        # This should be rejected.
        # ---------------------------------------------------------

        exceeded_key = f"quota-exceeded-{uuid.uuid4()}"

        response = client.post(
            "/generate/",
            params={
                "quantity": 1,
            },
            headers={
                "X-API-Key": raw_api_key,
                "Idempotency-Key": exceeded_key,
            },
        )

        assert response.status_code == 429

        assert response.json()["detail"] == (
            "API call quota exceeded"
        )

        # ---------------------------------------------------------
        # Verify total usage is exactly 1000
        # ---------------------------------------------------------

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