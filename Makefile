.PHONY: install test lint typecheck check replay fixtures format-tasks eval eval-earnings eval-fixed-income docker-build docker-eval docker-pipeline clean

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

# Shortcuts for one suite. `make eval` loops `finrl-eval runnable`.
eval-earnings:
	$(UV) run finrl-eval run --suite earnings --provider $(PROVIDER)

eval-fixed-income:
	$(UV) run finrl-eval run --suite fixed_income --provider $(PROVIDER)

PROVIDER ?= mock
eval:
	@set -eu; \
	for suite in $$($(UV) run finrl-eval runnable); do \
		$(UV) run finrl-eval run --suite "$$suite" --provider $(PROVIDER); \
	done

IMAGE ?= finrl-eval:local
docker-build:
	docker build -t $(IMAGE) .

docker-eval: docker-build
	@set -eu; \
	for suite in $$(docker compose run --rm -T eval runnable); do \
		docker compose run --rm eval run --suite "$$suite" --provider $(PROVIDER); \
	done

docker-pipeline: docker-build
	docker compose run --rm pipeline

fixtures:
	$(UV) run python scripts/generate_earnings_fixtures.py

clean:
	rm -rf runs .pytest_cache .mypy_cache .ruff_cache
