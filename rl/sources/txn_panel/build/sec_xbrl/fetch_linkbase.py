"""Fetch each filing's schema, presentation and label files, to tell income-statement lines apart.

usage: python fetch_linkbase.py <cik> [<cik> ...]   (after fetch_xbrl.py)
writes sec/linkbase/<accession>/{schema.xsd, pre.xml, lab.xml} for every filing in sec/facts/CIK<cik>.csv.
The schema names each presentation role ("Statement - Consolidated Statements of Operations"), the
presentation file lists the concepts under each role, and the label file gives each concept its
line-item label as the company printed it.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_xbrl import HERE, get  # noqa: E402


def main(cik):
    filings = {}
    for r in csv.DictReader(open(f"{HERE}/sec/facts/CIK{cik}.csv")):
        filings[r["accession"]] = r["source"].rsplit("/", 1)[0]
    for acc, base in sorted(filings.items()):
        out = f"{HERE}/sec/linkbase/{acc}"
        if os.path.exists(f"{out}/lab.xml"):
            continue
        names = [i["name"] for i in json.loads(get(base + "/index.json"))["directory"]["item"]]
        pick = {"schema.xsd": [n for n in names if n.endswith(".xsd")],
                "pre.xml": [n for n in names if n.endswith("_pre.xml")],
                "lab.xml": [n for n in names if n.endswith("_lab.xml")]}
        if not all(pick.values()):
            print(cik, acc, "missing", [k for k, v in pick.items() if not v], file=sys.stderr)
            continue
        os.makedirs(out, exist_ok=True)
        for local, cands in pick.items():
            open(f"{out}/{local}", "wb").write(get(f"{base}/{cands[0]}", binary=True))
        print(cik, acc, "ok", file=sys.stderr)


if __name__ == "__main__":
    for c in sys.argv[1:]:
        main(int(c))
