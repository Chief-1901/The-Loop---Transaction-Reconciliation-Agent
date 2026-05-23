from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest
from pydantic import BaseModel

from recon_agent.llm.providers import gemini_call, openai_call, LLMError, RawLLMResponse


class _Schema(BaseModel):
    x: int


# ---------------------------------------------------------------------------
# openai_call — error mapping tests
# ---------------------------------------------------------------------------

def test_openai_rate_limit_maps_to_LLMError(monkeypatch):
    from openai import RateLimitError

    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RateLimitError(
        "429",
        response=MagicMock(status_code=429, request=MagicMock()),
        body=None,
    )

    # OpenAI is imported locally inside openai_call, patch at the openai module level
    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(LLMError) as exc_info:
            openai_call("gpt-4o-mini", [{"role": "user", "content": "hi"}], _Schema)
        assert exc_info.value.code == "LLM_RATE_LIMIT"
        assert exc_info.value.retriable is True


def test_openai_timeout_maps_to_LLMError(monkeypatch):
    from openai import APITimeoutError

    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = APITimeoutError(
        request=MagicMock()
    )

    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(LLMError) as exc_info:
            openai_call("gpt-4o-mini", [{"role": "user", "content": "hi"}], _Schema)
        assert exc_info.value.code == "LLM_TIMEOUT"
        assert exc_info.value.retriable is True


def test_openai_generic_error_maps_to_LLMError(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("something broke")

    with patch("openai.OpenAI", return_value=fake_client):
        with pytest.raises(LLMError) as exc_info:
            openai_call("gpt-4o-mini", [{"role": "user", "content": "hi"}], _Schema)
        assert exc_info.value.code == "LLM_PROVIDER_ERROR"
        assert exc_info.value.retriable is False


def test_openai_success_returns_RawLLMResponse(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    fake_message = MagicMock()
    fake_message.content = '{"x": 42}'

    fake_usage = MagicMock()
    fake_usage.prompt_tokens = 10
    fake_usage.completion_tokens = 5

    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=fake_message)]
    fake_resp.usage = fake_usage

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    with patch("openai.OpenAI", return_value=fake_client):
        result = openai_call("gpt-4o-mini", [{"role": "user", "content": "hi"}], _Schema)

    assert isinstance(result, RawLLMResponse)
    assert result.text == '{"x": 42}'
    assert result.tokens_in == 10
    assert result.tokens_out == 5
    assert result.latency_ms >= 0


# ---------------------------------------------------------------------------
# gemini_call — error mapping tests
# (google.genai is imported locally inside gemini_call, so we patch at the
#  google.genai module level rather than recon_agent.llm.providers.genai)
# ---------------------------------------------------------------------------

def _make_gemini_patches(fake_client):
    """Return a list of patch context managers for google.genai internals."""
    return [
        patch("google.genai.Client", return_value=fake_client),
    ]


def test_gemini_rate_limit_maps_to_LLMError(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = Exception("429 rate limit exceeded")

    with patch("google.genai.Client", return_value=fake_client):
        with pytest.raises(LLMError) as exc_info:
            gemini_call("gemini-2.5-flash", [{"role": "user", "content": "hi"}], _Schema)
        assert exc_info.value.code == "LLM_RATE_LIMIT"
        assert exc_info.value.retriable is True


def test_gemini_timeout_maps_to_LLMError(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = Exception("Request timeout occurred")

    with patch("google.genai.Client", return_value=fake_client):
        with pytest.raises(LLMError) as exc_info:
            gemini_call("gemini-2.5-flash", [{"role": "user", "content": "hi"}], _Schema)
        assert exc_info.value.code == "LLM_TIMEOUT"
        assert exc_info.value.retriable is True


def test_gemini_generic_error_maps_to_LLMError(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = Exception("unknown failure")

    with patch("google.genai.Client", return_value=fake_client):
        with pytest.raises(LLMError) as exc_info:
            gemini_call("gemini-2.5-flash", [{"role": "user", "content": "hi"}], _Schema)
        assert exc_info.value.code == "LLM_PROVIDER_ERROR"
        assert exc_info.value.retriable is False


def test_gemini_success_returns_RawLLMResponse(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    fake_usage = MagicMock()
    fake_usage.prompt_token_count = 15
    fake_usage.candidates_token_count = 8

    fake_resp = MagicMock()
    fake_resp.text = '{"x": 7}'
    fake_resp.usage_metadata = fake_usage

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_resp

    with patch("google.genai.Client", return_value=fake_client):
        result = gemini_call("gemini-2.5-flash", [{"role": "user", "content": "hi"}], _Schema)

    assert isinstance(result, RawLLMResponse)
    assert result.text == '{"x": 7}'
    assert result.tokens_in == 15
    assert result.tokens_out == 8
    assert result.latency_ms >= 0
