"""Replay the case-study baseline runs through the rl/ graders and check they
reproduce rl/sources/research_design_case/baseline_runs/GRADED.md.

No API calls. Model responses come from baseline_runs/<model>/{pairwise,pointwise}.json;
the scorer's semantic decisions come from the cached baseline_runs/_issue_scores.json.
Writes one record per (model, task) to rl/runs/research_design/baseline/<model>.jsonl,
which also gives every graded task a baseline reward from four models.

Checks, and exits non-zero if any fail:
  - prompt fingerprints in the task tree match the fingerprints recorded on the runs
  - pairwise strong-item accuracy matches GRADED.md
  - review recall and manufactured-per-review match GRADED.md

Usage:
    python rl/replay_research_design.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib import RL, iter_tasks, write_json  # noqa: E402
from graders import pairwise_pick, review_issues  # noqa: E402

RUNS = RL / "sources" / "research_design_case" / "baseline_runs"
OUT = RL / "runs" / "research_design" / "baseline"

# baseline_runs/GRADED.md: strong-item pairwise accuracy, review recall, manufactured per review
EXPECTED = {
    "claude-haiku-4-5": (0.58, 0.53, 14.3),
    "claude-sonnet-5": (0.67, 0.29, 0.1),
    "claude-opus-4-8": (0.67, 0.33, 0.3),
    "claude-opus-5": (0.75, 0.62, 0.2),
}


def main() -> None:
    tasks = {t["id"]: (d, t) for d, t in iter_tasks()}
    scores = json.loads((RUNS / "_issue_scores.json").read_text())
    failures, summary = [], {}

    for model, (exp_strong, exp_recall, exp_manuf) in EXPECTED.items():
        records = []
        pw = json.loads((RUNS / model / "pairwise.json").read_text())
        pt = json.loads((RUNS / model / "pointwise.json").read_text())

        # ---- instrument identity ------------------------------------------
        for run, prefix in ((pw, "rd-funding-"), (pt, "rd-review-")):
            fps = {t["prompt"]["fingerprint"] for tid, (_, t) in tasks.items() if tid.startswith(prefix)}
            if fps != {run["prompt_fingerprint"]}:
                failures.append(f"{model}: {prefix} fingerprint {fps} != run {run['prompt_fingerprint']}")

        # ---- compare mode -------------------------------------------------
        by_item: dict[str, dict] = {}
        for r in pw["results"]:
            if r["status"] == "ok":
                by_item.setdefault(r["id"], {})[r["tag"]] = r["result"]
        strong_hits = strong_n = 0
        for sid, resp in by_item.items():
            d, t = tasks[f"rd-funding-{sid}"]
            if t["status"] != "graded":
                continue
            gold = json.loads((d / "grader" / "gold.json").read_text())
            g = pairwise_pick.grade(gold, resp)
            records.append({"task": t["id"], "model": model, "responses": resp, **g})
            if gold["preference_strength"] == "strong":
                strong_hits += sum(g["breakdown"]["correct"].values())
                strong_n += len(resp)

        # ---- review mode --------------------------------------------------
        s = scores[model]
        surfaced = blocking = bad = reviews = 0
        for r in pt["results"]:
            if r["status"] != "ok":
                continue
            tid = f"rd-review-{r['id']}-{r['tag']}"
            d, t = tasks[tid]
            if t["status"] != "graded":
                continue
            key = (r["id"], r["tag"])
            cached = {
                "gold_recall": [{"gold_ref": f"blocking#{x['n']}", "surfaced": x["surfaced"]}
                                for x in s["recall"] if (x["item"], x["slot"]) == key],
                "issue_buckets": [x for x in s["buckets"] if (x["item"], x["slot"]) == key],
            }
            gold = json.loads((d / "grader" / "gold.json").read_text())
            g = review_issues.grade(gold, cached, **t["grader"]["params"])
            records.append({"task": tid, "model": model, "response": r["result"],
                            "scorer": {"model": s["scorer"], "cached": True, **cached}, **g})
            b = g["breakdown"]
            surfaced += b["blocking_surfaced"]
            blocking += b["blocking_total"]
            bad += b["manufactured"] + b["contradicts_gold"]
            reviews += 1

        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{model}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n"
                                                    for x in records))
        got = (strong_hits / strong_n, surfaced / blocking, bad / reviews)
        summary[model] = {"strong_pairwise_accuracy": round(got[0], 3),
                          "review_recall": round(got[1], 3),
                          "manufactured_per_review": round(got[2], 2),
                          "mean_review_reward": round(sum(x["reward"] for x in records
                                                          if x["task"].startswith("rd-review"))
                                                      / reviews, 3),
                          "n_records": len(records)}
        for name, g_, e in zip(("strong accuracy", "recall", "manufactured/review"), got,
                               (exp_strong, exp_recall, exp_manuf)):
            # GRADED.md rounds half-up to its printed precision (0.15 -> 0.2)
            if abs(g_ - e) > (0.051 if name == "manufactured/review" else 0.005):
                failures.append(f"{model}: {name} {g_:.3f} != GRADED.md {e}")

    write_json(OUT / "summary.json", summary)
    print(f"{'model':<20}{'strong acc':>12}{'recall':>9}{'manuf/rev':>11}{'review reward':>15}")
    for m, v in summary.items():
        print(f"{m:<20}{v['strong_pairwise_accuracy']:>12.0%}{v['review_recall']:>9.0%}"
              f"{v['manufactured_per_review']:>11.2f}{v['mean_review_reward']:>15.2f}")
    if failures:
        print("\nMISMATCHES\n  " + "\n  ".join(failures))
        raise SystemExit(1)
    print("\nAll fingerprints and GRADED.md numbers reproduced.")


if __name__ == "__main__":
    main()
