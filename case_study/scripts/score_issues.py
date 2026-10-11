"""Pointwise recall / precision — the semantic half of SCORING.md.

Matching is semantic, never string comparison: a model can surface gold's issue
in completely different words, and Part 1 showed models raise legitimate issues
gold never listed. So a scorer model buckets each issue against the classified
gold from split_gold.py.

  Recall    = blocking gold issues surfaced / blocking gold issues
  Precision = (matched + real_unlisted) / all issues raised

Four buckets per model issue:

  matched          semantically the same concern as a gold issue
  real_unlisted    not in gold, but a legitimate concern -> counts as REAL
  manufactured     not in gold and not legitimate
  contradicts_gold matches something gold explicitly ruled OUT ("the objection
                   that N is too small does not apply"). Counted as manufactured
                   and reported separately: it is the sharpest available evidence
                   of the Part 1 failure, since the expert pre-rejected it in writing.

Two isolation properties:
  - the scorer is never told which model produced a review, so it cannot favour one
  - it sees the plan and the firm context, without which "is this objection
    legitimate?" is not answerable

Usage:
    python scripts/score_issues.py                       # all models
    python scripts/score_issues.py --models claude-haiku-4-5
    python scripts/score_issues.py --report              # re-print, no API
"""

from __future__ import annotations

import argparse
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "part2" / "runs"
ITEMS = ROOT / "part2" / "items"
GOLD_ISSUES = ROOT / "part2" / "gold" / "_issues.json"

SYSTEM = """You are adjudicating a review of a research plan against a senior reviewer's own
written critique of that same plan. You are the scorer, not the reviewer.

You get: the firm context, the seed question, the plan, the reviewer's classified issues
(the gold), and a list of issues some evaluator raised. Do two jobs.

JOB 1 — For each GOLD BLOCKING issue, decide whether the evaluator surfaced it.
Semantic match, not wording. The evaluator may phrase it completely differently, fold it
into a broader point, or reach it from another direction; all of those count as surfaced.
It does NOT count if the evaluator merely touches the same topic without making the
reviewer's actual objection. State the evaluator issue index that surfaced it, or null.

JOB 2 — Put every evaluator issue in exactly one bucket:

- "matched"          — the same concern as one of the gold issues (blocking OR secondary).
- "real_unlisted"    — not in gold, but a legitimate concern about THIS plan that a desk
                       would take seriously. Be willing to use this: the reviewer did not
                       claim to be exhaustive, and a sharp point they missed is still real.
- "manufactured"     — not legitimate here. This is the canonical-objection failure: a
                       standard concern (survivorship, sample size, look-ahead, confounders,
                       overfitting) recited without checking whether it bites on this plan
                       and this data. ALSO use this when `why_it_applies_here` is generic —
                       when the justification would read identically against any plan in
                       this asset class, the objection was not earned, even if the concern
                       is real in the abstract.
- "contradicts_gold" — it raises an objection the reviewer EXPLICITLY ruled out (the gold
                       items labelled anti_objection). This is the strongest bucket: the
                       reviewer considered exactly this and said in writing that it does
                       not apply here.

Judge against this plan, this data and this firm. A concern that is textbook-correct in
general but inert here is manufactured. When genuinely torn between real_unlisted and
manufactured, choose real_unlisted and set `uncertain` true — those escalate to a human."""

USER = """FIRM CONTEXT
{context}

SEED QUESTION
{seed}

THE PLAN
{plan}

THE REVIEWER'S CRITIQUE (gold)
{gold}

ISSUES RAISED BY AN EVALUATOR ({n} of them)
{issues}

Do both jobs. Cover every gold blocking issue and every one of the {n} evaluator issues."""

