from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.subscription import Subscription
from models.usage_event import UsageEvent
from services.pricing import PricingService


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

        # API call usage

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

        # AI token usage

        ai_events = (
            self.db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.metric_name == "ai_token",
                UsageEvent.created_at
                >= subscription.current_period_start,
                UsageEvent.created_at
                < subscription.current_period_end,
            )
            .all()
        )

        input_tokens = 0
        cached_input_tokens = 0
        output_tokens = 0
        reasoning_tokens = 0

        for event in ai_events:

            if event.token_category == "input":
                input_tokens += event.quantity

            elif event.token_category == "cached_input":
                cached_input_tokens += event.quantity

            elif event.token_category == "output":
                output_tokens += event.quantity

            elif event.token_category == "reasoning":
                reasoning_tokens += event.quantity

        # Calculate AI cost

        ai_cost = PricingService.calculate_ai_cost(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )

        return {
            "api_calls": api_calls,
            "ai_tokens": (
                input_tokens
                + cached_input_tokens
                + output_tokens
                + reasoning_tokens
            ),
            "cost_cents": ai_cost,
        }