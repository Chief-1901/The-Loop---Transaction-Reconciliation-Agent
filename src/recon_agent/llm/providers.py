from __future__ import annotations
import json
import os
import time
from typing import Any

from pydantic import BaseModel


def _dereference_schema(schema: dict, defs: dict) -> dict:
    """Recursively resolve $ref references using $defs."""
    if "$ref" in schema:
        ref = schema["$ref"]
        # e.g. "#/$defs/CorrectionProposal" -> "CorrectionProposal"
        name = ref.split("/")[-1]
        if name in defs:
            resolved = dict(defs[name])
            # Merge any other keys from original schema
            for k, v in schema.items():
                if k != "$ref":
                    resolved[k] = v
            return _dereference_schema(resolved, defs)
    result = {}
    for k, v in schema.items():
        if k == "$defs":
            continue  # strip defs from output
        if isinstance(v, dict):
            result[k] = _dereference_schema(v, defs)
        elif isinstance(v, list):
            result[k] = [_dereference_schema(i, defs) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def sanitize_schema_for_openai(schema: dict | list | object) -> dict | list | object:
    """Recursively prepare a JSON schema for OpenAI strict mode.

    OpenAI strict mode requires:
    - additionalProperties: false on all object types
    - required: list must include every key in properties
    - All object schemas must have a 'properties' key (even if empty {})
    - No $ref/$defs (must be dereferenced inline)
    - No 'default' values (they conflict with required)
    - No 'title' keys
    """
    # First dereference any $ref/$defs in the top-level schema
    if isinstance(schema, dict) and "$defs" in schema:
        defs = schema.get("$defs", {})
        schema = _dereference_schema(schema, defs)

    def _sanitize(s: Any) -> Any:
        if isinstance(s, dict):
            cleaned = {k: _sanitize(v) for k, v in s.items()
                       if k not in ("default", "title", "additionalProperties", "$defs", "$ref")}
            if cleaned.get("type") == "object" or "properties" in cleaned:
                cleaned["additionalProperties"] = False
                if "properties" not in cleaned:
                    cleaned["properties"] = {}
                cleaned["required"] = sorted(cleaned["properties"].keys())
            # Fix anyOf with bare {} (any type) — simplify to just string/null for OpenAI
            if "anyOf" in cleaned:
                any_of = cleaned["anyOf"]
                # If one option is {} (unrestricted), replace whole anyOf with string or null
                if any(v == {} for v in any_of):
                    non_null = [v for v in any_of if v != {} and v != {"type": "null"}]
                    null_opt = [{"type": "null"}] if any(v == {"type": "null"} for v in any_of) else []
                    if non_null:
                        cleaned["anyOf"] = non_null + null_opt
                    else:
                        cleaned = {"type": "string"}  # fallback
            return cleaned
        if isinstance(s, list):
            return [_sanitize(item) for item in s]
        return s

    return _sanitize(schema)


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
                max_output_tokens=8192,
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

    strict_schema = sanitize_schema_for_openai(response_schema.model_json_schema())

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": strict_schema,
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


def openrouter_call(
    model: str,
    messages: list[dict],
    response_schema: type[BaseModel],
    timeout_s: float = 30.0,
) -> RawLLMResponse:
    """Hits OpenRouter's OpenAI-compatible endpoint. Uses JSON-mode + schema hint."""
    from openai import OpenAI, APITimeoutError, RateLimitError

    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        timeout=timeout_s,
    )
    started = time.time()

    # Inject the schema as a hint in the first system message (or prepend a new one)
    schema_str = json.dumps(response_schema.model_json_schema(), indent=2)
    schema_hint = (
        "Respond with a single JSON object matching this schema EXACTLY. "
        "No prose, no markdown fences. JSON only.\n\nSchema:\n" + schema_str
    )
    augmented = list(messages)
    if augmented and augmented[0].get("role") == "system":
        augmented[0] = {**augmented[0], "content": augmented[0]["content"] + "\n\n" + schema_hint}
    else:
        augmented.insert(0, {"role": "system", "content": schema_hint})

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=augmented,
            response_format={"type": "json_object"},
            max_tokens=4096,
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
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
    )
