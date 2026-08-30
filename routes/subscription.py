from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.subscription import Subscription
from db.database import get_db
from services.billing import BillingService

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)


@router.post("/")
def create_subscription(
    tenant_id: UUID,
    plan_id: str,
    db: Session = Depends(get_db),
):
    billing = BillingService(db)

    try:
        subscription = billing.create_subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
        )

        return {
            "id": str(subscription.id),
            "tenant_id": str(subscription.tenant_id),
            "plan_id": subscription.plan_id,
            "status": subscription.status,
            "current_period_start": (
                subscription.current_period_start.isoformat()
            ),
            "current_period_end": (
                subscription.current_period_end.isoformat()
            ),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
@router.get("/{tenant_id}")
def get_subscription(
    tenant_id: UUID,
    db: Session = Depends(get_db),
):
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        )
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found",
        )

    return {
        "id": str(subscription.id),
        "tenant_id": str(subscription.tenant_id),
        "plan_id": subscription.plan_id,
        "status": subscription.status,
        "current_period_start": (
            subscription.current_period_start.isoformat()
        ),
        "current_period_end": (
            subscription.current_period_end.isoformat()
        ),
    }