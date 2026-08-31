import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from core.security import generate_api_key, hash_api_key
from db.database import SessionLocal
from main import app
from models.plan import Plan
from models.subscription import Subscription
from models.tenant import Tenant
from models.usage_event import UsageEvent


client = TestClient(app)


def test_generate_requires_api_key():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"auth-endpoint-plan-{uuid.uuid4()}"

    raw_api_key = generate_api_key()

    try:
        plan = Plan(
            id=plan_id,
            name="Auth Endpoint Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        tenant = Tenant(
            id=tenant_id,
            name="Auth Endpoint Tenant",
            plan_id=plan_id,
            api_key_hash=hash_api_key(raw_api_key),
        )

        db.add(tenant)
        db.commit()

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

        # Missing API key
        response = client.post(
            "/generate/",
            params={"quantity": 1},
            headers={
                "Idempotency-Key": f"missing-key-{uuid.uuid4()}",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "API key required"

        # Invalid API key
        response = client.post(
            "/generate/",
            params={"quantity": 1},
            headers={
                "X-API-Key": "sk_invalid_key",
                "Idempotency-Key": f"invalid-key-{uuid.uuid4()}",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"

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