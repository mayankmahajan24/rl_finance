"""Ablation and per-trap credit: every step of the reference, and every planted problem, must count.

  per-trap credit  a gold-derived answer (everything planted, found exactly) scores best; dropping
                   any one planted item from it must lower the reward, or the verifier ignores it.
                   data_audit (required problems), anomaly_scoring (planted spikes, drops and the
                   first 60 days of level shifts), growth_thesis (unreliable airlines)
  step ablation    the reference with one step turned off must lose reward on every task where that
                   step's trap is planted. data_audit's six checks emit their own issue types, so a
                   step is turned off by removing its types from the reference's answer

Graded offline in a scratch copy of the container layout (JUDGE=keyword, no API key).

    python rl/harness/ablation.py --split bench
    python rl/harness/ablation.py --split bench --family data_audit --sample 2
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import tomllib

RL = pathlib.Path(__file__).resolve().parents[1]
# data_audit's reference checks (solutions/reference/audit.py) and the issue types each one reports
AUDIT_STEPS = {"1 duplicates": {"duplicate_rows"}, "2 ticket size": {"swapped_columns", "unit_scale"},
               "3 outages": {"outage"}, "4 date shift": {"date_shift"}, "5 ticker-wide breaks": {"ticker_remap"},
               "6 peer steps": {"series_swap", "double_count", "level_shift"}}
# anomaly_scoring's verifier labels the first 60 days of a planted level shift positive
SHIFT_DAYS = 60
GOLD_SCORER = """import argparse, json
from pathlib import Path
import pandas as pd
ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
df['anomaly_score'] = 0.0
for w in json.loads((Path(__file__).parent / 'windows.json').read_text()):
    m = (df.ticker == w['ticker']) & (df.source_id == w['source_id']) & df.date.between(w['start'], w['end'])
    df.loc[m, 'anomaly_score'] = 1.0
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[['date', 'ticker', 'source_id', 'anomaly_score']].to_csv(a.output, index=False)
"""


def layout(task: pathlib.Path) -> pathlib.Path:
    """A scratch /app with the task's data unpacked."""
    import gzip
    app = pathlib.Path(tempfile.mkdtemp(prefix=f"ablation-{task.name}-")) / "app"
    shutil.copytree(task / "environment" / "data", app / "data")
    for gz in (app / "data").glob("*.gz"):
        gz.with_suffix("").write_bytes(gzip.decompress(gz.read_bytes()))
        gz.unlink()
    (app / "output").mkdir()
    (app / "solution").mkdir()
    return app


def env(app: pathlib.Path, task: pathlib.Path) -> dict:
    e = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    # PYTHONDONTWRITEBYTECODE: the verifier runs inside the built task's tests/, and __pycache__ there changes its hash
    return dict(e, APP_DIR=str(app), TESTS_DIR=str(task / "tests"), LOGS_DIR=str(app.parent / "logs"), JUDGE="keyword",
                PYTHONDONTWRITEBYTECODE="1",
                PATH=str(pathlib.Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])


def grade(task: pathlib.Path, files: dict[str, str]) -> float:
    """The task's verifier on these files (paths under /app)."""
    app = layout(task)
    for rel, text in files.items():
        (app / rel).write_text(text)
    verifier = next(line.split()[1].split("/")[-1] for line in (task / "tests" / "test.sh").read_text().splitlines()
                    if line.startswith("python /tests/"))
    r = subprocess.run([sys.executable, verifier], cwd=task / "tests", env=env(app, task), capture_output=True, text=True)
    try:
        return float((app.parent / "logs" / "verifier" / "reward.txt").read_text())
    except FileNotFoundError:
        raise SystemExit(f"{task.name}: verifier failed: {r.stderr[-500:]}")
    finally:
        shutil.rmtree(app.parent, ignore_errors=True)


def reference_output(task: pathlib.Path) -> dict[str, str]:
    """What the task's reference solution writes to /app/output."""
    app = layout(task)
    shutil.copytree(task / "solution", app.parent / "solver")
    subprocess.run(["bash", str(app.parent / "solver" / "solve.sh")], cwd=app, env=env(app, task), check=True,
                   capture_output=True)
    out = {f"output/{p.name}": p.read_text() for p in (app / "output").iterdir()}
    shutil.rmtree(app.parent, ignore_errors=True)
    return out


