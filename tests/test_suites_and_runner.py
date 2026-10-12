import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finrl_eval.cli import app
from finrl_eval.providers import get_provider
from finrl_eval.providers.base import ProviderError
from finrl_eval.providers.mock import failure_kind
from finrl_eval.report import load_run
from finrl_eval.rewards import shaped_reward
from finrl_eval.runner import run
from finrl_eval.schema import RewardRecord, RunConfig
from finrl_eval.suites import get_suite, live_suites, planned

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("suite_name", sorted(live_suites()))
def test_suite_samples_prompts_and_rubric_are_consistent(suite_name: str) -> None:
    suite = get_suite(suite_name)
    samples = suite.load_samples()
    assert samples, "suite has no samples"
    assert len({s.id for s in samples}) == len(samples), "duplicate sample ids"
    engine = suite.prompt_engine()
    rubric = suite.rubric()
    for s in samples:
        assert s.task in suite.spec.tasks
        prompt = engine.render(s)
        for field in s.inputs["answer_fields"]:
            assert field in prompt
        # Every numeric expected field must be covered by some criterion for that task.
        scored_fields = {getattr(c.scorer, "field", None) for c in rubric.for_task(s.task)}
        for key in s.expected:
            assert key in scored_fields, f"{suite_name}/{s.task}: {key} not scored"


@pytest.mark.parametrize("suite_name", sorted(live_suites()))
def test_oracle_scores_perfect_and_broken_scores_floor(suite_name: str, tmp_path: Path) -> None:
    _, oracle = run(RunConfig(suite=suite_name, provider="mock", model="mock-oracle"), tmp_path)
    assert oracle.mean_score == 1.0 and oracle.pass_rate == 1.0
    _, broken = run(RunConfig(suite=suite_name, provider="mock", model="mock-broken"), tmp_path)
    assert broken.mean_score <= 0.25 and broken.pass_rate == 0.0


def test_noisy_run_is_deterministic_and_writes_artifacts(tmp_path: Path) -> None:
    cfg = RunConfig(suite="earnings", provider="mock", seed=7, limit=10)
    dir_a, sum_a = run(cfg, tmp_path / "a")
    dir_b, sum_b = run(cfg, tmp_path / "b")
    assert sum_a.mean_score == sum_b.mean_score
    assert sum_a.by_criterion == sum_b.by_criterion
    assert 0.0 < sum_a.mean_score < 1.0
    for name in [
        "config.json",
        "rubric.json",
        "samples.jsonl",
        "summary.json",
        "rewards.jsonl",
        "report.md",
        "failure_modes.md",
    ]:
        assert (dir_a / name).exists(), name
    summary, results = load_run(dir_a)
    assert summary.n_samples == len(results) == 10
    rewards = [
        RewardRecord.model_validate_json(line)
        for line in (dir_a / "rewards.jsonl").read_text().splitlines()
    ]
    assert [r.reward for r in rewards] == [r.score for r in results]
    assert (dir_a / "failure_modes.md").read_text().startswith("# Failure modes")


def test_mock_failure_kinds_cover_all_buckets() -> None:
    kinds = {failure_kind(0, f"s{i}", "noisy") for i in range(500)}
    assert kinds == {
        "correct",
        "numeric_slip",
        "gaap_confusion",
        "unit_error",
        "missing_field",
        "format_violation",
    }
    assert failure_kind(0, "x", "oracle") == "correct"
    assert failure_kind(0, "x", "broken") == "format_violation"


def test_shaped_reward() -> None:
    rec = RewardRecord(
        sample_id="a",
        suite="s",
        task="t",
        prompt="",
        system="",
        response="",
        reward=0.8,
        dimension_rewards={"math": 0.6, "context": 1.0},
        failed_criteria=[],
        hard_constraint_violation=False,
    )
    assert shaped_reward(rec) == 0.8
    assert shaped_reward(rec, {"math": 3, "context": 1}) == 0.7
    rec.hard_constraint_violation = True
    assert shaped_reward(rec) == pytest.approx(0.3)


def test_real_providers_require_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        get_provider("anthropic")
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        get_provider("openai")
    with pytest.raises(ProviderError, match="Unknown provider"):
        get_provider("nope")


def test_earnings_fixture_is_not_stale() -> None:
    spec = importlib.util.spec_from_file_location(
        "gen", REPO / "scripts" / "generate_earnings_fixtures.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen"] = module  # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(module)
    checked_in = (REPO / "finrl_eval/suites/earnings/fixtures/earnings.json").read_text()
    assert module.render() == checked_in, "run scripts/generate_earnings_fixtures.py"


def test_cli_list_run_report(tmp_path: Path) -> None:
    runner = CliRunner()
    listed = runner.invoke(app, ["list", "--json"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert {s["name"] for s in payload["suites"]} == set(live_suites())
    assert payload["planned"] == planned()
    assert set(payload["planned"]) == {"quant_signal", "dataset_valuation"}
    mirrors = payload["format_mirrors"]
    for cls in live_suites().values():
        assert mirrors[cls.mirror.workflow] == len(cls().load_samples())

    names = runner.invoke(app, ["runnable"])
    assert names.exit_code == 0, names.output
    assert names.output.splitlines() == list(live_suites())

    ran = runner.invoke(
        app,
        [
            "run",
            "--suite",
            "fixed_income",
            "--provider",
            "mock",
            "--limit",
            "4",
            "--runs-dir",
            str(tmp_path),
        ],
    )
    assert ran.exit_code == 0, ran.output
    run_dir = next(tmp_path.iterdir())
    assert run_dir.name.endswith("-fixed_income-mock")

    rep = runner.invoke(app, ["report", str(run_dir)])
    assert rep.exit_code == 0 and rep.output.startswith("# Finance RL eval report")
    fail = runner.invoke(app, ["report", str(run_dir), "--failures", "--regenerate"])
    assert fail.exit_code == 0 and "Worst" in fail.output

    bad = runner.invoke(app, ["run", "--suite", "quant_signal", "--runs-dir", str(tmp_path)])
    assert bad.exit_code == 2 and "planned" in bad.output
    bad_dir = runner.invoke(app, ["report", str(tmp_path / "missing")])
    assert bad_dir.exit_code == 2
