from services.pricing import PricingService


def test_input_token_cost():
    cost = PricingService.calculate_ai_cost(
        input_tokens=1000,
    )

    assert cost == 1000


def test_cached_input_token_cost():
    cost = PricingService.calculate_ai_cost(
        cached_input_tokens=1000,
    )

    assert cost == 0


def test_output_token_cost():
    cost = PricingService.calculate_ai_cost(
        output_tokens=1000,
    )

    assert cost == 2000


def test_reasoning_tokens_use_output_price():
    cost = PricingService.calculate_ai_cost(
        reasoning_tokens=1000,
    )

    assert cost == 2000


def test_combined_token_cost():
    cost = PricingService.calculate_ai_cost(
        input_tokens=1000,
        cached_input_tokens=500,
        output_tokens=2000,
        reasoning_tokens=500,
    )

    assert cost == 6000