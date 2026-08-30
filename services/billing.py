import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.plan import Plan
from models.subscription import Subscription
from models.tenant import Tenant
from models.usage_event import UsageEvent


class BillingService:

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------
    # CURRENT USAGE
    # ---------------------------------------------------------

    def get_current_usage(self, tenant_id: UUID) -> dict:

        subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            )
            .first()
        )

        if subscription is None:
            raise ValueError("No active subscription found")

        api_calls = (
            self.db.query(
                func.coalesce(func.sum(UsageEvent.quantity), 0)
            )
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.metric_name == "api_call",
                UsageEvent.created_at
                >= subscription.current_period_start,
                UsageEvent.created_at
                < subscription.current_period_end,
            )
            .scalar()
        )

        ai_tokens = (
            self.db.query(
                func.coalesce(func.sum(UsageEvent.quantity), 0)
            )
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.metric_name == "ai_token",
                UsageEvent.created_at
                >= subscription.current_period_start,
                UsageEvent.created_at
                < subscription.current_period_end,
            )
            .scalar()
        )

        return {
            "api_calls": api_calls,
            "ai_tokens": ai_tokens,
        }

    # ---------------------------------------------------------
    # CREATE SUBSCRIPTION
    # ---------------------------------------------------------

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
            raise ValueError(
                "Tenant already has an active subscription"
            )

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

    # ---------------------------------------------------------
    # CHANGE SUBSCRIPTION PLAN
    # ---------------------------------------------------------

    def change_subscription_plan(
        self,
        tenant_id: UUID,
        new_plan_id: str,
    ) -> Subscription:

        subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            )
            .first()
        )

        if subscription is None:
            raise ValueError("No active subscription found")

        new_plan = (
            self.db.query(Plan)
            .filter(Plan.id == new_plan_id)
            .first()
        )

        if new_plan is None:
            raise ValueError("Plan not found")

        if subscription.plan_id == new_plan_id:
            raise ValueError(
                "Tenant is already subscribed to this plan"
            )
        
        subscription.plan_id = new_plan_id
        subscription.updated_at = datetime.now(timezone.utc)

    def cancel_subscription(
       self,
       tenant_id: UUID,
       ) -> Subscription:

        subscription = (
        self.db.query(Subscription)
        .filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        )
        .first()
        )

        if subscription is None:
          raise ValueError("No active subscription found")

        subscription.status = "cancelled"
        subscription.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(subscription)

        return subscription