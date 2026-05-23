from __future__ import annotations
import os
import time
from typing import Any

from pydantic import BaseModel


def sanitize_schema_for_gemini(schema: dict | list | object) -> dict | list | object:
    """Recursively remove keys that Gemini Developer API rejects from a JSON schema.

    Gemini Developer API does not support: additionalProperties, title in nested
    positions, $defs/$ref. We strip these so Pydantic-derived schemas are accepted.
    """
    if isinstance(schema, dict):
        cleaned = {}
        for k, v in schema.items():
            if k in ("additionalProperties", "title"):
                continue
            cleaned[k] = sanitize_schema_for_gemini(v)
        return cleaned
    if isinstance(schema, list):
        return [sanitize_schema_for_gemini(item) for item in schema]
    return schema


class RawLLMResponse(BaseModel):
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


class LLMError(Exception):
    """Provider call failed. Caller classifies kind via `code` and HTTP status."""
    def __init__(self, code: str, message: str, retriable: bool):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retriable = retriable


def gemini_call(
    model: str,
    messages: list[dict],
    response_schema: type[BaseModel],
    timeout_s: float = 30.0,
) -> RawLLMResponse:
    """Hits Gemini's generateContent endpoint with structured-output mode."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    started = time.time()

    # Concatenate messages into a single content (Gemini's simpler API surface).
    content = "\n\n".join(
        f"[{m.get('role', 'user').upper()}] {m['content']}"
        for m in messages
    )

    schema_dict = sanitize_schema_for_gemini(response_schema.model_json_schema())

    try:
        resp = client.models.generate_content(
            model=model,
            contents=content,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema_dict,
                max_output_tokens=2048,
                temperature=0.2,
            ),
        )
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate limit" in msg.lower():
            raise LLMError("LLM_RATE_LIMIT", msg, retriable=True) from e
        if "timeout" in msg.lower():
            raise LLMError("LLM_TIMEOUT", msg, retriable=True) from e
        raise LLMError("LLM_PROVIDER_ERROR", msg, retriable=False) from e

    latency_ms = int((time.time() - started) * 1000)
    usage = resp.usage_metadata
    return RawLLMResponse(
        text=resp.text,
        tokens_in=usage.prompt_token_count,
        tokens_out=usage.candidates_token_count,
        latency_ms=latency_ms,
    )


def openai_call(
    model: str,
    messages: list[dict],
    response_schema: type[BaseModel],
    timeout_s: float = 30.0,
) -> RawLLMResponse:
    """Hits OpenAI chat.completions with strict json_schema."""
    from openai import OpenAI, APITimeoutError, RateLimitError

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=timeout_s)
    started = time.time()

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": response_schema.model_json_schema(),
                    "strict": True,
                },
            },
            max_tokens=2048,
            temperature=0.2,
        )
    except RateLimitError as e:
        raise LLMError("LLM_RATE_LIMIT", str(e), retriable=True) from e
    except APITimeoutError as e:
        raise LLMError("LLM_TIMEOUT", str(e), retriable=True) from e
    except Exception as e:
        raise LLMError("LLM_PROVIDER_ERROR", str(e), retriable=False) from e

    latency_ms = int((time.time() - started) * 1000)
    choice = resp.choices[0].message
    usage = resp.usage
    return RawLLMResponse(
        text=choice.content or "",
        tokens_in=usage.prompt_tokens,
        tokens_out=usage.completion_tokens,
        latency_ms=latency_ms,
    )
