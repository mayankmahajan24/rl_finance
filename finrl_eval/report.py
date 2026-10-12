"""Markdown report and failure-mode analysis generated from a run directory."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from finrl_eval.schema import RunSummary, SampleResult


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    s = json.dumps(v) if isinstance(v, list | dict) else str(v)
    return s if len(s) <= 40 else s[:37] + "..."


def render_summary_md(summary: RunSummary, results: list[SampleResult]) -> str:
    lines = [
        f"# Finance RL eval report: `{summary.suite}` x `{summary.provider}/{summary.model}`",
        "",
        f"- Run: `{summary.run_id}`",
        f"- Samples: {summary.n_samples} (errors: {summary.n_errors})",
        f"- Mean score: **{summary.mean_score:.3f}**",
        f"- Pass rate (score >= {summary.pass_threshold}): **{_pct(summary.pass_rate)}**",
        f"- Started: {summary.started_at.isoformat(timespec='seconds')}",
        "",
        "## Score by dimension",
        "",
        _table(
            ["Dimension", "Mean", "n"],
            [[d, f"{a.mean:.3f}", str(a.n)] for d, a in summary.by_dimension.items()],
        ),
        "",
        "## Score by task",
        "",
        _table(
            ["Task", "Mean", "n"],
            [[t, f"{a.mean:.3f}", str(a.n)] for t, a in summary.by_task.items()],
        ),
        "",
        "## Score by criterion",
        "",
        _table(
            ["Criterion", "Mean", "n"],
            [[c, f"{a.mean:.3f}", str(a.n)] for c, a in summary.by_criterion.items()],
        ),
        "",
        "## Per-sample scores",
        "",
        _table(
            ["Sample", "Task", "Difficulty", "Score", "Failed criteria"],
            [
                [
                    r.sample_id,
                    r.task,
                    r.difficulty,
                    f"{r.score:.3f}",
                    ", ".join(r.failed_criteria) or "-",
                ]
                for r in results
            ],
        ),
        "",
    ]
    return "\n".join(lines)


def render_failure_modes_md(
    summary: RunSummary, results: list[SampleResult], worst_n: int = 10
) -> str:
    failed = [r for r in results if r.failed_criteria or r.error]
    crit_counter: Counter[str] = Counter()
    dim_counter: Counter[str] = Counter()
    by_tag: dict[str, list[float]] = defaultdict(list)
    for r in results:
        for t in r.tags:
            by_tag[t].append(r.score)
    for r in failed:
        crit_counter.update(r.failed_criteria)
        dim_counter.update({c.dimension.value for c in r.criteria if not c.passed})

    lines = [
        f"# Failure modes: `{summary.suite}` x `{summary.provider}/{summary.model}`",
        "",
        f"{len(failed)} of {summary.n_samples} samples failed at least one rubric criterion.",
        "",
        "## Most frequently failed criteria",
        "",
        _table(
            ["Criterion", "Failures", "Share of samples"],
            [[c, str(n), _pct(n / summary.n_samples)] for c, n in crit_counter.most_common()],
        )
        if crit_counter
        else "_No criterion failures._",
        "",
        "## Failures by rubric dimension",
        "",
        _table(
            ["Dimension", "Samples with a failure"],
            [[d, str(n)] for d, n in dim_counter.most_common()],
        )
        if dim_counter
        else "_None._",
        "",
        "## Mean score by tag",
        "",
        _table(
            ["Tag", "Mean score", "n"],
            [
                [t, f"{sum(v) / len(v):.3f}", str(len(v))]
                for t, v in sorted(by_tag.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
            ],
        )
        if by_tag
        else "_No tags._",
        "",
        f"## Worst {min(worst_n, len(results))} samples",
        "",
    ]
    worst = sorted(results, key=lambda r: r.score)[:worst_n]
    for r in worst:
        lines += [
            f"### `{r.sample_id}` ({r.task}, {r.difficulty}) - score {r.score:.3f}",
            "",
        ]
        if r.error:
            lines += [f"Provider error: `{r.error}`", ""]
        failed_crits = [c for c in r.criteria if not c.passed]
        if failed_crits:
            lines += [
                _table(
                    ["Criterion", "Dimension", "Score", "Expected", "Actual", "Detail"],
                    [
                        [
                            c.name,
                            c.dimension.value,
                            f"{c.score:.2f}",
                            _fmt(c.expected),
                            _fmt(c.actual),
                            c.detail,
                        ]
                        for c in failed_crits
                    ],
                ),
                "",
            ]
        else:
            lines += ["All criteria passed.", ""]
        excerpt = r.response.strip().replace("```", "'''")
        if len(excerpt) > 600:
            excerpt = excerpt[:600] + " ..."
        lines += [
            "<details><summary>Model response</summary>",
            "",
            "```text",
            excerpt,
            "```",
            "",
            "</details>",
            "",
        ]
    return "\n".join(lines)


def write_reports(run_dir: Path, summary: RunSummary, results: list[SampleResult]) -> None:
    (run_dir / "report.md").write_text(render_summary_md(summary, results))
    (run_dir / "failure_modes.md").write_text(render_failure_modes_md(summary, results))


def load_run(run_dir: Path) -> tuple[RunSummary, list[SampleResult]]:
    summary = RunSummary.model_validate_json((run_dir / "summary.json").read_text())
    results = [
        SampleResult.model_validate_json(line)
        for line in (run_dir / "samples.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return summary, results
