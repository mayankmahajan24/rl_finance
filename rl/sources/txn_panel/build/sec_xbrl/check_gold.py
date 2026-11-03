"""Consistency checks on the gold table.

1. Four first-reported quarters sum to the full year as first reported (direct-Q4 years only;
   derived Q4s satisfy this by construction).
2. Year-over-year growth on a consistent basis: flags |YoY| > 15% for a human look.
   Basis: a 2018 quarter is compared with the prior year's latest (restated) value, earlier
   quarters with the prior year's first-reported value.
"""
import csv, os, sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_gold import facts_for  # noqa: E402
from series import SERIES  # noqa: E402

q = defaultdict(dict)
for r in csv.DictReader(open("gold/kpi_quarterly.csv")):
    q[r["series"]][r["period_end"]] = r


def near(a, b, tol_days=10):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= tol_days


print("== 1. quarters sum to full year (first reported)")
bad = 0
for s in SERIES:
    fys = [r for r in facts_for(s) if r["kind"] == "FY"]
    first_fy = {}
    for r in sorted(fys, key=lambda r: r["filed"]):
        first_fy.setdefault(r["end"], r)
    for end, fy in sorted(first_fy.items()):
        ends = sorted(e for e in q[s["id"]] if date.fromisoformat(fy["start"]) < date.fromisoformat(e) <= date.fromisoformat(end))
        if len(ends) != 4 or any(q[s["id"]][e]["first_derived"] == "True" for e in ends):
            continue
        tot = sum(float(q[s["id"]][e]["first_value"]) for e in ends)
        diff = tot / fy["value_musd"] - 1
        if abs(diff) > 0.002:
            bad += 1
            print(f"  {s['id']} FY ending {end}: quarters {tot:,.0f} vs FY {fy['value_musd']:,.0f} ({diff:+.2%})")
print(f"  {bad} mismatches")

print("== 2. YoY growth outside ±15%")
for sid, rows in sorted(q.items()):
    ends = sorted(rows)
    for e in ends:
        prior = [p for p in ends if near(p, str(date.fromisoformat(e).replace(year=date.fromisoformat(e).year - 1)), 10)]
        if not prior or e < "2015":
            continue
        p = rows[prior[0]]
        base = float(p["latest_value"]) if e >= "2018" else float(p["first_value"])
        g = float(rows[e]["first_value"]) / base - 1
        if abs(g) > 0.15:
            print(f"  {sid} {e}: {g:+.1%}  ({p['first_value']} -> {rows[e]['first_value']})")
