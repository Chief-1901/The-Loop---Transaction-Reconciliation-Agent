from recon_agent.llm.pricing import cost_inr, PRICING, USD_TO_INR


def test_pricing_table_has_models():
    assert "gemini-2.5-pro" in PRICING
    assert "gpt-4o-mini" in PRICING


def test_cost_inr_basic():
    # gemini-2.5-pro: $1.25/M in, $5/M out
    # 1000 in + 500 out = 0.00125*1 + 0.005*0.5 = 0.00125 + 0.0025 = 0.00375 USD
    # × 83 INR = 0.31125 INR
    cost = cost_inr("gemini-2.5-pro", 1000, 500)
    assert abs(cost - 0.31125) < 0.01


def test_cost_inr_zero():
    assert cost_inr("gemini-2.5-pro", 0, 0) == 0.0


def test_cost_inr_unknown_model_raises():
    import pytest
    with pytest.raises(KeyError):
        cost_inr("gpt-99", 100, 100)
