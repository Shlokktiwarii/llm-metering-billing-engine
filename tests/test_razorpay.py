import requests

from core.config import settings


def test_razorpay_auth():
    response = requests.get(
        "https://api.razorpay.com/v1/payments?count=1",
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        ),
    )

    print("\nSTATUS:", response.status_code)
    print("RESPONSE:", response.text)

    assert response.status_code == 200
        