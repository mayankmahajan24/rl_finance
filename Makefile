.PHONY: install test lint typecheck check replay fixtures format-tasks clean

UV ?= uv

install:
	$(UV) sync

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

typecheck:
	$(UV) run mypy finrl_eval tests scripts

replay:
	$(UV) run python rl/replay_case_study.py

format-tasks:
	$(UV) run python scripts/build_instrumentation_suites.py

check: lint typecheck test replay

fixtures:
	$(UV) run python scripts/generate_earnings_fixtures.py

clean:
	rm -rf runs .pytest_cache .mypy_cache .ruff_cache
