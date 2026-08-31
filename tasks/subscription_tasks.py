from celery_app import celery_app
from db.database import SessionLocal
from models.subscription import Subscription
from services.billing import BillingService
from sqlalchemy import func

@celery_app.task
def renew_expired_subscriptions():
    db = SessionLocal()

    try:
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status == "active",
                Subscription.current_period_end <= func.now(),
            )
            .all()
        )

        billing = BillingService(db)

        renewed_count = 0

        for subscription in subscriptions:
            try:
                billing.renew_subscription(
                    tenant_id=subscription.tenant_id
                )
                renewed_count += 1

            except ValueError as exc:
                print(
                    f"Failed to renew "
                    f"{subscription.id}: {exc}"
                )

        return {
            "renewed": renewed_count
        }

    finally:
        db.close()