def leave_one_out(task, items, answer) -> list[str]:
    """Problems where dropping one planted item from the gold answer doesn't lower the reward."""
    full = grade(task, answer(items))
    out = []
    for i, item in enumerate(items):
        r = grade(task, answer(items[:i] + items[i + 1:]))
        if r >= full:
            out.append(f"{task.name}: dropping planted {item} leaves the reward at {r:.3f} (all found: {full:.3f})")
    return out


def audit_planted(truth: dict) -> list[dict]:
    return [{k: v for k, v in x.items() if k != "origin"} for x in truth["required"]]


def audit_credit(task: pathlib.Path, truth: dict) -> list[str]:
    return leave_one_out(task, audit_planted(truth), lambda items: {"output/issues.json": json.dumps(items)})


def audit_ablation(task: pathlib.Path, truth: dict) -> list[str]:
    planted, out = audit_planted(truth), []
    ref = json.loads(reference_output(task)["output/issues.json"])
    full = grade(task, {"output/issues.json": json.dumps(ref)})
    for step, types in AUDIT_STEPS.items():
        if not any(x["type"] in types for x in planted):
            continue
        r = grade(task, {"output/issues.json": json.dumps([x for x in ref if x["type"] not in types])})
        if r >= full:
            out.append(f"{task.name}: turning off check {step} leaves the reference at {r:.3f} (full: {full:.3f})")
    return out


def anomaly_credit(task: pathlib.Path, truth: dict) -> list[str]:
    import pandas as pd
    windows = [dict(ticker=p["ticker"], source_id=p["source_id"], start=p["date"], end=p["date"]) for p in truth["points"]]
    windows += [dict(ticker=s["ticker"], source_id=s["source_id"], start=s["start"],
                     end=str((pd.Timestamp(s["start"]) + pd.Timedelta(days=SHIFT_DAYS - 1)).date())) for s in truth["shifts"]]
    return leave_one_out(task, windows, lambda ws: {"solution/score.py": GOLD_SCORER, "solution/windows.json": json.dumps(ws)})


def thesis_credit(task: pathlib.Path, truth: dict) -> list[str]:
    memo = reference_output(task)["output/memo.md"]
    return leave_one_out(task, truth["unreliable"], lambda u: {
        "output/answer.json": json.dumps({"fastest": truth["fastest"], "growth": truth["true_growth"], "unreliable": u}),
        "output/memo.md": memo})


CREDIT = {"data_audit": audit_credit, "anomaly_scoring": anomaly_credit, "growth_thesis": thesis_credit}
ABLATION = {"data_audit": audit_ablation}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="bench")
    ap.add_argument("--family", action="append", choices=sorted(CREDIT))
    ap.add_argument("--sample", type=int, help="tasks per family")
    a = ap.parse_args(argv)
    problems, done = [], {}
    for p in sorted((RL / "tasks" / a.split).glob("*/task.toml")):
        fam = tomllib.loads(p.read_text())["metadata"]["family"]
        if fam not in CREDIT or (a.family and fam not in a.family) or done.get(fam, 0) == a.sample:
            continue
        truth = json.loads((p.parent / "tests" / "ground_truth.json").read_text())
        if truth.get("control"):
            continue                          # nothing planted
        done[fam] = done.get(fam, 0) + 1
        found = CREDIT[fam](p.parent, truth) + (ABLATION[fam](p.parent, truth) if fam in ABLATION else [])
        print(f"{'ok  ' if not found else 'FAIL'} {p.parent.name}" + "".join(f"\n       {x}" for x in found), flush=True)
        problems += found
    if not done:
        raise SystemExit(f"no planted tasks of {sorted(CREDIT)} built under tasks/{a.split}/")
    if problems:
        raise SystemExit(f"{len(problems)} planted items or reference steps that don't count")
    print(f"every planted item and reference step counts ({sum(done.values())} tasks)")


if __name__ == "__main__":
    main()
