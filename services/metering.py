from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.subscription import Subscription
from models.usage_event import UsageEvent


class MeterService:

    def __init__(self, db: Session):
        self.db = db

    def check_quota(
        self,
        tenant_id: UUID,
        metric_name: str,
        quantity: int,
    ) -> bool:

        # Find the tenant's active subscription
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

        # Get the plan attached to the subscription
        plan = subscription.plan

        # Select the correct quota
        if metric_name == "api_call":
            quota = plan.api_call_quota

        elif metric_name == "ai_token":
            quota = plan.ai_token_quota

        else:
            raise ValueError(
                f"Unknown metric name: {metric_name}"
            )

        # Calculate current usage in the current billing period
        current_usage = (
            self.db.query(
                func.coalesce(
                    func.sum(UsageEvent.quantity),
                    0,
                )
            )
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.metric_name == metric_name,
                UsageEvent.created_at
                >= subscription.current_period_start,
                UsageEvent.created_at
                < subscription.current_period_end,
            )
            .scalar()
        )

        # Check whether the new usage would exceed the quota
        if current_usage + quantity > quota:
            return False

        return True

    def record(
        self,
        tenant_id: UUID,
        metric_name: str,
        quantity: int,
        idempotency_key: str,
    ):

        # -------------------------------------------------
        # 1. Check whether this request was already processed
        # -------------------------------------------------

        existing_event = (
            self.db.query(UsageEvent)
            .filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
            .first()
        )

        if existing_event is not None:
            # Retry → return the original event
            return existing_event, False

        # -------------------------------------------------
        # 2. Check quota
        # -------------------------------------------------

        if not self.check_quota(
            tenant_id=tenant_id,
            metric_name=metric_name,
            quantity=quantity,
        ):
            raise ValueError("Usage quota exceeded")

        # -------------------------------------------------
        # 3. Create usage event
        # -------------------------------------------------

        event = UsageEvent(
            tenant_id=tenant_id,
            metric_name=metric_name,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )

        self.db.add(event)

        # -------------------------------------------------
        # 4. Save to database
        # -------------------------------------------------

        try:
            self.db.commit()
            self.db.refresh(event)

            # True = newly created
            return event, True

        except IntegrityError:
            # Another request may have created the same
            # idempotency key at the same time.
            self.db.rollback()

            existing_event = (
                self.db.query(UsageEvent)
                .filter(
                    UsageEvent.tenant_id == tenant_id,
                    UsageEvent.idempotency_key == idempotency_key,
                )
                .first()
            )

            if existing_event is None:
                raise

            # False = duplicate/retry
            return existing_event, False