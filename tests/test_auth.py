import uuid

from core.security import generate_api_key, hash_api_key
from db.database import SessionLocal
from models.plan import Plan
from models.tenant import Tenant


def test_api_key_hash_and_lookup():
    db = SessionLocal()

    tenant_id = uuid.uuid4()
    plan_id = f"auth-test-plan-{uuid.uuid4()}"

    raw_api_key = generate_api_key()

    try:
        # Create plan
        plan = Plan(
            id=plan_id,
            name="Auth Test Plan",
            api_call_quota=1000,
            ai_token_quota=10000,
            price_cents=0,
        )

        db.add(plan)
        db.commit()

        # Store ONLY the hash
        tenant = Tenant(
            id=tenant_id,
            name="Auth Test Tenant",
            plan_id=plan_id,
            api_key_hash=hash_api_key(raw_api_key),
        )

        db.add(tenant)
        db.commit()

        # Look up tenant using hashed API key
        stored_hash = hash_api_key(raw_api_key)

        found_tenant = (
            db.query(Tenant)
            .filter(
                Tenant.api_key_hash == stored_hash
            )
            .first()
        )

        assert found_tenant is not None
        assert found_tenant.id == tenant_id

        # Raw key must not equal stored value
        assert raw_api_key != found_tenant.api_key_hash

    finally:
        db.query(Tenant).filter(
            Tenant.id == tenant_id
        ).delete()

        db.query(Plan).filter(
            Plan.id == plan_id
        ).delete()

        db.commit()
        db.close()