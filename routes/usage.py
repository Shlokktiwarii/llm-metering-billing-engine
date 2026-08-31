from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from dependencies.auth import get_current_tenant
from models.tenant import Tenant
from models.subscription import Subscription
from services.billing import BillingService


router = APIRouter(
    prefix="/usage",
    tags=["Usage"],
)


@router.get("/")
def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.tenant_id == tenant.id,
            Subscription.status == "active",
        )
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found",
        )

    billing = BillingService(db)

    try:
        usage = billing.get_current_usage(tenant.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    plan = subscription.plan

    return {
        "tenant_id": str(tenant.id),
        "api_calls": {
            "used": usage["api_calls"],
            "limit": plan.api_call_quota,
        },
        "ai_tokens": {
            "used": usage["ai_tokens"],
            "limit": plan.ai_token_quota,
            "cost": usage["ai_token_cost"],
            "breakdown": usage["token_breakdown"],
        },
    }