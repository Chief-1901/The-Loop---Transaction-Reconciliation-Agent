# GrabOn AI Labs Challenge — Brainstorming Q&A Log

Project: Assignment 02 "The Loop" — Transaction Reconciliation Agent
Date started: 2026-05-23
Working directory: `D:\GrabOn - Interview Assignnment challenge\`
Official brief: `grabon_challenge.md`

This log captures every clarifying question asked during the design phase, the options offered, the user's selection, and the reasoning. Use it to recover context if the conversation is lost or to review why a decision was made.

---

## Q1 — Planner output style

**Question:** How should the Planner output its plan each iteration?

**Options offered:**
1. **ReAct (single next action) — Recommended.** Each loop iteration the planner emits ONE next tool call + reasoning. Simpler state, easier recovery (just re-plan one step), easier to make Decide reasoning concrete. Standard for production agents.
2. **Plan-and-Execute (multi-step plan upfront).** Planner emits a full ordered plan (e.g., 8 steps) at the start, executor walks it. Re-plans only on failure or when the plan is exhausted. Fewer LLM calls = cheaper, but harder to recover gracefully and the "agentic loop" is less visible.
3. **Hybrid: ReAct loop with mini-plan hint.** Planner emits next action AND a "rough next 2-3 steps" hint for context. LLM has lookahead but executor only commits to one step at a time.

**User selected:** ReAct (single next action).

**Why this matters:** Shapes the whole architecture. ReAct means Plan is called every iteration, Decide is meta-cognition over a single observation. Recovery becomes simpler — re-plan one step, not re-plan a multi-step sequence.

---

## Q2 — Apply-correction semantics

**Question:** When the agent applies a correction, what should it actually do?

**Options offered:**
1. **Corrections ledger (write-only) — Recommended.** `apply_correction` appends to a `corrections.jsonl` ledger; source CSV/API stays immutable. Audit-friendly, evals trivially verifiable (diff ledger vs ground_truth), demo runs repeatable, matches how real payments-ops teams work.
2. **Mutate a working copy.** Each run copies fixtures to a `/workdir`, agent mutates the copy. More "real" but eval verification needs full file diff, each run needs reset.
3. **Propose-only mode (no apply).** Agent emits proposed corrections, never writes. Safest, but the brief says "apply them, verify reconciliation" — would fail a stated requirement.

**User selected:** Corrections ledger (write-only).

**Why this matters:** Ledger is the only mutation point in the entire system. Everything else is read-only on fixtures. Production-thinking signal for the deep-dive.

---

## Q3 — Eval LLM mode

**Question:** How should the 12 eval scenarios handle LLM calls? (Demo MUST be live per brief — this is only about evals.)

**Options offered:**
1. **Record-replay cassettes — Recommended.** First eval run records every LLM call to `evals/cassettes/<scenario>.jsonl`. Subsequent runs replay deterministically. `make eval` is free + fast + reproducible. `make eval-live` re-records. Submission ships with committed cassettes.
2. **All-live evals every run.** Each eval run costs ~$2-5 and takes 5-10 min. No reproducibility — same scenario can pass once, fail next time. CI-hostile.
3. **Hybrid: critical scenarios live, rest replayed.** More complex Makefile, harder to defend in deep-dive.

**User selected:** Record-replay cassettes.

**Clarification given before answer:** explained what a cassette is (recorded JSONL of `(prompt, model, response)`, replayed deterministically), the cost difference ($5 vs $80+ over 3 days of dev iteration), and the reviewer experience (clone repo and `make eval` works without API keys).

**Why this matters:** Makes evals fast, free, reproducible, CI-friendly. Reviewers can verify our claims without spending money.

---

## Q4 — Third provider (Ollama)

**Question:** Do you want Ollama (local Llama 3 or Mistral) as the 3rd provider?

**Options offered:**
1. **Yes, but graceful fallback — Recommended.** Router tries Ollama for one cheap subtask. If Ollama isn't running, falls back to Haiku. Earns multi-LLM points without setup friction.
2. **Yes, required (no fallback).** Strongest multi-LLM signal but adds 5-15 min to setup.
3. **No, skip Ollama.** Two providers is enough per brief's Minimum Bar.

**User initially selected:** No, skip Ollama.

**Note:** This decision was later reconsidered (see Q8 below) when the official rubric was found to reward 4+ providers for 5/5 on Multi-LLM. Final decision after the "smart plan" debate: still 2 providers (Gemini + OpenAI), but with shadow testing between them to score 4/5 on Multi-LLM.

---

## Q5 — Loom video shape

**Question:** What should the 15-20 min Loom demo prioritize?

**Options offered (multi-select):**
1. Live happy-path run (3-5 min) — `make demo` on ~50 txns, dashboard visible, tools firing, ledger appending
2. Live failure-recovery scenario (3-5 min) — `--seed-fail fetch_api` triggers 30% failure, classifier marks transient, retry-backoff kicks in
3. Architecture walkthrough (4-6 min) — Mermaid diagram on screen, walk through loop → tools → router → recovery → budget
4. Eval run with cassettes (2-3 min) — `make eval` runs all 12 scenarios in ~30s, shows report

**User selected:** All four.

**Why this matters:** Loom total ≈ 12-19 min, fits the 15-20 min target. Each scene answers a specific question reviewers will ask.

---

## Q6 — Mid-stream provider swap

**User instruction:** "I want to use gemini+openAI not claude change that also make sure that i score as maximum points as possible"

**Action taken:**
- Updated routing table to use Google Gemini + OpenAI, no Anthropic.
- Read the official brief at `grabon_challenge.md` to confirm the exact rubric.
- Identified the rubric gap: current plan would cap at ~86% (3/5 on Multi-LLM, 3/5 on Eval Rigor) because the official rubric's 5/5 criteria are "4+ providers used deliberately" and "30+ cases, statistical comparison with p-values, CI/CD gate".

---

## Q7 — Max-score upgrades

**Question:** Which max-score upgrades do you want in the plan? (Pick any subset. Each is independent.)

**Options offered (multi-select):**
1. **Upgrade providers 2 → 4 (Gemini + OpenAI + Groq + DeepSeek) — Recommended.** Closes Multi-LLM 3→4.
2. **Add shadow testing — Recommended.** Closes Multi-LLM 4→5.
3. **Eval cases 12 → 30+ via parametric seeds — Recommended.** Closes Eval Rigor 3→4.
4. **Statistical comparison + GitHub Actions CI gate — Recommended.** Closes Eval Rigor 4→5.

**User selected initially:** All four.

**Then user asked:** "or do you think its too much just do what they asked and move on? whats your opinion?"

---

## Q8 — Smart plan vs bloated max (my honest opinion)

**Recommendation given:** The smart plan, not bloated max.

**Reasoning:**
- The rubric isn't a binary checklist. 2 providers with justified subtasks, cost-per-task, and shadow testing between them can realistically score 4/5 on Multi-LLM — not 3/5.
- The brief itself warns: "Using GPT-4o for intent classification and Ollama for error parsing shows judgment. Using GPT-4o for everything shows a lack of it." The flip side is equally true: bolting on Groq + DeepSeek for subtasks that don't need separate providers also shows lack of judgment.
- Brief says: "A thoughtful partial implementation with a strong README... is better than a rushed complete implementation."

**KEEP from max plan (high leverage, low risk):**
- Shadow testing between Gemini Pro and GPT-4o on Plan phase (same 2 providers, no new SDKs)
- Statistical comparison (paired bootstrap, p-values, 95% CI)
- GitHub Actions CI gate (cassette evals on PR)
- Versioned state snapshots

**DROP from max plan (low marginal value, high risk):**
- 2 → 4 providers (Groq + DeepSeek). Skip. Make the 2-provider story tight instead.
- 12 → 30+ parametric scenarios. Skip. 12 rigorous scenarios beats 30+ bloated ones.

**Projected scores:**
- Original plan: ~86%
- Bloated max: ~100% if executed perfectly, high execution risk
- **Smart plan: ~92-94%, high execution confidence** ← chosen

**User selected:** Smart plan. "okay proceed with the smart plan plan intencively using the skills and /superpower:brainstorming so that we dont have to plan throught the project make sure we are getting each and every minute detail"

---

## Design sections — running approval status

| # | Section | Status |
|---|---|---|
| 1 | High-level architecture | ✅ Approved |
| 2 | AgentState + loop contract + terminal conditions | ✅ Approved |
| 3 | Tool registry + 8 tool specs | ✅ Approved |
| 4 | LLM router + cost tracking + shadow + statistical comparison | ✅ Approved |
| 5 | Recovery + Budget + Observability | ✅ Approved |
| 6 | Mock fixtures + ground truth + ledger | ✅ Approved |
| 7 | Eval framework + 12 scenarios + CI gate | ✅ Approved |
| 8 | Repo layout + CLI surface + Makefile | ✅ Approved |
| 9 | README outline + Loom script + cost model | ✅ Approved |

## Files produced from the design phase

| File | Purpose |
|---|---|
| `docs/superpowers/specs/2026-05-23-recon-agent-design.md` | Canonical design spec; source of truth for implementation |
| `docs/superpowers/plans/2026-05-23-recon-agent-implementation.md` | Phase-by-phase implementation plan (~70 tasks across 10 phases) |
| `LOOM_SCRIPT.md` | Read-aloud script for the 15-20 min Loom video |
| `DEEP_DIVE_PREP.md` | Interview prep for the 60-min technical deep-dive |
| `BRAINSTORMING_LOG.md` | This file — Q&A log |

## Implementation plan — phase overview

10 phases, each independently shippable. Phases are logical milestones, not calendar days (per user preference).

| # | Phase | Exit condition |
|---|---|---|
| 1 | Scaffolding + no-op loop | `recon demo` runs a 1-step no-op loop, exits 0, writes snapshots |
| 2 | LLM plumbing | Plan + Decide make real LLM calls, halt cleanly |
| 3 | Data layer | `generate_fixtures.py` produces deterministic output for all 10 variants |
| 4 | 8 core tools | All 8 tools registered, individually unit-tested, runnable end-to-end |
| 5 | Recovery + budget enforcement | Forced 429 demo recovers cleanly; `--budget-calls 3` halts cleanly |
| 6 | Observability polish | Rich dashboard renders during `make demo`; structlog JSONL parseable |
| 7 | Eval framework + 12 scenarios | `make eval` shows 12/12 PASS in replay mode (~30s, free) |
| 8 | Shadow + statistical comparison | `make eval-compare` produces `shadow_comparison_*.md` with p-value |
| 9 | CI gate | GitHub Actions runs evals on PR, blocks merge on regression |
| 10 | Documentation & polish | README a-k complete with real cost data, Loom recorded, submission sent |

---

## Final consolidated decisions

(See also: `C:\Users\Admin\.claude\projects\D--GrabOn---Interview-Assignnment-challenge\memory\design_decisions.md`)

1. **Planner style:** ReAct (single next action per iteration)
2. **Apply semantics:** Append-only `corrections.jsonl` ledger
3. **Eval mode:** Record-replay cassettes; demo stays live
4. **Providers (2):** Google Gemini (2.5 Pro + 2.5 Flash) + OpenAI (GPT-4o-mini + GPT-4o)
5. **Shadow testing:** Plan phase only, `--shadow` flag, off by default
6. **Eval scenarios:** 12 rigorous (5 happy + 3 recovery + 2 budget + 2 impossible)
7. **Statistical comparison:** Paired bootstrap, 10k resamples, p-value + 95% CI
8. **CI gate:** GitHub Actions, runs `make eval` on PR, blocks merge on regression
9. **Loom structure:** happy path → failure recovery → architecture → eval, 12-19 min total
10. **State management:** Pydantic v2 `AgentState` with `version` field, snapshot per step
11. **Recovery:** Separate layer; 3 strategies (retry / replan / degrade) dispatched by error kind
12. **Budget:** Pydantic `Budget`, checked top-of-loop, CLI-overridable, defaults: 100k tokens / 600s / 60 calls / 5 fails / ₹50

**Target score:** 4-5/5 across all five rubric dimensions, ~92-94% projected, high execution confidence.
