"""`finrl-eval` command line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from finrl_eval import __version__
from finrl_eval.providers import PROVIDERS
from finrl_eval.schema import RunConfig, SampleResult
from finrl_eval.suites import live_suites, planned

app = typer.Typer(
    help="Finance RL: evaluate frontier models on high-stakes financial tasks.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _version_callback() -> None:  # pragma: no cover - typer plumbing
    pass


@app.command("list")
def list_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable")] = False,
) -> None:
    """List available suites, their tasks, and providers."""
    suites: list[dict[str, Any]] = []
    mirror_counts: dict[str, int] = {}
    mirror_lines: list[str] = []
    for name, cls in live_suites().items():
        suite = cls()
        n_samples = len(suite.load_samples())
        mirror = cls.mirror
        mirror_counts[mirror.workflow] = n_samples
        mirror_lines.append(
            f"  {mirror.workflow:<16}{n_samples:>2} tasks  ({mirror.role} / {mirror.world})"
        )
        suites.append(
            {
                "name": name,
                "title": cls.spec.title,
                "version": cls.spec.version,
                "tasks": cls.spec.tasks,
                "n_samples": n_samples,
                "n_criteria": len(suite.rubric().criteria),
                "description": cls.spec.description,
            }
        )
    payload = {
        "suites": suites,
        "planned": planned(),
        "providers": sorted(PROVIDERS),
        "format_mirrors": {
            **mirror_counts,
            "note": (
                "FORMAT task folders under rl/roles/; "
                "rebuilt by scripts/build_instrumentation_suites.py"
            ),
        },
    }
    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.secho(f"finrl-eval {__version__}", bold=True)
    typer.echo("\nSuites:")
    for s in suites:
        typer.echo(
            f"  {s['name']:<14} {s['title']}  [v{s['version']}, "
            f"{s['n_samples']} samples, {s['n_criteria']} criteria]"
        )
        typer.echo(f"  {'':<14} tasks: {', '.join(s['tasks'])}")
    typer.echo("\nPlanned (extension points, not runnable):")
    for name, desc in planned().items():
        typer.echo(f"  {name:<14} {desc}")
    typer.echo("\nFORMAT mirrors (rl/roles/, produce + rubric grader):")
    for line in mirror_lines:
        typer.echo(line)
    typer.echo(f"\nProviders: {', '.join(sorted(PROVIDERS))}")
    typer.echo("  mock models: mock-noisy (default), mock-oracle, mock-broken")


@app.command("runnable")
def runnable_cmd() -> None:
    """Print live suite names, one per line, in registry order."""
    for name in live_suites():
        typer.echo(name)


@app.command("run")
def run_cmd(
    suite: Annotated[str, typer.Option(help="Suite name, see `finrl-eval list`.")],
    provider: Annotated[str, typer.Option(help="mock | anthropic | openai")] = "mock",
    model: Annotated[str | None, typer.Option(help="Provider model id.")] = None,
    limit: Annotated[int | None, typer.Option(help="Only run the first N samples.")] = None,
    judge: Annotated[str | None, typer.Option(help="Provider for LLM-as-judge criteria.")] = None,
    pass_threshold: Annotated[float, typer.Option()] = 0.8,
    seed: Annotated[int, typer.Option(help="Seed for the mock provider.")] = 0,
    runs_dir: Annotated[Path, typer.Option(help="Root directory for run outputs.")] = Path("runs"),
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    """Run a suite against a provider and write results to runs/<timestamp>/."""
    from finrl_eval.runner import run

    runnable = live_suites()
    if suite not in runnable:
        hint = " (planned, not yet implemented)" if suite in planned() else ""
        typer.secho(f"Unknown suite {suite!r}{hint}. Available: {', '.join(runnable)}", fg="red")
        raise typer.Exit(2)
    config = RunConfig(
        suite=suite,
        provider=provider,
        model=model,
        limit=limit,
        judge_provider=judge,
        pass_threshold=pass_threshold,
        seed=seed,
    )

    def progress(i: int, n: int, r: SampleResult) -> None:
        if quiet:
            return
        status = "ERR " if r.error else ("PASS" if r.score >= pass_threshold else "FAIL")
        color = "red" if status != "PASS" else "green"
        failed = f"  failed: {', '.join(r.failed_criteria)}" if r.failed_criteria else ""
        typer.secho(f"[{i:>3}/{n}] {status} {r.score:.3f}  {r.sample_id}{failed}", fg=color)

    try:
        run_dir, summary = run(config, runs_root=runs_dir, progress=progress)
    except Exception as exc:  # surface provider/config errors cleanly
        typer.secho(f"error: {exc}", fg="red")
        raise typer.Exit(1) from exc

    typer.echo("")
    typer.secho(
        f"suite={summary.suite} provider={summary.provider} model={summary.model}", bold=True
    )
    typer.echo(
        f"mean score {summary.mean_score:.3f}  pass rate {summary.pass_rate * 100:.1f}%  "
        f"({summary.n_samples} samples, {summary.n_errors} errors)"
    )
    for d, a in summary.by_dimension.items():
        typer.echo(f"  {d:<11} {a.mean:.3f}")
    typer.echo(f"\nresults: {run_dir}")
    typer.echo(f"  report:        {run_dir / 'report.md'}")
    typer.echo(f"  failure modes: {run_dir / 'failure_modes.md'}")
    typer.echo(f"  rewards:       {run_dir / 'rewards.jsonl'}")


@app.command("report")
def report_cmd(
    run_dir: Annotated[Path, typer.Argument(help="A runs/<timestamp>/ directory.")],
    failures: Annotated[bool, typer.Option("--failures", help="Print failure_modes.md.")] = False,
    regenerate: Annotated[bool, typer.Option(help="Rebuild Markdown from JSON.")] = False,
) -> None:
    """Print (and optionally regenerate) the Markdown report for a run."""
    from finrl_eval.report import load_run, write_reports

    if not (run_dir / "summary.json").exists():
        typer.secho(f"{run_dir} is not a run directory (no summary.json)", fg="red")
        raise typer.Exit(2)
    if regenerate:
        summary, results = load_run(run_dir)
        write_reports(run_dir, summary, results)
    target = run_dir / ("failure_modes.md" if failures else "report.md")
    typer.echo(target.read_text())


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
