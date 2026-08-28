from core.prices import AI_TOKEN_PRICES

class PricingService:

    @staticmethod
    def calculate_ai_cost(
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> int:

        input_cost = (
            input_tokens * AI_TOKEN_PRICES["input"]
        )

        cached_input_cost = (
            cached_input_tokens
            * AI_TOKEN_PRICES["cached_input"]
        )

        # Reasoning tokens are billed at the output rate.
        output_cost = (
            (output_tokens + reasoning_tokens)
            * AI_TOKEN_PRICES["output"]
        )

        return input_cost + cached_input_cost + output_cost