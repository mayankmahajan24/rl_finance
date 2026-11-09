"""Earnings-release dates: every 8-K a company filed under Item 2.02 (Results of Operations), from SEC submissions.

usage: python fetch_releases.py   (after fetch_xbrl.py, which caches sec/submissions/)
writes ../../raw/earnings_releases.csv: cik, filed, accession. kpi_nowcast dates each task the day
before the first of these after its target quarter ends, the first day the quarter's results could
be public. Some companies also file mid-quarter investor updates under Item 2.02; taking the first
filing after quarter end counts those as a report too.
"""
import csv
import glob
import json
import os

from fetch_xbrl import HERE, get

OUT = os.path.join(HERE, "..", "..", "raw", "earnings_releases.csv")
FILED_FROM, FILED_TO = "2014-01-01", "2019-06-30"


def releases(path):
    sub = json.load(open(path))
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        if f["filingTo"] >= FILED_FROM:
            blocks.append(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
    out = set()
    for b in blocks:
        for form, acc, filed, items in zip(b["form"], b["accessionNumber"], b["filingDate"], b["items"]):
            if form == "8-K" and "2.02" in items.split(",") and FILED_FROM <= filed <= FILED_TO:
                out.add((int(sub["cik"]), filed, acc))
    return out


def main():
    rows = set()
    for path in sorted(glob.glob(os.path.join(HERE, "sec", "submissions", "CIK*.json"))):
        rows |= releases(path)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cik", "filed", "accession"])
        w.writerows(sorted(rows))
    print(f"{len(rows)} releases -> {OUT}")


if __name__ == "__main__":
    main()
