# Model Routing

| Subtask | Provider | Model | Cost ($/M in, $/M out) | Why this model |
|---------|----------|-------|------------------------|----------------|
| `plan` | OpenRouter | openai/gpt-oss-120b:free | $0 (free tier) | OpenAI's GPT-OSS-120B via OpenRouter free tier. Native structured-output + function-calling. 200 req/day quota is sufficient for cassette recording and demo workloads. Reliable JSON schema compliance avoids the brittle prompt-engineering required by smaller free models. |
| `decide` | OpenRouter | openai/gpt-oss-120b:free | $0 (free tier) | Binary HALT/PLAN meta-decision; same model as plan amortizes the OpenRouter client. |
| `classify` | OpenAI | gpt-4o-mini | $0.15 / $0.60 | High-volume cheap structured JSON via OpenAI's `json_schema strict` mode. Output is a fixed Pydantic enum; minimal reasoning required. |
| `propose` | OpenRouter | openai/gpt-oss-120b:free | $0 (free tier) | Per-correction LLM call; in-family with plan/decide; free tier handles per-discrepancy proposals. |
| `summary` | OpenRouter | openai/gpt-oss-120b:free | $0 (free tier) | One natural-language summary call at end. In-family with plan/decide. |
| `shadow_plan` | OpenAI | gpt-4o | $2.50 / $10.00 | Capable-tier shadow comparison vs gpt-oss-120b on Plan. Only invoked when `--shadow` is set. |

## Why OpenRouter + OpenAI, not Gemini

The initial prototype used Gemini 2.5 Flash Lite for plan/decide/propose. After cassette recording, two issues surfaced:

1. **Quota exhaustion** — Flash Lite's daily free quota (~50-200 req/day depending on AI Studio tier) ran out during the 12-scenario recording sweep (~360 LLM calls total).
2. **Structured-output gaps** — Gemini's json_schema mode occasionally returned malformed JSON for complex nested schemas (e.g., `propose_correction`'s `CorrectionProposal`).

We switched the main plan/decide/propose/summary subtasks to **openai/gpt-oss-120b:free** via OpenRouter, which resolved both issues. GPT-OSS-120B's free tier provides 200 req/day and reliable structured-output via the OpenAI-compatible `/v1/chat/completions` endpoint.

`classify` remains on **gpt-4o-mini** via the direct OpenAI API, where OpenAI's strict `json_schema` enforcement gives the highest-reliability batch enum classification (no retry logic needed).

## Why gpt-oss-120b over other free OpenRouter models

During cassette recording we evaluated several free-tier models on OpenRouter:

| Model | Outcome |
|-------|---------|
| `openai/gpt-oss-120b:free` | ✓ Works — reliable JSON, 200 req/day |
| `openai/gpt-oss-20b:free` | Same JSON issues as 120b (smaller model) |
| `meta-llama/llama-3.3-70b:free` | 429 rate-limit errors on burst workloads |
| `google/gemini-2.0-flash:free` | 404 / model not available on free tier |
| `deepseek/deepseek-chat:free` | API key not valid / 402 payment required |

gpt-oss-120b struck the right balance: adequate structured-output quality, sufficient free quota, OpenAI-compatible API (reuses existing `openrouter_call()` adapter).

## `OPENROUTER_MODEL` env override

Set `OPENROUTER_MODEL=<model-id>` to swap the default at runtime — useful for testing other OpenRouter free models without code changes. The override applies to all OpenRouter-routed subtasks (plan, decide, propose, summary).

## `PLAN_PROVIDER=openai` override

Set `PLAN_PROVIDER=openai` to force the `plan` subtask (ONLY) to use `gpt-4o`. This is the lever the shadow-comparison eval pulls to record "config_b" cassettes. Other subtasks remain on default OpenRouter routes.

## Robustness measures added for free-tier models

Free-tier models on OpenRouter occasionally return empty content or malformed JSON. `providers.py` adds:

- **3-retry loop** in `openrouter_call()` with 0.5s sleep between attempts — catches transient empty-content responses.
- **`_simplify_schema_for_openrouter()`** — strips `anyOf: [{type: null}]` constructs (Pydantic's Optional encoding) before sending the schema; prevents models from outputting `{"type": "null"}` instead of JSON `null`.
- Standard **RateLimitError / APITimeoutError** handling mapped to `LLMError` with `retriable=True`.

## Switching providers entirely

Want to swap OpenRouter for Claude on Plan?

1. Add `claude_call(...)` adapter to `src/recon_agent/llm/providers.py` (~30 LOC)
2. Add pricing entries to `src/recon_agent/llm/pricing.py`
3. Update `ROUTING_TABLE["plan"]` in `router.py`
4. Re-record cassettes: `LLM_MODE=record python -m evals.runner`

Total time: ~20 minutes.
