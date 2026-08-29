from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from services.metering import MeterService

router = APIRouter(
    prefix="/generate",
    tags=["Metering"],
)


@router.post("/")
def generate(
    tenant_id: UUID,
    quantity: int = 1,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero",
        )

    meter = MeterService(db)

    try:
        event, created = meter.record(
            tenant_id=tenant_id,
            metric_name="api_call",
            quantity=quantity,
            idempotency_key=idempotency_key,
        )

    except ValueError as exc:
        message = str(exc)

        if message == "Usage quota exceeded":
            raise HTTPException(
                status_code=429,
                detail="API call quota exceeded",
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )

    return {
        "event_id": str(event.id),
        "tenant_id": str(event.tenant_id),
        "metric_name": event.metric_name,
        "quantity": event.quantity,
        "idempotent": not created,
    }