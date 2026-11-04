"""Calibration: how often models pass each task, how noisy the reward is, which tasks to keep.

`run` drives a calibration job through Harbor: every task of a split, k attempts per model, one job
folder per model under rl/runs/calibration/<split>/<run_id>/jobs/. Re-running resumes a job instead
of restarting it, and live runs need each family's instrument approved (rl/harness/approve.py). It
then imports the trials as run records (records.py) and writes the report.

`report` reads run records (Harbor imports, API runners, solvers) and writes stats.json and report.md:

  per task and model  attempts, errored share (errored trials are reported, never scored), mean
                      score, noise (std across attempts), pass rate at the family's threshold, and
                      pass@k / pass^k with 95% bootstrap intervals
  per split           model separation (paired bootstrap over tasks of the mean score difference)
                      and the difficulty distribution
  per task            keep / too_easy / too_hard / noisy / broken (the reference fails): a
                      recommendation only; dropping a task is an expert's call
  per family          noise floor, and the ceiling: the reference solution's score and the best
                      trial, with the family's note where its gold is known to be incomplete

Each family's scored metric and pass threshold are `calibration` in family.yaml.

    python rl/harness/calibrate.py run --split bench --model claude-opus-5-5 --model claude-sonnet-5-5 --k 5 \\
        -- --allow-agent-host api.anthropic.com --allow-environment-host deb.debian.org
    python rl/harness/calibrate.py report rl/runs/calibration/bench/<run_id>/records.jsonl rl/runs/solutions/bench.records.jsonl
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import random
import subprocess
import sys
import time
import tomllib
from collections import Counter, defaultdict
from math import comb

import yaml

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import instrument  # noqa: E402
import records  # noqa: E402

BOOT = 1000
NOISY = 0.25            # std across attempts above this: the task can't tell attempts apart
SOLVERS = ("reference", "oracle")


def pass_at_k(n, c, k):
    return float('nan') if n < k else 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    return float('nan') if n < k else comb(c, k) / comb(n, k)


def family_config(family: str) -> dict:
    f = RL / "families" / family / "family.yaml"
    cfg = (yaml.safe_load(f.read_text()) or {}).get("calibration", {}) if f.exists() else {}
    return {"metric": cfg.get("metric", "reward"), "pass": cfg.get("pass", 0.8), "note": cfg.get("ceiling_note")}


def score(r: dict, cfg: dict) -> float | None:
    v = r["rewards"].get(cfg["metric"])
    return None if v is None else float(v)


def interval(passes: list[bool], k: int, stat, rng: random.Random) -> list[float] | None:
    """95% bootstrap interval of pass@k or pass^k over a task's attempts."""
    n = len(passes)
    if n < k:
        return None
    draws = sorted(stat(n, sum(rng.choices(passes, k=n)), k) for _ in range(BOOT))
    return [round(draws[int(0.025 * BOOT)], 3), round(draws[int(0.975 * BOOT)], 3)]


def task_stats(rs: list[dict], cfg: dict, k: int, rng: random.Random) -> dict:
    scored = [s for s in (score(r, cfg) for r in rs if r["status"] == "ok") if s is not None]
    passes = [s >= cfg["pass"] for s in scored]
    n, c = len(scored), sum(passes)
    mean = sum(scored) / n if n else None
    std = (sum((s - mean) ** 2 for s in scored) / (n - 1)) ** 0.5 if n > 1 else None
    return {"attempts": len(rs), "errored": round(1 - n / len(rs), 3), "n": n,
            "mean": None if mean is None else round(mean, 4), "noise": None if std is None else round(std, 4),
            "pass_rate": round(c / n, 3) if n else None,
            f"pass@{k}": round(pass_at_k(n, c, k), 3) if n >= k else None,
            f"pass@{k}_ci": interval(passes, k, pass_at_k, rng),
            f"pass^{k}": round(pass_hat_k(n, c, k), 3) if n >= k else None,
            f"pass^{k}_ci": interval(passes, k, pass_hat_k, rng)}


