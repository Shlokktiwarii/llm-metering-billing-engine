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


def test_generate_endpoint_is_idempotent():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"generate-test-plan-{uuid.uuid4()}"

    raw_api_key = generate_api_key()

    try:
        # ---------------------------------------------------------
        # Create plan
        # ---------------------------------------------------------

        plan = Plan(
            id=plan_id,
            name="Generate Test Plan",
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
            name="Generate Test Tenant",
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

        idempotency_key = f"generate-test-{uuid.uuid4()}"

        # ---------------------------------------------------------
        # First request
        # ---------------------------------------------------------

        response_1 = client.post(
            "/generate/",
            params={
                "quantity": 1,
            },
            headers={
                "X-API-Key": raw_api_key,
                "Idempotency-Key": idempotency_key,
            },
        )

        assert response_1.status_code == 200

        data_1 = response_1.json()

        assert data_1["quantity"] == 1
        assert data_1["idempotent"] is False

        first_event_id = data_1["event_id"]

        # ---------------------------------------------------------
        # Second request with SAME idempotency key
        # ---------------------------------------------------------

        response_2 = client.post(
            "/generate/",
            params={
                "quantity": 1,
            },
            headers={
                "X-API-Key": raw_api_key,
                "Idempotency-Key": idempotency_key,
            },
        )

        assert response_2.status_code == 200

        data_2 = response_2.json()

        assert data_2["event_id"] == first_event_id
        assert data_2["idempotent"] is True

        # ---------------------------------------------------------
        # Verify database contains exactly ONE event
        # ---------------------------------------------------------

        event_count = (
            db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
            .count()
        )

        assert event_count == 1

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