"""`finrl-eval` command line interface.

This slice lists suites and prints the runnable names. It does not score them.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from finrl_eval import __version__
from finrl_eval.suites import live_suites, planned

app = typer.Typer(
    help="Finance RL: list task suites and the names a later runner can score.",
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
    """List available suites and their FORMAT mirror counts."""
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
                "description": cls.spec.description,
            }
        )
    payload = {
        "suites": suites,
        "planned": planned(),
        "format_mirrors": {
            **mirror_counts,
            "note": (
                "FORMAT task folders under rl/roles/; "
                "rebuilt by scripts/build_instrumentation_suites.py. "
                "Status is needs_rubric until a grader is attached."
            ),
        },
    }
    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.secho(f"finrl-eval {__version__}", bold=True)
    typer.echo("\nSuites:")
    for s in suites:
        typer.echo(f"  {s['name']:<14} {s['title']}  [v{s['version']}, {s['n_samples']} samples]")
        typer.echo(f"  {'':<14} tasks: {', '.join(s['tasks'])}")
    typer.echo("\nPlanned (extension points, not runnable):")
    for name, desc in planned().items():
        typer.echo(f"  {name:<14} {desc}")
    typer.echo("\nFORMAT mirrors (rl/roles/, produce, needs_rubric):")
    for line in mirror_lines:
        typer.echo(line)


@app.command("runnable")
def runnable_cmd() -> None:
    """Print live suite names, one per line, in registry order."""
    for name in live_suites():
        typer.echo(name)


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
