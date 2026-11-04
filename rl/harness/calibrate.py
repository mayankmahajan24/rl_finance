"""Calibration: how often models pass each task, how noisy the reward is, which tasks to keep.

`run` drives a calibration job through Harbor: every task of a split, k attempts per model, one job
folder per model under rl/runs/calibration/<split>/<run_id>/jobs/. Re-running resumes a job instead
of restarting it; the run's arguments are pinned in its folder (args.json), and resuming with
different ones is refused. Live runs need each family's instrument approved (rl/harness/approve.py)
and a --budget: after each model's job its trials are imported as run records (records.py), and no
further job starts once their cost reaches the budget. A Harbor failure stops the run.

`report` reads run records (Harbor imports, API runners, solvers) and writes stats.json and report.md:

  per task and model  attempts, errored share (infrastructure errors and ungraded attempts are
                      reported, never scored; refusals, truncations, timeouts and unparseable
                      answers score 0), mean score, noise (std across attempts), pass rate at the
                      family's threshold, and pass@k / pass^k with 95% bootstrap intervals
  per family          model separation (paired bootstrap over the family's tasks of the mean score
                      difference), noise floor (mean noise), the difficulty distribution, and the
                      ceiling: the reference solution's score, the best model's mean and the best
                      single trial, with the family's note where its gold is known to be incomplete
  per task            keep / too_easy / too_hard / noisy (noise above NOISY times its family's
                      floor) / broken (the reference fails): a recommendation only; dropping a
                      task is an expert's call

Each family's scored metric and pass threshold are `calibration` in family.yaml.

    python rl/harness/calibrate.py run --split bench --model claude-opus-5-5 --model claude-sonnet-5-5 --k 5 --budget 200 \\
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
from collections import Counter, defaultdict
from math import comb

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import instrument  # noqa: E402
import local  # noqa: E402
import records  # noqa: E402
from lib import family  # noqa: E402

BOOT = 1000
NOISY = 2.0             # a task whose noise is above this many times its family's noise floor is flagged
SOLVERS = ("reference", "oracle")


def pass_at_k(n, c, k):
    return float('nan') if n < k else 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    return float('nan') if n < k else comb(c, k) / comb(n, k)


def family_config(family_id: str) -> dict:
    cfg = family(family_id).get("calibration", {})
    return {"metric": cfg.get("metric", "reward"), "pass": cfg.get("pass", 0.8), "note": cfg.get("ceiling_note")}


def score(r: dict, cfg: dict) -> float | None:
    return records.score(r, cfg["metric"])


def interval(passes: list[bool], k: int, stat, rng: random.Random) -> list[float] | None:
    """95% bootstrap interval of pass@k or pass^k over a task's attempts."""
    n = len(passes)
    if n < k:
        return None
    draws = sorted(stat(n, sum(rng.choices(passes, k=n)), k) for _ in range(BOOT))
    return [round(draws[int(0.025 * BOOT)], 3), round(draws[int(0.975 * BOOT)], 3)]


def task_stats(rs: list[dict], cfg: dict, k: int, rng: random.Random) -> dict:
    scored = [s for s in (score(r, cfg) for r in rs) if s is not None]
    passes = [s >= cfg["pass"] for s in scored]
    n, c = len(scored), sum(passes)
    mean = sum(scored) / n if n else None
    std = (sum((s - mean) ** 2 for s in scored) / (n - 1)) ** 0.5 if n > 1 else None
    return {"attempts": len(rs), "errored": round(1 - n / len(rs), 3), "n": n,
            "mean": None if mean is None else round(mean, 4), "best": max(scored) if scored else None,
            "noise": None if std is None else round(std, 4),
            "pass_rate": round(c / n, 3) if n else None,
            f"pass@{k}": round(pass_at_k(n, c, k), 3) if n >= k else None,
            f"pass@{k}_ci": interval(passes, k, pass_at_k, rng),
            f"pass^{k}": round(pass_hat_k(n, c, k), 3) if n >= k else None,
            f"pass^{k}_ci": interval(passes, k, pass_hat_k, rng)}


