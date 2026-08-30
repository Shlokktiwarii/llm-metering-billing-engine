from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.subscription import Subscription
from services.billing import BillingService


router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)


class ChangePlanRequest(BaseModel):
    plan_id: str


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


@router.patch("/{tenant_id}")
def change_subscription_plan(
    tenant_id: UUID,
    request: ChangePlanRequest,
    db: Session = Depends(get_db),
):
    billing = BillingService(db)

    try:
        subscription = billing.change_subscription_plan(
            tenant_id=tenant_id,
            new_plan_id=request.plan_id,
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

@router.delete("/{tenant_id}")
def cancel_subscription(
    tenant_id: UUID,
    db: Session = Depends(get_db),
):
    billing = BillingService(db)

    try:
        subscription = billing.cancel_subscription(tenant_id=tenant_id)

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