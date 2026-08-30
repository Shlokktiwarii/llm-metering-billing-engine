from services.razorpay_service import RazorpayService


def test_razorpay_connection():
    razorpay = RazorpayService()

    try:
        result = razorpay.create_plan(
            name="Test Plan",
            amount_cents=10000,
        )

        print("\nRAZORPAY RESPONSE:")
        print(result)

        assert result["id"].startswith("plan_")

    except Exception as e:
        print("\nRAZORPAY ERROR:")
        print(type(e))
        print(e)

        