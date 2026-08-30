import uuid
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.subscription import Subscription
from models.tenant import Tenant
from models.usage_event import UsageEvent
from services.pricing import PricingService
from models.plan import Plan

class BillingService:

    def __init__(self, db: Session):
        self.db = db

    def create_subscription(
        self,
        tenant_id: UUID,
        plan_id: str,
    ) -> Subscription:

        tenant = (
            self.db.query(Tenant)
            .filter(Tenant.id == tenant_id)
            .first()
        )

        if tenant is None:
            raise ValueError("Tenant not found")

        plan = (
            self.db.query(Plan)
            .filter(Plan.id == plan_id)
            .first()
        )

        if plan is None:
            raise ValueError("Plan not found")

        existing_subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            )
            .first()
        )

        if existing_subscription is not None:
            raise ValueError("Tenant already has an active subscription")

        now = datetime.now(timezone.utc)

        subscription = Subscription(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )

        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)

        return subscription