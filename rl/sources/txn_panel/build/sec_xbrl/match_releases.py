"""When each filed figure was first public: find it in the earnings release that came before its filing.

usage: python match_releases.py   (after fetch_releases.py and assemble_statements.py / assemble_gold.py)
writes ../../raw/release_matches.csv: one row per figure found in a press release, keyed by the
filing that later carried it (accession, concept, member, end, value) with the release's date and
accession. A figure is searched for in every Item 2.02 release filed after the filing's own period
ended and on or before the filing itself (a 10-Q or 10-K repeats figures the release already
published, restated comparatives included). Figures are matched by value, as the release would
print them (whole millions, or thousands, or millions to one or two decimals), not by parsing each company's table
layout. A fourth quarter derived as full year minus nine months may differ from the release's own
fourth-quarter figure by rounding, so for those the search allows one unit in the last printed digit,
and value_released records the figure the release printed. A KPI that sums two lines counts as public
once both lines were. A figure not found keeps its filing date: either the release didn't carry it
(many segment and product splits) or printed a different number.
"""
import csv
import gzip
import io
import os
import re
from collections import defaultdict

from fetch_releases import release_text

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "..", "raw")
GRADER_ONLY = os.path.join(HERE, "..", "..", "grader_only")
OUT = os.path.join(RAW, "release_matches.csv")


def printed(v: float) -> list[str]:
    """The ways a release could print a value given in USD millions: a whole number of millions as it
    is; a value with thousands as thousands, or millions to one or two decimals."""
    v = abs(v)
    if abs(v - round(v)) < 1e-9:
        out = {f"{v:,.0f}"}
    else:
        out = {f"{v * 1000:,.0f}", f"{v:,.1f}", f"{v:,.2f}"}
    # short numbers turn up by chance (a percentage, a guidance range): a false match would date a figure
    # before it was public, a missed one only dates it later, so only 4+ digit prints count
    return [s for s in out if len(s.replace(",", "").replace(".", "")) >= 4]


def found(text: str, v: float, derived: bool = False) -> float | None:
    """The value as the release printed it, or None."""
    tries = [v] + ([v + d for d in (-1, 1, -0.1, 0.1, -0.001, 0.001)] if derived else [])
    for x in tries:
        if any(re.search(r"(?<![\d,.])" + re.escape(s) + r"(?![\d,]|\.\d)", text) for s in printed(x)):
            return round(x, 3)
    return None


def main():
    releases = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(RAW, "earnings_releases.csv"))):
        releases[int(r["cik"])].append((r["filed"], r["accession"]))
    rows = list(csv.DictReader(io.TextIOWrapper(gzip.open(os.path.join(RAW, "statement_facts.csv.gz")), "utf-8")))
    cik_of = {r["accession"]: int(r["cik"]) for r in rows}
    kpi = list(csv.DictReader(open(os.path.join(GRADER_ONLY, "kpi_facts.csv"))))
    facts = [(r["accession"], r["concept"], r["member"], r["end"], float(r["value"]), r["filed"], r["derived"] == "True")
             for r in rows if r["unit"] == "USD"]
    facts += [(r["accession"], r["concept"], "", r["end"], float(r["value_musd"]), r["filed"], r["derived"] == "True")
              for r in kpi if " + " not in r["concept"]]
    period_end = defaultdict(str)          # a filing's own period: the latest quarter it reports
    for acc, _, _, end, *_ in facts:
        period_end[acc] = max(period_end[acc], end)
    out, n, hits = [], 0, {}
    for acc, concept, member, end, value, filed, derived in facts:
        cik = cik_of.get(acc) or int(acc.split("-")[0])
        n += 1
        for rel in sorted(x for x in releases[cik] if period_end[acc] < x[0] <= filed):
            v = found(release_text(cik, rel[1]), value, derived)
            if v is not None:
                out.append([acc, concept, member, end, value, v, rel[0], rel[1]])
                hits[(acc, concept.split(":")[-1], member, end)] = (rel, v)
                break
    for r in kpi:                          # a KPI summed from two lines: public once both parts were
        if " + " not in r["concept"]:
            continue
        parts = [hits.get((r["accession"], c.strip().split(":")[-1], "", r["end"])) for c in r["concept"].split(" + ")]
        n += 1
        if all(parts):
            rel = max(p[0] for p in parts)
            out.append([r["accession"], r["concept"], "", r["end"], float(r["value_musd"]),
                        round(sum(p[1] for p in parts), 3), rel[0], rel[1]])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["accession", "concept", "member", "end", "value_musd", "value_released", "released", "release_accession"])
        w.writerows(sorted(set(map(tuple, out))))
    print(f"{len(out)} of {n} filed dollar figures found in an earlier press release -> {OUT}")


if __name__ == "__main__":
    main()
