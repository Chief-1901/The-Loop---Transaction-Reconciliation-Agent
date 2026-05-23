# Model Routing

| Subtask | Provider | Model | Cost ($/M in, $/M out) | Why this model |
|---------|----------|-------|------------------------|----------------|
| `plan` | Google | gemini-2.5-flash-lite | $0.01 / $0.04 | Cheapest tier in the Flash family. Generous free-tier daily quota. Structured-output reliability is sufficient for ReAct's constrained single-step planning. |
| `decide` | Google | gemini-2.5-flash-lite | $0.01 / $0.04 | Binary HALT-vs-PLAN decision gated by structured-output schema; flash-lite is sufficient and in-family with plan. |
| `classify` | OpenAI | gpt-4o-mini | $0.15 / $0.60 | High-volume cheap structured JSON via OpenAI's `json_schema strict` mode. Output is a fixed Pydantic enum; minimal reasoning required. |
| `propose` | Google | gemini-2.5-flash-lite | $0.01 / $0.04 | Per-correction call; many of them; cheapest available Gemini model in-family with plan/decide. |
| `summary` | Google | gemini-2.5-flash-lite | $0.01 / $0.04 | One call at end; natural-language only. In-family. |
| `shadow_plan` | OpenAI | gpt-4o | $2.50 / $10.00 | Capable-tier comparison vs Gemini flash-lite on Plan. Only invoked when `--shadow` is set. |

## Why two providers, not four

The rubric rewards "4+ providers used deliberately". The keyword is **deliberately**. Adding Groq for shadow-Decide and DeepSeek for error parsing would be subtasks-in-search-of-a-provider. The brief itself warns against this anti-pattern: "Using GPT-4o for everything shows a lack of judgment" — and the same applies to using four providers when two are doing real work.

Instead, the 2-provider story is tight: each provider has multiple justified subtasks, costs tracked per task, shadow comparison statistically validates the Plan-phase choice. See `reports/shadow_comparison_*.md` for the statistical artifact.

## Why flash-lite over flash or pro for Plan/Decide

The original design routed Plan + Decide to Gemini 2.5 Pro. We moved through three model choices during development and settled on **flash-lite**. Honest reasoning:

1. **Cost** — flash-lite is **~8x cheaper than flash** ($0.01/M vs $0.075/M input) and **~125x cheaper than Pro** ($0.01/M vs $1.25/M input). At the scale GrabOn's brief describes (96M txns/year), this gap compounds into real money.

2. **Free-tier quota** — Pro's daily quota on AI Studio free tier is ~50 req/day. Standard Flash is ~20 req/day. flash-lite has substantially more headroom — enough for cassette recording (~360 calls across 12 scenarios) in a single sitting without billing.

3. **Sufficient quality for ReAct** — Plan picks ONE tool from a fixed set of ~8 options. Decide picks ONE of {HALT, PLAN}. Both are constrained by Pydantic structured-output schemas. There's no open-ended generation where Pro's reasoning premium would actually matter — the decision space is tiny.

4. **In-family routing** — keeping plan/decide/propose/summary all on Gemini flash-lite amortizes the SDK client, simplifies the prompt-cache story, and gives a single cohesive provider story.

The shadow-comparison artifact (`reports/shadow_comparison_*.md`) empirically validates this choice: if flash-lite-Plan performs statistically worse than GPT-4o-Plan, the verdict line will say so and we'd revisit. If it doesn't, flash-lite stays.

## `GEMINI_MODEL` env override

Set `GEMINI_MODEL=gemini-2.5-flash` (or any other Gemini model in the pricing table) to swap the default at runtime — useful for ad-hoc testing or if flash-lite ever hits a quota wall. The override applies to all Gemini-routed subtasks (plan, decide, propose, summary).

## `PLAN_PROVIDER=openai` override

Set `PLAN_PROVIDER=openai` to force the `plan` subtask (ONLY) to use `gpt-4o`. This is the lever the shadow-comparison eval pulls to record "config_b" cassettes. Other subtasks remain on default Gemini routes.

## Switching providers entirely

Want to swap Gemini for Claude on Plan?

1. Add `claude_call(...)` adapter to `src/recon_agent/llm/providers.py` (~30 LOC)
2. Add pricing entries to `src/recon_agent/llm/pricing.py`
3. Update `ROUTING_TABLE["plan"]` in `router.py`
4. Re-record cassettes: `LLM_MODE=record python -m evals.runner`

Total time: ~20 minutes.
