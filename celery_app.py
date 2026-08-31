from celery import Celery

from core.config import settings


celery_app = Celery(
    "billing_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.subscription_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    beat_schedule={
        "renew-expired-subscriptions": {
            "task": "tasks.subscription_tasks.renew_expired_subscriptions",
            "schedule": 3600.0,
        },
    },
)