"""Console entry points for the rl/ scripts (pyproject.toml [project.scripts]).

`pip install -e .` from the checkout puts rl-build, rl-check, rl-export and rl-run on PATH, bound to whichever Python
installed them, so they work from any directory and never depend on a venv's absolute paths. Each
runs the script of the same checkout with its own arguments: `rl-build panel --split bench` is
`python rl/build.py panel --split bench`.
"""

from __future__ import annotations

import pathlib
import runpy
import sys

RL = pathlib.Path(__file__).resolve().parent / "rl"


def _run(script: str) -> None:
    path = RL / script
    if not path.exists():
        raise SystemExit(f"{path} not found: install from a checkout with `pip install -e .`")
    sys.argv[0] = str(path)
    runpy.run_path(str(path), run_name="__main__")


def build() -> None:
    _run("build.py")


def check() -> None:
    _run("splits/check.py")


def export() -> None:
    _run("export.py")


def run() -> None:
    _run("harness/run_api.py")