def recommend(per_model: dict[str, dict], reference: float | None, cfg: dict) -> str:
    rates = [s["pass_rate"] for s in per_model.values() if s["pass_rate"] is not None]
    if reference is not None and reference < cfg["pass"]:
        return "broken"
    if not rates:
        return "no_data"
    if all(r == 1 for r in rates):
        return "too_easy"
    if all(r == 0 for r in rates):
        return "too_hard"
    if any(s["noise"] is not None and s["noise"] > NOISY for s in per_model.values()):
        return "noisy"
    return "keep"


def separation(means: dict[str, dict[str, float]], rng: random.Random) -> list[dict]:
    """Per model pair: mean score difference over shared tasks and its 95% paired-bootstrap interval."""
    out = []
    for a, b in itertools.combinations(sorted(means), 2):
        shared = sorted(set(means[a]) & set(means[b]))
        if len(shared) < 2:
            continue
        diffs = [means[a][t] - means[b][t] for t in shared]
        boot = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(BOOT))
        lo, hi = boot[int(0.025 * BOOT)], boot[int(0.975 * BOOT)]
        out.append({"a": a, "b": b, "tasks": len(shared), "mean_diff": round(sum(diffs) / len(diffs), 4),
                    "ci": [round(lo, 4), round(hi, 4)], "separated": lo > 0 or hi < 0})
    return out


def bucket(p: float | None) -> str:
    if p is None or p in (0, 1):
        return str(p)
    lo = min(int(p * 5), 4) * 20
    return f"{lo}-{lo + 20}%"


def report(recs: list[dict], k: int, seed: int = 0) -> dict:
    """Calibration statistics for one split's records (model runs plus any solver runs)."""
    rng = random.Random(seed)
    trials, refs = defaultdict(list), {}
    for r in recs:
        if (r.get("runner") or {}).get("agent") in SOLVERS:
            s = score(r, family_config(r["family"]))
            if s is not None and r["status"] == "ok":
                refs[r["task_id"]] = max(s, refs.get(r["task_id"], s))
        elif r.get("model"):
            trials[(r["family"], r["task_id"], r["model"])].append(r)
    tasks, means = {}, defaultdict(dict)
    for (fam, tid, model), rs in sorted(trials.items()):
        st = task_stats(rs, family_config(fam), k, rng)
        tasks.setdefault(tid, {"family": fam, "models": {}})["models"][model] = st
        if st["mean"] is not None:
            means[model][tid] = st["mean"]
    for tid, t in tasks.items():
        t["reference"] = refs.get(tid)
        t["recommendation"] = recommend(t["models"], t["reference"], family_config(t["family"]))
    families = {}
    for fam in sorted({t["family"] for t in tasks.values()}):
        cfg, ts = family_config(fam), [t for t in tasks.values() if t["family"] == fam]
        stats = [s for t in ts for s in t["models"].values()]
        ref = [t["reference"] for t in ts if t["reference"] is not None]
        best = [max(s["mean"] for s in t["models"].values() if s["mean"] is not None)
                for t in ts if any(s["mean"] is not None for s in t["models"].values())]
        noise = [s["noise"] for s in stats if s["noise"] is not None]
        families[fam] = {"metric": cfg["metric"], "pass": cfg["pass"], "tasks": len(ts),
                         "noise_floor": round(sum(noise) / len(noise), 4) if noise else None,
                         "ceiling_reference": round(sum(ref) / len(ref), 4) if ref else None,
                         "ceiling_best_trial": round(sum(best) / len(best), 4) if best else None,
                         "ceiling_note": cfg["note"],
                         "recommendations": dict(sorted(Counter(t["recommendation"] for t in ts).items())),
                         "difficulty": dict(sorted(Counter(bucket(s["pass_rate"]) for s in stats).items()))}
    return {"k": k, "families": families, "separation": separation(means, rng), "tasks": tasks}