SCHEMA = {
    "type": "object",
    "properties": {
        "gold_recall": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gold_ref": {"type": "string"},
                    "surfaced": {"type": "boolean"},
                    "by_issue": {"type": ["integer", "null"]},
                    "note": {"type": "string"},
                },
                "required": ["gold_ref", "surfaced", "by_issue", "note"],
                "additionalProperties": False,
            },
        },
        "issue_buckets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idx": {"type": "integer"},
                    "bucket": {
                        "type": "string",
                        "enum": ["matched", "real_unlisted", "manufactured", "contradicts_gold"],
                    },
                    "uncertain": {"type": "boolean"},
                    "why": {"type": "string"},
                },
                "required": ["idx", "bucket", "uncertain", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["gold_recall", "issue_buckets"],
    "additionalProperties": False,
}


def fmt_gold(rows: list[dict]) -> str:
    out = []
    for r in rows:
        tag = {"blocking": "BLOCKING", "secondary": "secondary",
               "anti_objection": "EXPLICITLY RULED OUT BY THE REVIEWER",
               "praise": "praise (not an issue)"}[r["label"]]
        out.append(f"[{r['label']}#{r['n']}] ({tag})\n{r['text']}")
    return "\n\n".join(out)


def fmt_issues(issues: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] severity={x['severity']} category={x['category']}\n"
        f"    summary: {x['summary']}\n"
        f"    why_it_applies_here: {x['why_it_applies_here']}\n"
        f"    what_breaks: {x['what_breaks']}"
        for i, x in enumerate(issues)
    )


