from __future__ import annotations
from pydantic import BaseModel

USD_TO_INR = 83.0


class ModelPrice(BaseModel):
    input: float    # USD per 1M tokens
    output: float


PRICING: dict[str, ModelPrice] = {
    "gemini-2.5-pro":          ModelPrice(input=1.25,  output=5.00),
    "gemini-2.5-flash":        ModelPrice(input=0.075, output=0.30),
    "gemini-2.5-flash-lite":   ModelPrice(input=0.01,  output=0.04),
    # gemini-3.x models (fallback when 2.5-flash quota exhausted)
    "gemini-3.1-flash-lite":         ModelPrice(input=0.01,  output=0.04),
    "gemini-3.1-flash-lite-preview": ModelPrice(input=0.01,  output=0.04),
    "gpt-4o":                  ModelPrice(input=2.50,  output=10.00),
    "gpt-4o-mini":             ModelPrice(input=0.15,  output=0.60),
    # OpenRouter free models (cost = 0)
    "deepseek/deepseek-chat:free":            ModelPrice(input=0.0, output=0.0),
    "deepseek/deepseek-r1:free":              ModelPrice(input=0.0, output=0.0),
    "openai/gpt-oss-120b:free":               ModelPrice(input=0.0, output=0.0),
    "meta-llama/llama-3.3-70b-instruct:free": ModelPrice(input=0.0, output=0.0),
    "google/gemini-2.0-flash-exp:free":       ModelPrice(input=0.0, output=0.0),
    "qwen/qwen-2.5-72b-instruct:free":        ModelPrice(input=0.0, output=0.0),
}


def cost_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING[model]
    usd = (tokens_in / 1_000_000) * p.input + (tokens_out / 1_000_000) * p.output
    return round(usd * USD_TO_INR, 4)
