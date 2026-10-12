"""Run orchestrator. Load samples, render prompts, call a provider, score with the rubric, and write a run directory."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from finrl_eval.prompts import parse_json_answer
from finrl_eval.providers import get_provider
from finrl_eval.providers.base import ModelProvider
from finrl_eval.report import write_reports
from finrl_eval.rewards import write_rewards
from finrl_eval.schema import (
    DimensionAggregate,
    ModelRequest,
    RewardRecord,
    RunConfig,
    RunSummary,
    Sample,
    SampleResult,
)
from finrl_eval.scorers import ScoreContext
from finrl_eval.suites import get_suite
from finrl_eval.suites.base import TaskSuite

ProgressFn = Callable[[int, int, SampleResult], None]


def _agg(values: list[float]) -> DimensionAggregate:
    return DimensionAggregate(mean=round(mean(values), 4) if values else 0.0, n=len(values))


def evaluate_sample(
    suite: TaskSuite,
    sample: Sample,
    provider: ModelProvider,
    judge: ModelProvider | None,
    system: str,
    prompt: str,
) -> SampleResult:
    req = ModelRequest(
        sample_id=sample.id,
        system=system,
        prompt=prompt,
        oracle={"expected": sample.expected} if provider.needs_oracle else None,
    )
    resp = provider.complete(req)
    parsed = parse_json_answer(resp.text) if resp.text else None
    outcome = suite.rubric().evaluate(
        ScoreContext(sample=sample, response=resp.text, parsed=parsed, judge=judge)
    )
    return SampleResult(
        sample_id=sample.id,
        task=sample.task,
        tags=sample.tags,
        difficulty=sample.difficulty,
        prompt=prompt,
        response=resp.text,
        parsed=parsed,
        score=outcome.score if not resp.error else 0.0,
        dimension_scores=outcome.dimension_scores,
        criteria=outcome.criteria,
        failed_criteria=outcome.failed,
        latency_ms=resp.latency_ms,
        error=resp.error,
    )


def summarize(
    config: RunConfig,
    suite: TaskSuite,
    provider: ModelProvider,
    results: list[SampleResult],
    run_id: str,
    started: datetime,
) -> RunSummary:
    by_dim: dict[str, list[float]] = defaultdict(list)
    by_task: dict[str, list[float]] = defaultdict(list)
    by_crit: dict[str, list[float]] = defaultdict(list)
    for r in results:
        by_task[r.task].append(r.score)
        for d, s in r.dimension_scores.items():
            by_dim[d].append(s)
        for c in r.criteria:
            by_crit[c.name].append(c.score)
    scores = [r.score for r in results]
    return RunSummary(
        run_id=run_id,
        suite=suite.spec.name,
        suite_version=suite.spec.version,
        provider=provider.name,
        model=provider.model,
        started_at=started,
        finished_at=datetime.now(UTC),
        n_samples=len(results),
        n_errors=sum(1 for r in results if r.error),
        mean_score=round(mean(scores), 4) if scores else 0.0,
        pass_rate=round(sum(1 for s in scores if s >= config.pass_threshold) / len(scores), 4)
        if scores
        else 0.0,
        pass_threshold=config.pass_threshold,
        by_dimension={k: _agg(v) for k, v in sorted(by_dim.items())},
        by_task={k: _agg(v) for k, v in sorted(by_task.items())},
        by_criterion={k: _agg(v) for k, v in sorted(by_crit.items())},
    )


def run(
    config: RunConfig, runs_root: Path = Path("runs"), progress: ProgressFn | None = None
) -> tuple[Path, RunSummary]:
    started = datetime.now(UTC)
    suite = get_suite(config.suite)
    provider = get_provider(config.provider, config.model, seed=config.seed)
    judge = get_provider(config.judge_provider, seed=config.seed) if config.judge_provider else None
    engine = suite.prompt_engine()

    samples = suite.load_samples()
    if config.limit:
        samples = samples[: config.limit]

    base_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{suite.spec.name}-{provider.name}"
    run_id, n = base_id, 1
    while (runs_root / run_id).exists():
        n += 1
        run_id = f"{base_id}-{n}"
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "config.json").write_text(config.model_dump_json(indent=2))
    (run_dir / "rubric.json").write_text(json.dumps(suite.rubric().describe(), indent=2))

    results: list[SampleResult] = []
    rewards: list[RewardRecord] = []
    with (run_dir / "samples.jsonl").open("w") as fh:
        for i, sample in enumerate(samples, 1):
            prompt = engine.render(sample)
            result = evaluate_sample(suite, sample, provider, judge, engine.system, prompt)
            results.append(result)
            fh.write(result.model_dump_json() + "\n")
            rewards.append(
                RewardRecord(
                    sample_id=sample.id,
                    suite=suite.spec.name,
                    task=sample.task,
                    prompt=prompt,
                    system=engine.system,
                    response=result.response,
                    reward=result.score,
                    dimension_rewards=result.dimension_scores,
                    failed_criteria=result.failed_criteria,
                    hard_constraint_violation=any(
                        c.name in result.failed_criteria for c in suite.rubric().criteria if c.hard
                    ),
                )
            )
            if progress:
                progress(i, len(samples), result)

    summary = summarize(config, suite, provider, results, run_id, started)
    (run_dir / "summary.json").write_text(summary.model_dump_json(indent=2))
    write_rewards(run_dir, rewards)
    write_reports(run_dir, summary, results)
    return run_dir, summary
