"""Score eval runs against human gold — the deterministic half.

Everything here is exact comparison against a gold field. The semantic half
(recall/precision of pointwise issues against gold's prose critiques) needs a
judgment call per issue and lives in score_issues.py.

Scored only on items that have gold. The four context-flip items are excluded
automatically until their gold is filled, so partial gold never silently
shrinks the denominator without saying so.

Baselines matter more than the raw accuracy here. Gold prefers A on 6 of 10
items, so a model that always answers A scores 60% while discriminating
nothing. Every accuracy is printed against its majority-class baseline.

Usage:
    python scripts/score.py
    python scripts/score.py --models claude-haiku-4-5 claude-opus-5
"""

from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "part2" / "runs"
GOLD = ROOT / "part2" / "gold"

# SCORING.md tenet -> issue category map. Tenets 1 and 13 are carried by
# dedicated fields (goal_type, why_it_applies_here) and have no category, so
# a gold list naming them is only partially checkable here — reported, not hidden.
TENET_CATS = {
    2: {"firm_fit"}, 3: {"no_edge"}, 4: {"unnecessary_complexity"},
    5: {"proxy_substitution", "measure_validity"}, 6: {"horizon_mismatch"},
    7: {"evidence_standard", "evidence_hierarchy"}, 8: {"breadth"},
    9: {"sequencing"}, 10: {"human_oversight"}, 11: {"falsification"},
    12: {"invented_economics"},
}
UNMAPPABLE = {1, 13}


def load_gold() -> dict[str, dict]:
    out = {}
    for p in sorted(GOLD.glob("S*.json")):
        d = json.loads(p.read_text())
        if all(v in ("", [], None) for k, v in d.items() if not k.startswith("_")):
            continue                      # not yet filled
        out[p.stem] = d
    return out


def real_pick(res: dict, tag: str) -> str:
    """Winner in terms of the ORIGINAL slot, undoing the B/A swap."""
    w = res["winner"]
    return w if tag == "AB" else ("B" if w == "A" else "A")


