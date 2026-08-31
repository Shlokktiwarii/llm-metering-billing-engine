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


def test_tenant_isolation():
    db = SessionLocal()

    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    plan_a_id = f"isolation-plan-a-{uuid.uuid4()}"
    plan_b_id = f"isolation-plan-b-{uuid.uuid4()}"

    api_key_a = generate_api_key()
    api_key_b = generate_api_key()

    try:
        # ---------------------------------------------------------
        # Create plans
        # ---------------------------------------------------------

        plan_a = Plan(
            id=plan_a_id,
            name="Tenant A Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        plan_b = Plan(
            id=plan_b_id,
            name="Tenant B Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        db.add_all([plan_a, plan_b])
        db.commit()

        # ---------------------------------------------------------
        # Create tenants
        # ---------------------------------------------------------

        tenant_a = Tenant(
            id=tenant_a_id,
            name="Tenant A",
            plan_id=plan_a_id,
            api_key_hash=hash_api_key(api_key_a),
        )

        tenant_b = Tenant(
            id=tenant_b_id,
            name="Tenant B",
            plan_id=plan_b_id,
            api_key_hash=hash_api_key(api_key_b),
        )

        db.add_all([tenant_a, tenant_b])
        db.commit()

        # ---------------------------------------------------------
        # Create active subscriptions
        # ---------------------------------------------------------

        now = datetime.now(timezone.utc)

        subscription_a = Subscription(
            tenant_id=tenant_a_id,
            plan_id=plan_a_id,
            status="active",
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),
        )

        subscription_b = Subscription(
            tenant_id=tenant_b_id,
            plan_id=plan_b_id,
            status="active",
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),
        )

        db.add_all([subscription_a, subscription_b])
        db.commit()

        # ---------------------------------------------------------
        # Tenant A makes an API call
        # ---------------------------------------------------------

        response_a = client.post(
            "/generate/",
            params={"quantity": 5},
            headers={
                "X-API-Key": api_key_a,
                "Idempotency-Key": f"tenant-a-{uuid.uuid4()}",
            },
        )

        assert response_a.status_code == 200

        data_a = response_a.json()

        assert data_a["tenant_id"] == str(tenant_a_id)

        # ---------------------------------------------------------
        # Tenant B makes an API call
        # ---------------------------------------------------------

        response_b = client.post(
            "/generate/",
            params={"quantity": 10},
            headers={
                "X-API-Key": api_key_b,
                "Idempotency-Key": f"tenant-b-{uuid.uuid4()}",
            },
        )

        assert response_b.status_code == 200

        data_b = response_b.json()

        assert data_b["tenant_id"] == str(tenant_b_id)

        # ---------------------------------------------------------
        # Verify Tenant A has only its own usage
        # ---------------------------------------------------------

        usage_a = (
            db.query(func.sum(UsageEvent.quantity))
            .filter(
                UsageEvent.tenant_id == tenant_a_id,
                UsageEvent.metric_name == "api_call",
            )
            .scalar()
        )

        assert usage_a == 5

        # ---------------------------------------------------------
        # Verify Tenant B has only its own usage
        # ---------------------------------------------------------

        usage_b = (
            db.query(func.sum(UsageEvent.quantity))
            .filter(
                UsageEvent.tenant_id == tenant_b_id,
                UsageEvent.metric_name == "api_call",
            )
            .scalar()
        )

        assert usage_b == 10

        # ---------------------------------------------------------
        # Tenant A can only see Tenant A's usage
        # ---------------------------------------------------------

        usage_response_a = client.get(
            "/usage/",
            headers={
                "X-API-Key": api_key_a,
            },
        )

        assert usage_response_a.status_code == 200

        usage_data_a = usage_response_a.json()

        assert usage_data_a["tenant_id"] == str(tenant_a_id)
        assert usage_data_a["api_calls"]["used"] == 5

        # ---------------------------------------------------------
        # Tenant B can only see Tenant B's usage
        # ---------------------------------------------------------

        usage_response_b = client.get(
            "/usage/",
            headers={
                "X-API-Key": api_key_b,
            },
        )

        assert usage_response_b.status_code == 200

        usage_data_b = usage_response_b.json()

        assert usage_data_b["tenant_id"] == str(tenant_b_id)
        assert usage_data_b["api_calls"]["used"] == 10

    finally:
        # ---------------------------------------------------------
        # Cleanup
        # ---------------------------------------------------------

        db.query(UsageEvent).filter(
            UsageEvent.tenant_id.in_(
                [tenant_a_id, tenant_b_id]
            )
        ).delete(synchronize_session=False)

        db.query(Subscription).filter(
            Subscription.tenant_id.in_(
                [tenant_a_id, tenant_b_id]
            )
        ).delete(synchronize_session=False)

        db.query(Tenant).filter(
            Tenant.id.in_(
                [tenant_a_id, tenant_b_id]
            )
        ).delete(synchronize_session=False)

        db.query(Plan).filter(
            Plan.id.in_(
                [plan_a_id, plan_b_id]
            )
        ).delete(synchronize_session=False)

        db.commit()
        db.close()