def report(models: list[str]) -> None:
    path = ROOT / "part2" / "runs" / "_issue_scores.json"
    if not path.exists():
        raise SystemExit("no scores yet — run without --report")
    data = json.loads(path.read_text())
    gold = json.loads(GOLD_ISSUES.read_text())["items"]
    n_block = sum(1 for it in gold.values() for s in ("A", "B")
                  for r in it[s] if r["label"] == "blocking")

    print("=" * 78)
    print(f"POINTWISE RECALL — blocking gold issues surfaced (denominator {n_block})")
    print("=" * 78)
    print(f"{'model':<22}{'recall':>14}{'issues raised':>16}{'per review':>13}")
    print("-" * 78)
    rows = {}
    for m in models:
        d = data.get(m)
        if not d:
            continue
        sur = sum(1 for r in d["recall"] if r["surfaced"])
        tot = len(d["recall"])
        nb = len(d["buckets"])
        rows[m] = d
        print(f"{m:<22}{f'{sur}/{tot} ({sur/tot:.0%})':>14}{nb:>16}{nb/20:>13.1f}")

    print()
    print("=" * 78)
    print("POINTWISE PRECISION — of everything raised, how much was real")
    print("=" * 78)
    print(f"{'model':<22}{'precision band':>16}{'matched':>10}{'real-unl':>10}"
          f"{'manufact':>10}{'CONTRA':>9}{'uncert':>8}")
    print("-" * 78)
    for m, d in rows.items():
        c = {k: 0 for k in ("matched", "real_unlisted", "manufactured", "contradicts_gold")}
        unc = 0
        for b in d["buckets"]:
            c[b["bucket"]] += 1
            unc += b.get("uncertain", False) and b["bucket"] == "real_unlisted"
        n = sum(c.values())
        real = c["matched"] + c["real_unlisted"]
        hi, lo = (real / n, (real - unc) / n) if n else (0, 0)
        print(f"{m:<22}{f'{lo:.0%} - {hi:.0%}':>16}{c['matched']:>10}"
              f"{c['real_unlisted']:>10}{c['manufactured']:>10}"
              f"{c['contradicts_gold']:>9}{unc:>8}")
    print()
    print("=" * 78)
    print("COMBINED — does anything order all four models?")
    print("=" * 78)
    print(f"{'model':<22}{'recall':>10}{'precision':>18}{'F1 band':>18}"
          f"{'manufactured':>14}")
    print("-" * 78)
    for m, d in rows.items():
        c = {k: 0 for k in ("matched", "real_unlisted", "manufactured", "contradicts_gold")}
        unc = 0
        for b in d["buckets"]:
            c[b["bucket"]] += 1
            unc += b.get("uncertain", False) and b["bucket"] == "real_unlisted"
        n = sum(c.values())
        real = c["matched"] + c["real_unlisted"]
        rec = sum(1 for r in d["recall"] if r["surfaced"]) / len(d["recall"])
        f1 = lambda p: 2 * rec * p / (rec + p) if rec + p else 0
        hi, lo = real / n, (real - unc) / n
        bad = c["manufactured"] + c["contradicts_gold"]
        print(f"{m:<22}{rec:>9.0%}{f'{lo:.0%} - {hi:.0%}':>18}"
              f"{f'{f1(lo):.2f} - {f1(hi):.2f}':>18}{bad:>14}")
    print("\nF1 is the standard way to combine these. Read whether it actually ranks the")
    print("models, or whether raising far more issues buys enough recall to offset the")
    print("precision it costs.")
    print("\nprecision = (matched + real_unlisted) / all raised.")
    print("The scorer was told to choose real_unlisted when torn and flag `uncertain`, so the")
    print("upper bound counts those as real and the LOWER bound counts them as manufactured.")
    print("Report the band: the point estimate is an artifact of that tie-breaking rule.")
    print("CONTRA = raised an objection the reviewer explicitly ruled out in writing.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*")
    ap.add_argument("--scorer", default="claude-opus-5")
    ap.add_argument("--workers", type=int, default=4)
    # Haiku emits up to 90 issues in one review; the scorer must bucket every one,
    # and Opus 5 thinks by default, so thinking tokens share this budget.
    ap.add_argument("--max-tokens", type=int, default=48000)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    models = args.models or sorted(p.name for p in RUNS.iterdir()
                                   if p.is_dir() and (p / "pointwise.json").exists())
    if args.report:
        return report(models)

    import anthropic
    import run_eval as R

    gold = json.loads(GOLD_ISSUES.read_text())["items"]
    items = {p.stem: json.loads(p.read_text()) for p in ITEMS.glob("*.json")}
    client = anthropic.Anthropic()
    out_path = ROOT / "part2" / "runs" / "_issue_scores.json"
    store = json.loads(out_path.read_text()) if out_path.exists() else {}

    for m in models:
        d = json.loads((RUNS / m / "pointwise.json").read_text())
        jobs = [r for r in d["results"]
                if r["status"] == "ok" and r["id"] in gold]

        def one(r):
            it, slot = r["id"], r["tag"]
            issues = r["result"]["issues"]
            res, _ = R.call(
                client, args.scorer, SYSTEM,
                USER.format(context=items[it]["context"], seed=items[it]["seed"],
                            plan=items[it][f"plan_{slot}"],
                            gold=fmt_gold(gold[it][slot]),
                            issues=fmt_issues(issues), n=len(issues)),
                SCHEMA, args.max_tokens)
            print(f"  {it:>4} {slot}  {len(issues):>3} issues -> "
                  f"{sum(1 for x in res['gold_recall'] if x['surfaced'])} gold surfaced")
            return it, slot, res, len(issues)

        print(f"{m} · scoring {len(jobs)} reviews with {args.scorer}")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            done = list(pool.map(one, jobs))

        recall, buckets = [], []
        for it, slot, res, n in done:
            blocking = [r for r in gold[it][slot] if r["label"] == "blocking"]
            seen = {x["gold_ref"]: x for x in res["gold_recall"]}
            for b in blocking:
                k = f"blocking#{b['n']}"
                hit = seen.get(k) or seen.get(str(b["n"])) or {}
                recall.append({"item": it, "slot": slot, "n": b["n"],
                               "gist": b["gist"], "surfaced": bool(hit.get("surfaced"))})
            for x in res["issue_buckets"]:
                buckets.append({"item": it, "slot": slot, **x})
        store[m] = {"scorer": args.scorer, "recall": recall, "buckets": buckets}
        out_path.write_text(json.dumps(store, indent=2) + "\n")
        print(f"  -> {out_path.relative_to(ROOT)}\n")

    report(models)


if __name__ == "__main__":
    main()
