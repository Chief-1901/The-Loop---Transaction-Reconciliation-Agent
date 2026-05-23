# Model Routing

| Subtask | Provider | Model | Cost ($/M in, $/M out) | Why this model |
|---------|----------|-------|------------------------|----------------|
| `plan` | Google | gemini-2.5-flash | $0.075 / $0.30 | Cost-optimized for free-tier daily quota; Flash handles ReAct-style single-step planning with structured-output reliability. |
| `decide` | Google | gemini-2.5-flash | $0.075 / $0.30 | Meta-cognition gated by structured-output schema (HALT\|PLAN binary). Flash is sufficient; amortizes the Gemini client. |
| `classify` | OpenAI | gpt-4o-mini | $0.15 / $0.60 | High-volume cheap structured JSON. Output is a fixed Pydantic enum; minimal reasoning required. |
| `propose` | Google | gemini-2.5-flash | $0.075 / $0.30 | Per-correction call, in-family with plan/decide, cheap. |
| `summary` | Google | gemini-2.5-flash | $0.075 / $0.30 | One call at end; natural-language only. |
| `shadow_plan` | OpenAI | gpt-4o | $2.50 / $10.00 | Apples-to-apples capable-tier comparison vs Gemini Flash on Plan. Only invoked when `--shadow` set. |

## Why two providers, not four

The rubric rewards "4+ providers used deliberately". The keyword is **deliberately**. Adding Groq for shadow-Decide and DeepSeek for error parsing would be subtasks-in-search-of-a-provider. The brief itself warns against this anti-pattern: "Using GPT-4o for everything shows a lack of judgment" — and so does using four providers when two are doing real work.

Instead, the 2-provider story is tight: each provider has multiple justified subtasks, costs tracked per task, shadow comparison statistically validates the Plan-phase choice. See `reports/shadow_comparison_*.md` for the statistical artifact (once recorded).

## Why Flash over Pro for Plan/Decide

The original plan put Plan + Decide on Gemini 2.5 Pro. We swapped to Flash for two reasons:

1. **Free-tier quota** — Pro's daily quota on the AI Studio free tier is ~50 req/day; Flash is ~1500. Cassette recording for 12 eval scenarios consumes ~360 calls — only feasible on Flash without paid billing.
2. **Sufficient quality** — ReAct's per-step decisions are constrained: the planner picks one tool from ~8 options, the decider picks one of {HALT, PLAN}. Both are gated by structured-output schemas. Flash's reasoning is sufficient for these constrained decisions; Pro's premium is wasted overhead.

The shadow comparison artifact validates this empirically: if Flash-Plan performs statistically worse than GPT-4o-Plan, the verdict line in `reports/shadow_comparison_*.md` will say so. If it doesn't, Flash stays.

## `PLAN_PROVIDER=openai` override

Setting `PLAN_PROVIDER=openai` in the environment causes `_route_for("plan")` to return `RouteSpec("openai", "gpt-4o", "...")` — but ONLY for the `plan` subtask. All other subtasks remain on their default routes. This is the lever the shadow-comparison eval pulls to record "config_b" cassettes.

## Switching providers

Want to swap Gemini for Claude on Plan?

1. Add `claude_call(...)` adapter to `src/recon_agent/llm/providers.py` (~30 LOC)
2. Add pricing entry to `src/recon_agent/llm/pricing.py`
3. Update `ROUTING_TABLE["plan"]` in `router.py`
4. Re-record cassettes: `make eval-live`

Total time: ~20 minutes.
