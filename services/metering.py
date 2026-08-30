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

        if metric_name == "api_call":
            quota = plan.api_call_quota

        elif metric_name == "ai_token":
            quota = plan.ai_token_quota

        else:
            raise ValueError(
                f"Unknown metric name: {metric_name}"
            )

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
        # 1. Check idempotency
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
            return existing_event, False

        # -------------------------------------------------
        # 2. Lock the active subscription
        # -------------------------------------------------

        subscription = (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            )
            .with_for_update()
            .first()
        )

        if subscription is None:
            raise ValueError("No active subscription found")

        # -------------------------------------------------
        # 3. Get quota
        # -------------------------------------------------

        plan = subscription.plan

        if metric_name == "api_call":
            quota = plan.api_call_quota

        elif metric_name == "ai_token":
            quota = plan.ai_token_quota

        else:
            raise ValueError(
                f"Unknown metric name: {metric_name}"
            )

        # -------------------------------------------------
        # 4. Calculate current usage
        # -------------------------------------------------

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

        # -------------------------------------------------
        # 5. Atomic quota decision
        # -------------------------------------------------

        if current_usage + quantity > quota:
            raise ValueError("Usage quota exceeded")

        # -------------------------------------------------
        # 6. Create usage event
        # -------------------------------------------------

        event = UsageEvent(
            tenant_id=tenant_id,
            metric_name=metric_name,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )

        self.db.add(event)

        # -------------------------------------------------
        # 7. Commit
        # -------------------------------------------------

        try:
            self.db.commit()
            self.db.refresh(event)

            return event, True

        except IntegrityError:
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

            return existing_event, False