def gold_tenets(s: str) -> set[int]:
    return {int(x) for x in str(s).replace(",", " ").split() if x.strip().isdigit()}


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*")
    args = ap.parse_args()

    gold = load_gold()
    if not gold:
        raise SystemExit("no gold filled in yet")
    models = args.models or sorted(p.name for p in RUNS.iterdir() if p.is_dir())

    scored = sorted(gold, key=lambda s: (s.endswith("F"), int(s[1:].rstrip("F"))))
    ungraded = sorted({p.stem for p in (ROOT / "part2" / "items").glob("*.json")} - set(gold))
    print(f"Scored on {len(scored)} items with gold: {', '.join(scored)}")
    if ungraded:
        print(f"NOT scored (gold empty): {', '.join(ungraded)}")

    # ---- baselines -------------------------------------------------------
    prefs = [gold[s]["preference"] for s in scored]
    base = max(prefs.count("A"), prefs.count("B")) / len(prefs)
    strong = [s for s in scored if gold[s]["preference_strength"] == "strong"]
    weak = [s for s in scored if gold[s]["preference_strength"] == "weak"]
    print(f"\nGold preference: A x{prefs.count('A')}, B x{prefs.count('B')}  "
          f"-> always-answer-A baseline = {base:.0%}")
    print(f"Strength: strong x{len(strong)}, weak x{len(weak)}")

    print("\n" + "=" * 76)
    print("PAIRWISE ACCURACY vs gold preference  (each item judged twice: A/B and B/A)")
    print("=" * 76)
    print(f"{'model':<20}{'all calls':>14}{'strong':>14}{'weak':>13}{'both-ways':>13}")
    print("-" * 76)
    pw_detail = {}
    for m in models:
        p = RUNS / m / "pairwise.json"
        if not p.exists():
            continue
        res = {(r["id"], r["tag"]): r["result"]
               for r in json.loads(p.read_text())["results"]
               if r["status"] == "ok" and r["id"] in gold}
        tot = cor = st = stn = wk = wkn = both = bothn = 0
        picks = {}
        for s in scored:
            g = gold[s]["preference"]
            got = [real_pick(res[(s, t)], t) for t in ("AB", "BA") if (s, t) in res]
            if not got:
                continue
            picks[s] = got
            for x in got:
                tot += 1
                cor += x == g
                if s in strong:
                    stn += 1; st += x == g
                else:
                    wkn += 1; wk += x == g
            if len(got) == 2:
                bothn += 1
                both += all(x == g for x in got)
        pw_detail[m] = picks
        print(f"{m:<20}{pct(cor, tot):>14}{pct(st, stn):>14}{pct(wk, wkn):>13}"
              f"{pct(both, bothn):>13}")
    def maj(items: list[str]) -> float:
        p = [gold[s]["preference"] for s in items]
        return max(p.count("A"), p.count("B")) / len(p) if p else 0

    print(f"{'--- always-A/B ---':<20}{base:>13.0%}{maj(strong):>13.0%}{maj(weak):>12.0%}")
    print("\nEach split carries its OWN majority baseline, and they differ sharply:")
    print(f"  strong items are {maj(strong):.0%} balanced, weak items {maj(weak):.0%} —")
    print("  so a weak-split score below that number is worse than answering blind.")
    print("\n'both-ways' = agreed with gold under BOTH orderings. This is the strict")
    print("read: an evaluator that only matches gold in one ordering matched by luck.")

    # ---- per-item agreement ---------------------------------------------
    print("\n" + "=" * 76)
    print("PER-ITEM  (gold pick, then each model's pick under A/B and B/A)")
    print("=" * 76)
    ms = [m for m in models if m in pw_detail]
    print(f"{'item':<6}{'gold':>5}{'str':>8}   " + "".join(f"{m.replace('claude-',''):<18}" for m in ms))
    print("-" * 76)
    for s in scored:
        g = gold[s]["preference"]
        row = f"{s:<6}{g:>5}{gold[s]['preference_strength']:>8}   "
        for m in ms:
            got = pw_detail[m].get(s, [])
            mark = "".join(x if x == g else x.lower() for x in got)
            ok = all(x == g for x in got) if got else None
            row += f"{mark + (' OK' if ok else ' xx' if got else ''):<18}"
        print(row)
    print("\nUppercase = matched gold, lowercase = did not. 'OK' only when both agree with gold.")

    # ---- frame accuracy --------------------------------------------------
    print("\n" + "=" * 76)
    print("FRAME ACCURACY  (goal_type and error_asymmetry vs gold)")
    print("=" * 76)
    print(f"{'model':<20}{'goal pairwise':>16}{'goal pointwise':>17}"
          f"{'asym pairwise':>16}{'asym pointwise':>16}")
    print("-" * 76)
    for m in models:
        cells = []
        for mode, fld in (("pairwise", "goal_type"), ("pointwise", "goal_type"),
                          ("pairwise", "error_asymmetry"), ("pointwise", "error_asymmetry")):
            p = RUNS / m / f"{mode}.json"
            if not p.exists():
                cells.append("-"); continue
            n = c = 0
            for r in json.loads(p.read_text())["results"]:
                if r["status"] != "ok" or r["id"] not in gold:
                    continue
                n += 1
                c += r["result"][fld] == gold[r["id"]][fld]
            cells.append(pct(c, n))
        print(f"{m:<20}{cells[0]:>16}{cells[1]:>17}{cells[2]:>16}{cells[3]:>16}")
    gt = [gold[s]["goal_type"] for s in scored]
    az = [gold[s]["error_asymmetry"] for s in scored]
    print(f"{'--- baseline ---':<20}"
          f"{max(gt.count(x) for x in set(gt)) / len(gt):>15.0%}"
          f"{'':>17}{max(az.count(x) for x in set(az)) / len(az):>15.0%}")

    # ---- error asymmetry, split by the item's true value -----------------
    print("\n" + "=" * 76)
    print("ERROR ASYMMETRY, split by the item's TRUE value")
    print("(SCORING.md: the pattern is the finding. A model that assumes one posture")
    print(" everywhere is right on the common class and wrong on the rest.)")
    print("=" * 76)
    kinds = sorted({gold[s]["error_asymmetry"] for s in scored})
    counts = {k: sum(1 for s in scored if gold[s]["error_asymmetry"] == k) for k in kinds}
    heads = [f"{k.replace('_dominant', '')} (n={counts[k]})" for k in kinds]
    print(f"{'model':<20}" + "".join(f"{h:>20}" for h in heads))
    print("-" * 76)
    for m in models:
        p = RUNS / m / "pointwise.json"
        if not p.exists():
            continue
        agg = {k: [0, 0] for k in kinds}
        for r in json.loads(p.read_text())["results"]:
            if r["status"] != "ok" or r["id"] not in gold:
                continue
            k = gold[r["id"]]["error_asymmetry"]
            agg[k][1] += 1
            agg[k][0] += r["result"]["error_asymmetry"] == k
        print(f"{m:<20}" + "".join(f"{pct(*agg[k]):>20}" for k in kinds))

    # ---- decisive tenets -------------------------------------------------
    print("\n" + "=" * 76)
    print("DECISIVE TENETS — did the model decide for gold's stated reason?")
    print("=" * 76)
    print("Gold names tenet numbers; the model returns issue categories. Compared via")
    print("the SCORING.md map. Tenets 1 and 13 have no category and are not checkable,")
    print("so this is a lower bound, and the uncheckable share is reported.")
    print(f"\n{'model':<20}{'hit >=1 gold tenet':>22}{'mean cats':>12}")
    print("-" * 76)
    ncheck = sum(1 for s in scored if gold_tenets(gold[s]["decisive_tenets"]) - UNMAPPABLE)
    for m in models:
        p = RUNS / m / "pairwise.json"
        if not p.exists():
            continue
        hit = n = 0
        sizes = []
        for r in json.loads(p.read_text())["results"]:
            if r["status"] != "ok" or r["id"] not in gold:
                continue
            want = gold_tenets(gold[r["id"]]["decisive_tenets"]) - UNMAPPABLE
            if not want:
                continue
            cats = set(r["result"]["decisive_tenets"])
            sizes.append(len(cats))
            n += 1
            hit += any(cats & TENET_CATS.get(t, set()) for t in want)
        print(f"{m:<20}{pct(hit, n):>22}{sum(sizes) / len(sizes) if sizes else 0:>12.1f}")
    print(f"\n{ncheck}/{len(scored)} items have at least one checkable gold tenet.")


if __name__ == "__main__":
    main()
