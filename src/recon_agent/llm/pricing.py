from __future__ import annotations
from pydantic import BaseModel

USD_TO_INR = 83.0


class ModelPrice(BaseModel):
    input: float    # USD per 1M tokens
    output: float


PRICING: dict[str, ModelPrice] = {
    "gemini-2.5-pro":        ModelPrice(input=1.25,  output=5.00),
    "gemini-2.5-flash":      ModelPrice(input=0.075, output=0.30),
    "gemini-2.5-flash-lite": ModelPrice(input=0.01,  output=0.04),
    "gpt-4o":                ModelPrice(input=2.50,  output=10.00),
    "gpt-4o-mini":           ModelPrice(input=0.15,  output=0.60),
}


def cost_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING[model]
    usd = (tokens_in / 1_000_000) * p.input + (tokens_out / 1_000_000) * p.output
    return round(usd * USD_TO_INR, 4)