def recommend(per_model: dict[str, dict], reference: float | None, cfg: dict, floor: float | None) -> str:
    rates = [s["pass_rate"] for s in per_model.values() if s["pass_rate"] is not None]
    if reference is not None and reference < cfg["pass"]:
        return "broken"
    if not rates:
        return "no_data"
    if all(r == 1 for r in rates):
        return "too_easy"
    if all(r == 0 for r in rates):
        return "too_hard"
    if floor and any(s["noise"] is not None and s["noise"] > NOISY * floor for s in per_model.values()):
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
        key = (r["family"], r["task_id"])
        if (r.get("runner") or {}).get("agent") in SOLVERS:
            s = score(r, family_config(r["family"]))
            if s is not None and r["status"] == "ok":
                refs[key] = max(s, refs.get(key, s))
        elif r.get("model"):
            trials[(*key, r["model"])].append(r)
    tasks, means = {}, defaultdict(lambda: defaultdict(dict))
    for (fam, tid, model), rs in sorted(trials.items()):
        st = task_stats(rs, family_config(fam), k, rng)
        tasks.setdefault((fam, tid), {"family": fam, "task_id": tid, "models": {}})["models"][model] = st
        if st["mean"] is not None:
            means[fam][model][tid] = st["mean"]
    families = {}
    for fam in sorted({f for f, _ in tasks}):
        cfg, ts = family_config(fam), [t for (f, _), t in tasks.items() if f == fam]
        stats = [s for t in ts for s in t["models"].values()]
        noise = [s["noise"] for s in stats if s["noise"] is not None]
        floor = sum(noise) / len(noise) if noise else None
        for t in ts:
            t["reference"] = refs.get((fam, t["task_id"]))
            t["recommendation"] = recommend(t["models"], t["reference"], cfg, floor)
        ref = [t["reference"] for t in ts if t["reference"] is not None]
        scored = [[s for s in t["models"].values() if s["mean"] is not None] for t in ts]
        best_model = [max(s["mean"] for s in ss) for ss in scored if ss]
        best_trial = [max(s["best"] for s in ss) for ss in scored if ss]
        families[fam] = {"metric": cfg["metric"], "pass": cfg["pass"], "tasks": len(ts),
                         "noise_floor": round(floor, 4) if floor is not None else None,
                         "ceiling_reference": round(sum(ref) / len(ref), 4) if ref else None,
                         "ceiling_best_model": round(sum(best_model) / len(best_model), 4) if best_model else None,
                         "ceiling_best_trial": round(sum(best_trial) / len(best_trial), 4) if best_trial else None,
                         "ceiling_note": cfg["note"],
                         "recommendations": dict(sorted(Counter(t["recommendation"] for t in ts).items())),
                         "difficulty": dict(sorted(Counter(bucket(s["pass_rate"]) for s in stats).items())),
                         "separation": separation(means[fam], rng)}
    return {"k": k, "families": families, "tasks": {f"{f}/{t}": v for (f, t), v in sorted(tasks.items())}}


