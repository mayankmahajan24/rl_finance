"""List candidate KPI line items in a company's extracted facts.

usage: python inspect_facts.py <cik> [keyword ...]
Shows each distinct (concept, dims) with how many quarterly (≈3-month) facts it has and the
years it spans, so a series can be mapped to the exact line item that is its KPI.
"""
import csv, sys
from collections import defaultdict
from datetime import date

cik, kws = sys.argv[1], [k.lower() for k in sys.argv[2:]]
agg = defaultdict(lambda: {"n": 0, "years": set(), "ex": None})
for r in csv.DictReader(open(f"sec/facts/CIK{cik}.csv")):
    if not r["start"] or not r["end"]:
        continue
    d = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
    if not 80 <= d <= 100:
        continue
    key = (r["concept"], r["dims"])
    text = (r["concept"] + " " + r["dims"]).lower()
    if kws and not any(k in text for k in kws):
        continue
    a = agg[key]; a["n"] += 1; a["years"].add(r["end"][:4]); a["ex"] = (r["end"], r["value"])
for (c, dm), a in sorted(agg.items(), key=lambda kv: -kv[1]["n"]):
    if dm.count("=") > 2:
        continue
    print(f"{a['n']:4d} {min(a['years'])}-{max(a['years'])}  {c}  [{dm}]  e.g. {a['ex'][0]} {float(a['ex'][1])/1e6:,.0f}M")
