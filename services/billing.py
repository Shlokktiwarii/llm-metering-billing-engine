from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.subscription import Subscription
from models.usage_event import UsageEvent


class BillingService:

    def __init__(self, db: Session):
        self.db = db

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