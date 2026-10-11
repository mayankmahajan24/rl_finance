.PHONY: install test lint typecheck check replay eval eval-earnings eval-fixed-income fixtures format-tasks docker-build docker-eval docker-pipeline clean

UV ?= uv
IMAGE ?= finrl-eval:local

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

eval-earnings:
	$(UV) run finrl-eval run --suite earnings --provider $(PROVIDER)

eval-fixed-income:
	$(UV) run finrl-eval run --suite fixed_income --provider $(PROVIDER)

PROVIDER ?= mock
eval: eval-earnings eval-fixed-income

fixtures:
	$(UV) run python scripts/generate_earnings_fixtures.py

docker-build:
	docker build -t $(IMAGE) .

docker-eval: docker-build
	docker compose run --rm eval run --suite earnings --provider $(PROVIDER)
	docker compose run --rm eval run --suite fixed_income --provider $(PROVIDER)

docker-pipeline: docker-build
	docker compose run --rm pipeline

clean:
	rm -rf runs .pytest_cache .mypy_cache .ruff_cache
