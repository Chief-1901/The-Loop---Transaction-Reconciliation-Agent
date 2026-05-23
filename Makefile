.PHONY: help setup demo demo-shadow demo-replay eval eval-live eval-compare \
        refresh-baseline lint typecheck test unit integration clean

help:
	@echo "make setup           # venv + deps"
	@echo "make demo            # run agent live (~45s, ~₹4)"
	@echo "make demo-shadow     # demo + Plan-phase shadow runner enabled"
	@echo "make demo-replay     # demo using cassettes (free)"
	@echo "make eval            # 12 scenarios via cassette replay (~30s, free)"
	@echo "make eval-live       # re-record cassettes (~5min, ~₹52)"
	@echo "make eval-compare    # produce shadow_comparison_*.md"
	@echo "make refresh-baseline"
	@echo "make lint            # ruff"
	@echo "make typecheck       # mypy"
	@echo "make test            # pytest (unit + integration)"

setup:
	python -m venv .venv
	.venv/Scripts/pip install -e ".[dev]"
	@test -f .env || cp .env.example .env
	@echo ">> Setup done. Edit .env to add GEMINI_API_KEY + OPENAI_API_KEY."

demo:
	.venv/Scripts/recon demo

demo-shadow:
	.venv/Scripts/recon demo --shadow

demo-replay:
	.venv/Scripts/recon demo --llm-mode replay

eval:
	LLM_MODE=replay .venv/Scripts/python -m evals.runner

eval-live:
	LLM_MODE=record .venv/Scripts/python -m evals.runner

eval-compare:
	@PLAN_PROVIDER=gemini LLM_MODE=replay .venv/Scripts/python -m evals.runner --tag config_a
	@PLAN_PROVIDER=openai LLM_MODE=replay .venv/Scripts/python -m evals.runner --tag config_b
	@.venv/Scripts/python -m evals.compare config_a config_b

refresh-baseline:
	.venv/Scripts/python -m evals.runner --output-json evals/baselines/main.json

lint:
	.venv/Scripts/ruff check src/ evals/ tests/

typecheck:
	.venv/Scripts/mypy src/

test: unit integration
unit:
	.venv/Scripts/pytest tests/unit -v
integration:
	.venv/Scripts/pytest tests/integration -v

clean:
	rm -rf reports/run_* reports/eval_* reports/shadow_comparison_*.md
	rm -f src/recon_agent/data/fixtures/tracking_db.csv
	rm -f src/recon_agent/data/fixtures/payu_settlements.json
