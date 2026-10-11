"""Re-run selected eval calls and merge them into an existing run file.

Two uses:
  --failed          re-run every call that errored (usually truncation)
  --items S3 S7     re-run those items outright, e.g. after their context changed

Merging rather than overwriting matters: a full re-run would discard the calls
that already succeeded and cost the tokens again. The run's prompt/schema
fingerprints are re-checked, so a retry after an instrument change is refused
rather than silently mixing two instruments in one file.

Usage:
    python scripts/retry_eval.py --model claude-haiku-4-5 --mode pointwise --failed
    python scripts/retry_eval.py --model claude-haiku-4-5 --mode both --items S3
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor

import anthropic

import run_eval as R  # same directory

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "part2" / "runs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=["pairwise", "pointwise", "both"], default="both")
    ap.add_argument("--failed", action="store_true", help="re-run calls that errored")
    ap.add_argument("--items", nargs="*", default=[], help="re-run these items outright")
    ap.add_argument("--max-tokens", type=int, default=32000)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if not args.failed and not args.items:
        raise SystemExit("nothing to do: pass --failed and/or --items")

    items = {p.stem: json.loads(p.read_text())
             for p in (ROOT / "part2" / "items").glob("*.json")}
    client = anthropic.Anthropic()
    modes = ["pairwise", "pointwise"] if args.mode == "both" else [args.mode]

    for mode in modes:
        path = RUNS / args.model / f"{mode}.json"
        if not path.exists():
            print(f"  {mode}: no existing run, skipped")
            continue
        run = json.loads(path.read_text())
        system, template = R.load_prompt(mode)
        schema = R.PAIRWISE_SCHEMA if mode == "pairwise" else R.POINTWISE_SCHEMA

        # refuse to mix instruments
        if R.fingerprint(system, template) != run["prompt_fingerprint"]:
            print(f"  {mode}: PROMPT CHANGED since this run — refusing to merge. "
                  f"Re-run the whole sweep instead.")
            continue

        targets = set()
        if args.failed:
            targets |= {(r["id"], r["tag"]) for r in run["results"] if r["status"] == "error"}
        for iid in args.items:
            tags = ("AB", "BA") if mode == "pairwise" else ("A", "B")
            targets |= {(iid, t) for t in tags}
        targets = {t for t in targets if t[0] in items}
        if not targets:
            print(f"  {mode}: nothing to retry")
            continue

        def build(iid: str, tag: str) -> str:
            it = items[iid]
            if mode == "pairwise":
                a, b = ("plan_A", "plan_B") if tag == "AB" else ("plan_B", "plan_A")
                return template.format(context=it["context"], seed=it["seed"],
                                       plan_A=it[a], plan_B=it[b])
            return template.format(context=it["context"], seed=it["seed"],
                                   plan=it[f"plan_{tag}"])

        def run_one(t):
            iid, tag = t
            usage = {}
            try:
                out, usage = R.call(client, args.model, system, build(iid, tag),
                                    schema, args.max_tokens)
                status = "ok"
            except Exception as e:
                out, status = {"error": f"{type(e).__name__}: {e}"}, "error"
            print(f"  {mode:9s} {iid:>4} {tag:<3} {status}")
            return {"id": iid, "tag": tag, "status": status, "usage": usage, "result": out}

        print(f"{args.model} · {mode} · retrying {len(targets)} calls")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            fresh = list(pool.map(run_one, sorted(targets)))

        merged = {(r["id"], r["tag"]): r for r in run["results"]}
        merged.update({(r["id"], r["tag"]): r for r in fresh})
        results = sorted(merged.values(),
                         key=lambda r: (r["id"].endswith("F"),
                                        int(r["id"][1:].rstrip("F")), r["tag"]))

        run["results"] = results
        run["n_calls"] = len(results)
        run["n_errors"] = sum(1 for r in results if r["status"] == "error")
        run["tokens_in"] = sum(r["usage"].get("in", 0) for r in results)
        run["tokens_out"] = sum(r["usage"].get("out", 0) for r in results)
        run.setdefault("retries", []).append({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "calls": sorted(f"{i}{t}" for i, t in targets),
            "max_tokens": args.max_tokens,
        })
        path.write_text(json.dumps(run, indent=2) + "\n")
        print(f"  -> {path.relative_to(ROOT)}  ({run['n_calls']} calls, "
              f"{run['n_errors']} errors)")


if __name__ == "__main__":
    main()
