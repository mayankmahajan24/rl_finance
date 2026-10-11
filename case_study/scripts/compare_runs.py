"""Compare eval runs across models.

Reports the diagnostics that do NOT require gold, so a sweep is readable before
the human labels exist:

  - schema viability      did the model hold the format at all
  - self-consistency      same plan chosen under A/B and B/A ordering
  - position bias         rate of picking slot A (50% = unbiased)
  - frame stability       does goal_type / error_asymmetry flip with ordering
  - verbosity             issues per pointwise review (the precision proxy)
  - both-directions use   does it ever return the "over-" value, or only "under-"

Once gold exists, accuracy is layered on top; these stay as the sanity checks.

Usage:
    python scripts/compare_runs.py                 # every model under part2/runs/
    python scripts/compare_runs.py --models claude-haiku-4-5 claude-opus-5
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "part2" / "runs"

# fields with an "over-" failure as well as an "under-" one. A model that never
# returns the over- value is applying a checklist, not judging fit.
BOTH_WAYS = {
    "evidence_standard": "over_demanding",
    "explainability_fit": "over_demanded",
    "error_posture_fit": "too_conservative",
    "method_sophistication_fit": "too_sophisticated_for_audience",
}


LIVE = {p.stem for p in (ROOT / "part2" / "items").glob("*.json")}


def load(model: str, mode: str) -> dict | None:
    """Load a run, keeping only calls for items that still exist.

    Items can be cut between sweeps (the four context-flip items were). Comparing
    a 14-item run against a 10-item one would be meaningless, so every run is
    restricted to the live item set and the drop is reported."""
    p = RUNS / model / f"{mode}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    kept = [r for r in d["results"] if r["id"] in LIVE]
    d["dropped"] = len(d["results"]) - len(kept)
    d["results"] = kept
    d["n_errors"] = sum(1 for r in kept if r["status"] == "error")
    return d


def pairwise_stats(d: dict) -> dict:
    ok = [r for r in d["results"] if r["status"] == "ok"]
    by_item: dict[str, dict[str, str]] = {}
    for r in ok:
        by_item.setdefault(r["id"], {})[r["tag"]] = r["result"]

    consistent = flipped = 0
    frame_stable = frame_total = 0
    for iid, tags in by_item.items():
        if {"AB", "BA"} <= tags.keys():
            # AB winner 'A' == real plan A; BA winner 'A' == real plan B
            real_ab = tags["AB"]["winner"]
            real_ba = "B" if tags["BA"]["winner"] == "A" else "A"
            consistent += real_ab == real_ba
            flipped += real_ab != real_ba
            frame_total += 1
            frame_stable += (tags["AB"]["goal_type"] == tags["BA"]["goal_type"])

    picks_a = sum(1 for r in ok if r["result"]["winner"] == "A")
    n_dec = [len(r["result"]["decisive_tenets"]) for r in ok]
    return {
        "calls": len(d["results"]),
        "errors": d["n_errors"],
        "pairs": len(by_item),
        "consistent": consistent,
        "flipped": flipped,
        "slot_a_rate": picks_a / len(ok) if ok else 0,
        "frame_stable": f"{frame_stable}/{frame_total}" if frame_total else "-",
        "decisive_mean": sum(n_dec) / len(n_dec) if n_dec else 0,
        "conf_mean": sum(r["result"]["confidence"] for r in ok) / len(ok) if ok else 0,
    }


def pointwise_stats(d: dict) -> dict:
    ok = [r for r in d["results"] if r["status"] == "ok"]
    n_issues = [len(r["result"]["issues"]) for r in ok]
    blocking = [sum(1 for i in r["result"]["issues"] if i["severity"] == "blocking") for r in ok]
    over_used = {
        f: sum(1 for r in ok if r["result"].get(f) == v) for f, v in BOTH_WAYS.items()
    }
    cats = Counter(i["category"] for r in ok for i in r["result"]["issues"])
    return {
        "calls": len(d["results"]),
        "errors": d["n_errors"],
        "issues_mean": sum(n_issues) / len(n_issues) if n_issues else 0,
        "issues_max": max(n_issues) if n_issues else 0,
        "blocking_mean": sum(blocking) / len(blocking) if blocking else 0,
        "over_used": over_used,
        "top_cats": cats.most_common(5),
        "no_falsifier": sum(1 for r in ok
                            if "NONE" in r["result"]["what_would_falsify"].upper()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*")
    args = ap.parse_args()

    models = args.models or sorted(p.name for p in RUNS.iterdir() if p.is_dir())
    if not models:
        raise SystemExit("no runs under part2/runs/")

    fps = {}
    print("=" * 78)
    print("PAIRWISE")
    print(f"{'model':<22}{'calls':>6}{'err':>5}{'consist':>9}{'slotA':>7}"
          f"{'frame':>8}{'decis':>7}{'conf':>6}")
    print("-" * 78)
    incomplete = []
    for m in models:
        d = load(m, "pairwise")
        if not d:
            continue
        if d["n_errors"]:
            incomplete.append(f"{m} pairwise ({d['n_errors']} failed)")
            continue        # a partial run is not a result
        fps.setdefault(("pairwise", d["prompt_fingerprint"]), []).append(m)
        s = pairwise_stats(d)
        print(f"{m:<22}{len(d['results']):>6}{s['errors']:>5}"
              f"{s['consistent']}/{s['pairs']:<7}{s['slot_a_rate']:>6.0%}"
              f"{s['frame_stable']:>8}{s['decisive_mean']:>7.1f}{s['conf_mean']:>6.1f}")

    print()
    print("=" * 78)
    print("POINTWISE")
    print(f"{'model':<22}{'calls':>6}{'err':>5}{'issues':>8}{'max':>5}"
          f"{'blocking':>10}{'no-falsifier':>14}")
    print("-" * 78)
    for m in models:
        d = load(m, "pointwise")
        if not d:
            continue
        if d["n_errors"]:
            incomplete.append(f"{m} pointwise ({d['n_errors']} failed)")
            continue
        fps.setdefault(("pointwise", d["prompt_fingerprint"]), []).append(m)
        s = pointwise_stats(d)
        print(f"{m:<22}{len(d['results']):>6}{s['errors']:>5}{s['issues_mean']:>8.1f}"
              f"{s['issues_max']:>5}{s['blocking_mean']:>10.1f}{s['no_falsifier']:>14}")

    if incomplete:
        print()
        print("EXCLUDED — run incomplete, partial data is not a result:")
        for x in incomplete:
            print(f"   {x}   (retry with scripts/retry_eval.py --failed)")

    drops = {m: load(m, "pairwise")["dropped"] for m in models if load(m, "pairwise")}
    if any(drops.values()):
        print()
        print("Calls excluded (item no longer in the set):",
              ", ".join(f"{m}:{n}" for m, n in drops.items() if n))

    print()
    print("Both-directions fields — times the OVER- value was used")
    print("(a model that never returns these is applying a checklist, not judging fit)")
    for m in models:
        d = load(m, "pointwise")
        if not d:
            continue
        s = pointwise_stats(d)
        print(f"  {m:<22}" + "  ".join(f"{k.split('_')[0]}={v}" for k, v in s["over_used"].items()))

    print()
    print("Issue categories most raised")
    for m in models:
        d = load(m, "pointwise")
        if not d:
            continue
        s = pointwise_stats(d)
        print(f"  {m:<22}" + ", ".join(f"{c}:{n}" for c, n in s["top_cats"]))

    # comparability guard
    print()
    bad = [k for k, v in fps.items() if len(v) != len([m for m in models if load(m, k[0])])]
    if bad:
        print("!! PROMPT MISMATCH — these runs did not use the same instrument:")
        for (mode, fp), ms in fps.items():
            print(f"   {mode} {fp}: {', '.join(ms)}")
    else:
        print("Prompt fingerprints match across models — runs are comparable.")


if __name__ == "__main__":
    main()
