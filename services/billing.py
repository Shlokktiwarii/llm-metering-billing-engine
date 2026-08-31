import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session
from services.pricing import PricingService

from models import subscription
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

    # ---------------------------------------------------------
    # API CALL USAGE
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # AI TOKEN USAGE BY CATEGORY
    # ---------------------------------------------------------

      token_rows = (
        self.db.query(
            UsageEvent.token_category,
            func.coalesce(
                func.sum(UsageEvent.quantity),
                0,
            ),
        )
        .filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.metric_name == "ai_token",
            UsageEvent.created_at
            >= subscription.current_period_start,
            UsageEvent.created_at
            < subscription.current_period_end,
        )
        .group_by(UsageEvent.token_category)
        .all()
    )

      token_usage = {
        "input": 0,
        "cached_input": 0,
        "output": 0,
        "reasoning": 0,
    }

      for category, quantity in token_rows:
        if category in token_usage:
            token_usage[category] = quantity

    # ---------------------------------------------------------
    # AI TOKEN COST
    # ---------------------------------------------------------

      ai_token_cost = PricingService.calculate_ai_cost(
        input_tokens=token_usage["input"],
        cached_input_tokens=token_usage["cached_input"],
        output_tokens=token_usage["output"],
        reasoning_tokens=token_usage["reasoning"],
    )

      ai_tokens = sum(token_usage.values())

      return {
        "api_calls": api_calls,
        "ai_tokens": ai_tokens,
        "ai_token_cost": ai_token_cost,
        "token_breakdown": token_usage,
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
        self.db.commit()
        self.db.refresh(subscription)

        return subscription

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

    def get_billing_summary(self, tenant_id: UUID) -> dict:

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

       plan = subscription.plan

       usage = self.get_current_usage(tenant_id)

       api_used = usage["api_calls"]
       ai_used = usage["ai_tokens"]
       ai_cost = usage["ai_token_cost"]

       return {
           "tenant_id": str(tenant_id),
           "plan": {
               "id": plan.id,
               "name": plan.name,
           },
           "subscription": {
               "status": subscription.status,
               "current_period_start": (
                   subscription.current_period_start.isoformat()
               ),
               "current_period_end": (
                   subscription.current_period_end.isoformat()
               ),
           },
           "usage": {
               "api_calls": {
                   "used": api_used,
                   "quota": plan.api_call_quota,
                   "remaining": max(
                       plan.api_call_quota - api_used,
                       0,
                   ),
               },
               "ai_tokens": {
                   "used": ai_used,
                   "quota": plan.ai_token_quota,
                   "remaining": max(
                       plan.ai_token_quota - ai_used,
                       0,
                   ),
                   "cost": ai_cost,
                   "breakdown": usage["token_breakdown"],
                },
           },
       }
    def renew_subscription(
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

       now = datetime.now(timezone.utc)

    # Make sure the subscription has a valid billing period
       if (
          subscription.current_period_start is None
          or subscription.current_period_end is None
        ):
          raise ValueError("Subscription has no billing period")

    # Renewal should only happen after the current period ends
       if now < subscription.current_period_end:
         raise ValueError("Subscription period has not ended")

    # Move the period forward by 30 days
       old_period_end = subscription.current_period_end

       subscription.current_period_start = old_period_end
       subscription.current_period_end = (
        old_period_end + timedelta(days=30)
      )

       subscription.updated_at = now

       self.db.commit()
       self.db.refresh(subscription)

       return subscription