def markdown(rep: dict, title: str) -> str:
    k = rep["k"]
    out = [f"# Calibration: {title}", "", f"k = {k}; scores are each family's `calibration.metric`.", "",
           "| Family | Metric (pass at) | Tasks | Noise floor | Ceiling: reference | Ceiling: best model | "
           "Ceiling: best trial | Recommendations |",
           "|---|---|---|---|---|---|---|---|"]
    for fam, f in rep["families"].items():
        recs = ", ".join(f"{name} {n}" for name, n in f["recommendations"].items())
        out.append(f"| {fam} | {f['metric']} (≥ {f['pass']}) | {f['tasks']} | {f['noise_floor']} | "
                   f"{f['ceiling_reference']} | {f['ceiling_best_model']} | {f['ceiling_best_trial']} | {recs} |")
    notes = [f"- {fam}: {f['ceiling_note']}" for fam, f in rep["families"].items() if f["ceiling_note"]]
    out += (["", "Ceiling notes:", *notes] if notes else [])
    out += ["", "## Model separation", "", "| Family | A | B | Tasks | Mean A − B | 95% CI | Separated |",
            "|---|---|---|---|---|---|---|"]
    out += [f"| {fam} | {s['a']} | {s['b']} | {s['tasks']} | {s['mean_diff']} | {s['ci']} | {'yes' if s['separated'] else 'no'} |"
            for fam, f in rep["families"].items() for s in f["separation"]]
    out += ["", "## Tasks", "",
            f"| Task | Family | Model | n | Errored | Mean | Noise | Pass rate | pass@{k} (95% CI) | pass^{k} | Recommendation |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in rep["tasks"].values():
        for model, s in sorted(t["models"].items()):
            out.append(f"| {t['task_id']} | {t['family']} | {model} | {s['n']} | {s['errored']} | {s['mean']} | {s['noise']} | "
                       f"{s['pass_rate']} | {s[f'pass@{k}']} {s[f'pass@{k}_ci'] or ''} | {s[f'pass^{k}']} | {t['recommendation']} |")
    return "\n".join(out) + "\n"


def write_report(files: list[pathlib.Path], k: int, out: pathlib.Path, title: str) -> None:
    rep = report(records.load(files), k)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(rep, indent=1) + "\n")
    (out / "report.md").write_text(markdown(rep, title))


def run(split: str, models: list[str], k: int, agent: str, run_id: str, budget: float,
        harbor_args: list[str]) -> pathlib.Path:
    """Run, or resume, one Harbor job per model over the split, importing its trials as records after
    each; stops before the next model once the records' cost reaches `budget`."""
    for fam in sorted({m["family"] for _, m in local.tasks(split)}):
        instrument.require_approved(fam)
    root = RL / "runs" / "calibration" / split / run_id
    records.pin_args(root, {"split": split, "models": models, "k": k, "agent": agent, "harbor_args": harbor_args})
    for model in models:
        recs = records.import_harbor(root / "jobs", run_id)
        records.write(root / "records.jsonl", recs)
        spent = sum((r.get("cost_usd") or 0) + (r.get("judge_cost_usd") or 0) for r in recs)
        if spent >= budget:
            raise SystemExit(f"budget ${budget} reached (${spent:.2f} spent): not starting {model}")
        jobs = root / "jobs" / model
        started = sorted(jobs.iterdir()) if jobs.exists() else []
        cmd = ([sys.executable, "-m", "harbor.cli.main", "job", "resume", "-p", str(started[-1])] if started else
               [sys.executable, "-m", "harbor.cli.main", "run", "-p", str(RL / "tasks" / split), "-a", agent, "-m", model,
                "-k", str(k), "-o", str(jobs), "-y", *harbor_args])
        print(" ".join(cmd), flush=True)
        if subprocess.run(cmd).returncode:
            raise SystemExit(f"harbor failed on {model}; fix it and re-run the same command to resume")
    records.write(root / "records.jsonl", records.import_harbor(root / "jobs", run_id))
    return root


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run or resume a calibration job through Harbor, then report")
    r.add_argument("--split", default="bench")
    r.add_argument("--model", action="append", required=True)
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--agent", default="claude-code")
    r.add_argument("--budget", type=float, required=True,
                   help="USD; no further model's job starts once recorded cost reaches it (Harbor agents that "
                        "report no token usage count as free)")
    r.add_argument("--run-id", default=time.strftime("%Y%m%d"))
    r.add_argument("harbor_args", nargs=argparse.REMAINDER, help="after --: passed on to harbor run")
    p = sub.add_parser("report", help="report over run-record files")
    p.add_argument("files", nargs="+", type=pathlib.Path)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--out", type=pathlib.Path, help="default: the first file's folder")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        root = run(a.split, a.model, a.k, a.agent, a.run_id, a.budget, [x for x in a.harbor_args if x != "--"])
        files = [root / "records.jsonl", *(RL / "runs" / "solutions").glob(f"{a.split}.records.jsonl")]
        write_report(files, a.k, root, f"{a.split} / {a.run_id}")
        out = root
    else:
        out = a.out or a.files[0].parent
        write_report(a.files, a.k, out, str(out))
    print(f"report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