def markdown(rep: dict, title: str) -> str:
    k = rep["k"]
    out = [f"# Calibration: {title}", "", f"k = {k}; scores are each family's `calibration.metric`.", "",
           "| Family | Metric (pass at) | Tasks | Noise floor | Ceiling: reference | Ceiling: best trial | Recommendations |",
           "|---|---|---|---|---|---|---|"]
    for fam, f in rep["families"].items():
        recs = ", ".join(f"{name} {n}" for name, n in f["recommendations"].items())
        out.append(f"| {fam} | {f['metric']} (≥ {f['pass']}) | {f['tasks']} | {f['noise_floor']} | "
                   f"{f['ceiling_reference']} | {f['ceiling_best_trial']} | {recs} |")
    notes = [f"- {fam}: {f['ceiling_note']}" for fam, f in rep["families"].items() if f["ceiling_note"]]
    out += (["", "Ceiling notes:", *notes] if notes else [])
    out += ["", "## Model separation", "", "| A | B | Tasks | Mean A − B | 95% CI | Separated |", "|---|---|---|---|---|---|"]
    out += [f"| {s['a']} | {s['b']} | {s['tasks']} | {s['mean_diff']} | {s['ci']} | {'yes' if s['separated'] else 'no'} |"
            for s in rep["separation"]]
    out += ["", "## Tasks", "",
            f"| Task | Family | Model | n | Errored | Mean | Noise | Pass rate | pass@{k} (95% CI) | pass^{k} | Recommendation |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for tid, t in sorted(rep["tasks"].items()):
        for model, s in sorted(t["models"].items()):
            out.append(f"| {tid} | {t['family']} | {model} | {s['n']} | {s['errored']} | {s['mean']} | {s['noise']} | "
                       f"{s['pass_rate']} | {s[f'pass@{k}']} {s[f'pass@{k}_ci'] or ''} | {s[f'pass^{k}']} | {t['recommendation']} |")
    return "\n".join(out) + "\n"


def write_report(files: list[pathlib.Path], k: int, out: pathlib.Path, title: str) -> None:
    rep = report(records.load(files), k)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(rep, indent=1) + "\n")
    (out / "report.md").write_text(markdown(rep, title))


def run(split: str, models: list[str], k: int, agent: str, run_id: str, harbor_args: list[str]) -> pathlib.Path:
    """Run, or resume, one Harbor job per model over the split; then import its trials as records."""
    tasks = RL / "tasks" / split
    for fam in sorted({tomllib.loads(p.read_text())["metadata"]["family"] for p in tasks.glob("*/task.toml")}):
        instrument.require_approved(fam)
    root = RL / "runs" / "calibration" / split / run_id
    for model in models:
        jobs = root / "jobs" / model
        started = sorted(jobs.iterdir()) if jobs.exists() else []
        cmd = ([sys.executable, "-m", "harbor.cli.main", "job", "resume", "-p", str(started[-1])] if started else
               [sys.executable, "-m", "harbor.cli.main", "run", "-p", str(tasks), "-a", agent, "-m", model,
                "-k", str(k), "-o", str(jobs), "-y", *harbor_args])
        print(" ".join(cmd), flush=True)
        subprocess.run(cmd)
    trials = sorted({p.parent for p in (root / "jobs").rglob("result.json") if (p.parent / "verifier").is_dir()})
    records.write(root / "records.jsonl", [records.from_harbor_trial(t) for t in trials])
    return root


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run or resume a calibration job through Harbor, then report")
    r.add_argument("--split", default="bench")
    r.add_argument("--model", action="append", required=True)
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--agent", default="claude-code")
    r.add_argument("--run-id", default=time.strftime("%Y%m%d"))
    r.add_argument("harbor_args", nargs=argparse.REMAINDER, help="after --: passed on to harbor run")
    p = sub.add_parser("report", help="report over run-record files")
    p.add_argument("files", nargs="+", type=pathlib.Path)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--out", type=pathlib.Path, help="default: the first file's folder")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        root = run(a.split, a.model, a.k, a.agent, a.run_id, [x for x in a.harbor_args if x != "--"])
        files = [root / "records.jsonl", *(RL / "runs" / "solutions").glob(f"{a.split}.records.jsonl")]
        write_report(files, a.k, root, f"{a.split} / {a.run_id}")
        out = root
    else:
        out = a.out or a.files[0].parent
        write_report(a.files, a.k, out, str(out))
    print(f"report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
