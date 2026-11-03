"""Build the gold KPI table: one row per (series, fiscal quarter, filing that reported it).

Every value keeps its filing (accession, filed date, instance URL), so the table serves two uses:
  - gold target: the value as FIRST reported for the target quarter
  - point-in-time actuals feed: every value whose filing date is on or before a case's as-of date,
    including restated comparatives (e.g. 2017 restated under ASC 606 in 2018 filings)

Q4 is rarely tagged as a 3-month fact; it is derived as full year minus nine months from the
same basis and flagged `derived`.

usage: python assemble_gold.py            -> gold/kpi_facts.csv, gold/kpi_quarterly.csv
"""
import csv, os
from collections import defaultdict
from datetime import date

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from series import SERIES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def days(r):
    return (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days


def kind(d):
    if 80 <= d <= 100: return "Q"
    if 265 <= d <= 285: return "9M"
    if 355 <= d <= 375: return "FY"
    return None


def matches(r, sel):
    """sel = (concept, dims) or (concept, dims, last filing date the line item still means this KPI)."""
    concept, dims = sel[:2]
    if len(sel) > 2 and r["filed"] > sel[2]:
        return False
    if r["dims"] != dims:
        return False
    if concept.startswith("*:"):  # company extension: namespace changes with every filing date
        return r["concept"].rsplit(":", 1)[-1] == concept[2:]
    return r["concept"] == concept


def facts_for(s):
    """All matching facts for one series. A series lists variants (first match wins per filing and period);
    a variant sums one or more components, e.g. mainline + regional passenger revenue before 2018."""
    hits = defaultdict(lambda: defaultdict(dict))  # (acc, start, end) -> variant -> {component: row}
    ciks = {comp["cik"] for v in s["variants"] for comp in v}
    for cik in ciks:
        for r in csv.DictReader(open(f"{HERE}/sec/facts/CIK{cik}.csv")):
            if not r["start"] or kind(days(r)) is None:
                continue
            for vi, variant in enumerate(s["variants"]):
                for ci, comp in enumerate(variant):
                    if comp["cik"] == int(r["cik"]) and any(matches(r, sel) for sel in comp["selectors"]):
                        hits[(r["accession"], r["start"], r["end"])][vi].setdefault(ci, r)
    rows = []
    for (acc, st, en), by_variant in hits.items():
        full = [vi for vi in sorted(by_variant) if len(by_variant[vi]) == len(s["variants"][vi])]
        if not full:
            continue
        comps = by_variant[full[0]]
        any_r = next(iter(comps.values()))
        rows.append(dict(series=s["id"], start=st, end=en, kind=kind(days(any_r)), variant=full[0],
                         value_musd=round(sum(float(c["value"]) for c in comps.values()) / 1e6, 3),
                         concept=" + ".join(sorted({c["concept"] + (f"[{c['dims']}]" if c["dims"] else "") for c in comps.values()})),
                         form=any_r["form"], accession=acc, filed=any_r["filed"], source=any_r["source"]))
    return rows


def quarterize(rows):
    """3-month values per filing, plus Q4 = FY - 9M where FY and 9M come from the same reporting basis."""
    q = [dict(r, derived=False) for r in rows if r["kind"] == "Q"]
    have = {(r["end"], r["accession"]) for r in q}
    nine = [r for r in rows if r["kind"] == "9M"]
    for fy in (r for r in rows if r["kind"] == "FY"):
        # 9M for the same fiscal year: same start date; prefer the same filing, else the latest filed on or before the FY filing
        cands = [n for n in nine if n["start"] == fy["start"] and n["filed"] <= fy["filed"]]
        same = [n for n in cands if n["accession"] == fy["accession"]]
        # Mixing a later restated full year with the original nine months fabricates a Q4, so outside
        # the filing itself only derive from the 10-K that first reported the year.
        fy_end = date.fromisoformat(fy["end"])
        first_report = (date.fromisoformat(fy["filed"]) - fy_end).days < 150
        if not first_report:
            # a restated full year pairs only with nine months restated on the same basis: same line item,
            # published as a prior-year comparative in the following fiscal year
            cands = [n for n in cands if n["variant"] == fy["variant"]
                     and (date.fromisoformat(n["filed"]) - fy_end).days > 200]
        if not (same or cands):
            continue
        n9 = (same or sorted(cands, key=lambda n: n["filed"]))[-1]
        if (fy["end"], fy["accession"]) in have:
            continue
        q.append(dict(fy, start=n9["end"], kind="Q", derived=True,
                      value_musd=round(fy["value_musd"] - n9["value_musd"], 3),
                      concept=fy["concept"] + " (FY - 9M)"))
    return q


def main():
    os.makedirs(f"{HERE}/gold", exist_ok=True)
    allq = []
    for s in SERIES:
        q = quarterize(facts_for(s))
        for r in q:
            r["period_end"] = r["end"]
        allq += q
    allq.sort(key=lambda r: (r["series"], r["end"], r["filed"]))
    cols = ["series", "end", "start", "value_musd", "derived", "filed", "form", "accession", "concept", "source"]
    with open(f"{HERE}/gold/kpi_facts.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(allq)

    # one row per (series, quarter): first-reported value, latest-restated value, and how many filings reported it
    by = defaultdict(list)
    for r in allq:
        by[(r["series"], r["end"])].append(r)
    out = []
    for (sid, end), rs in sorted(by.items()):
        rs.sort(key=lambda r: (r["filed"], r["derived"]))
        first, last = rs[0], rs[-1]
        out.append(dict(series=sid, period_end=end, first_value=first["value_musd"], first_filed=first["filed"],
                        first_derived=first["derived"], first_source=first["source"],
                        latest_value=last["value_musd"], latest_filed=last["filed"], n_reports=len(rs),
                        restated_pct=round((last["value_musd"] / first["value_musd"] - 1) * 100, 2) if first["value_musd"] else None))
    with open(f"{HERE}/gold/kpi_quarterly.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(f"{len(allq)} facts, {len(out)} series-quarters")


if __name__ == "__main__":
    main()
