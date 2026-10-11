"""Context-sensitivity test — does the discriminator apply tenet 2?

Each flip item is the SAME seed and the SAME two plans as its base, presented
under a different firm. Only the context changed, so:

  - `plan_implied_asker` should stay the SAME (the plan did not change). Drift
    means the model is reading the stated context back into the plan rather than
    reading the plan.
  - `fits_firm` MAY move, since the firm did change.
  - `preference` may or may not move. Whether it *should* is gold's call; what
    this script measures is whether the model is capable of moving at all.

A model that never changes its preference across a flip is not applying tenet 2 —
it is scoring plans in the abstract, whatever its raw accuracy.

Usage:  python scripts/flip_test.py [--models ...]
"""

from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "part2" / "runs"


def firm_class(s: str) -> str:
    """Coarse bucket for an implied-asker phrase. Paraphrase ("quant firm" vs
    "quant shop") must not count as drift; a systematic->fundamental change must."""
    s = s.lower()
    if any(w in s for w in ("systematic", "quant", "hft", "high-frequency", "factor")):
        return "systematic"
    if any(w in s for w in ("concentrated", "long-only", "fundamental", "event-driven",
                            "value", "discretionary")):
        return "fundamental"
    return "other"


def real_pick(res: dict, tag: str) -> str:
    """Winner in terms of the ORIGINAL slot, undoing the BA swap."""
    w = res["winner"]
    return w if tag == "AB" else ("B" if w == "A" else "A")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*")
    args = ap.parse_args()

    ctx = json.loads((ROOT / "part2" / "contexts.json").read_text())
    flips = {k: v for k, v in ctx["flips"].items() if not k.startswith("_")}
    if not flips:
        raise SystemExit("no flip items defined in contexts.json")

    models = args.models or sorted(p.name for p in RUNS.iterdir() if p.is_dir())

    for m in models:
        pw = RUNS / m / "pairwise.json"
        pt = RUNS / m / "pointwise.json"
        if not pw.exists():
            continue
        P = {(r["id"], r["tag"]): r["result"]
             for r in json.loads(pw.read_text())["results"] if r["status"] == "ok"}
        Q = {(r["id"], r["tag"]): r["result"]
             for r in json.loads(pt.read_text())["results"] if r["status"] == "ok"} \
            if pt.exists() else {}

        print("=" * 74)
        print(f"{m}")
        print("=" * 74)
        print(f"{'flip':>6} {'base firm':>12} {'flip firm':>12}  {'pref base':>10} "
              f"{'pref flip':>10}  moved")
        print("-" * 74)
        moved = comparable = 0
        for fid, spec in sorted(flips.items()):
            base = spec["base"]
            pb = [real_pick(P[(base, t)], t) for t in ("AB", "BA") if (base, t) in P]
            pf = [real_pick(P[(fid, t)], t) for t in ("AB", "BA") if (fid, t) in P]
            if not pb or not pf:
                print(f"{fid:>6}  (missing calls)")
                continue
            # only compare where the model was self-consistent on both
            if len(set(pb)) != 1 or len(set(pf)) != 1:
                print(f"{fid:>6} {'':>12} {spec['firm']:>12}  "
                      f"{'/'.join(pb):>10} {'/'.join(pf):>10}  inconsistent")
                continue
            comparable += 1
            b, f = pb[0], pf[0]
            moved += b != f
            print(f"{fid:>6} {ctx['assignment'][base]:>12} {spec['firm']:>12}  "
                  f"{b:>10} {f:>10}  {'YES' if b != f else 'no'}")

        print(f"\n  preference moved on {moved}/{comparable} comparable flips")
        if comparable and moved == 0:
            print("  -> never moved. Whether it SHOULD move is gold's call, but a model")
            print("     that cannot move on any flip is not weighing firm fit at all.")

        # implied-asker drift: the plan did not change, so this should not either
        if Q:
            print(f"\n  {'flip':>6}  implied-asker drift (plan unchanged, so should be stable)")
            drift = 0
            for fid, spec in sorted(flips.items()):
                base = spec["base"]
                for slot in ("A", "B"):
                    kb, kf = (base, slot), (fid, slot)
                    if kb in Q and kf in Q:
                        a, b = Q[kb]["plan_implied_asker"], Q[kf]["plan_implied_asker"]
                        ca, cb = firm_class(a), firm_class(b)
                        if ca != cb:
                            drift += 1
                            print(f"  {fid:>6}{slot}  {ca} -> {cb}")
                            print(f"  {'':>9} base: {a[:60]}")
                            print(f"  {'':>9} flip: {b[:60]}")
            n = 2 * len(flips)
            print(f"  -> firm-type drift on {drift}/{n} plan readings"
                  + ("  (reading the context into the plan)" if drift else
                     "  (stable — reading the plan, not the context)"))
        print()


if __name__ == "__main__":
    main()
