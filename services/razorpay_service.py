import razorpay

from core.config import settings


class RazorpayService:

    def __init__(self):
        self.client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

    def create_plan(
        self,
        name: str,
        amount_cents: int,
        period: str = "monthly",
        interval: int = 1,
    ):
        data = {
            "period": period,
            "interval": interval,
            "item": {
                "name": name,
                "amount": amount_cents,
                "currency": "INR",
                "description": f"{name} subscription plan",
            },
        }

        return self.client.plan.create(data=data)

    def create_subscription(
        self,
        razorpay_plan_id: str,
        total_count: int = 12,
        quantity: int = 1,
        customer_notify: bool = True,
    ):
        data = {
            "plan_id": razorpay_plan_id,
            "total_count": total_count,
            "quantity": quantity,
            "customer_notify": customer_notify,
        }

        return self.client.subscription.create(data=data)