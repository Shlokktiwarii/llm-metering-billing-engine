from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.tenant import Tenant
from core.security import hash_api_key


def get_current_tenant(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
    db: Session = Depends(get_db),
) -> Tenant:

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
        )

    api_key_hash = hash_api_key(x_api_key)

    tenant = (
        db.query(Tenant)
        .filter(
            Tenant.api_key_hash == api_key_hash
        )
        .first()
    )

    if tenant is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return tenant