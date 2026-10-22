"""Pull revenue-like XBRL facts (with dimensions) from every 10-Q/10-K a company filed in a date window.

usage: python fetch_xbrl.py <cik> [<cik> ...]
writes sec/facts/CIK<cik>.csv: one row per fact, keeping segment/product dimensions so
2018 ASC 606 disaggregations and segment KPIs are available, not just consolidated totals.
"""
import json, os, re, sys, time, urllib.request
import xml.etree.ElementTree as ET
import csv

UA = {"User-Agent": "research-analysis contact@example.com"}
HERE = os.path.dirname(os.path.abspath(__file__))
FILED_FROM, FILED_TO = "2014-01-01", "2019-06-30"
CONCEPT_RE = re.compile(r"(Revenue|Sales)", re.I)


def get(url, binary=False):
    for attempt in range(5):
        try:
            time.sleep(0.12)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                b = r.read()
                return b if binary else b.decode("utf-8", "replace")
        except Exception as e:  # SEC throttles with 403/429; back off
            time.sleep(2 ** attempt)
            err = e
    raise RuntimeError(f"{url}: {err}")


def filings(cik):
    sub = json.load(open(f"{HERE}/sec/submissions/CIK{cik:010d}.json"))
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        blocks.append(json.loads(get("https://data.sec.gov/submissions/" + f["name"])))
    out = []
    for b in blocks:
        for form, acc, filed, rep in zip(b["form"], b["accessionNumber"], b["filingDate"], b["reportDate"]):
            if form in ("10-Q", "10-K", "10-Q/A", "10-K/A") and FILED_FROM <= filed <= FILED_TO:
                out.append(dict(form=form, acc=acc, filed=filed, report=rep))
    return sorted({f["acc"]: f for f in out}.values(), key=lambda f: f["filed"])


def instance_url(cik, acc):
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    items = json.loads(get(base + "/index.json"))["directory"]["item"]
    names = [i["name"] for i in items]
    cands = [n for n in names if n.endswith("_htm.xml")] or \
            [n for n in names if n.endswith(".xml") and not re.search(r"(FilingSummary|_cal|_def|_lab|_pre|^R\d)", n)]
    return (base + "/" + cands[0]) if cands else None


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    ctx = {}
    for c in root.iter():
        if c.tag.endswith("}context"):
            per = {}
            for p in c.iter():
                t = p.tag.split("}")[-1]
                if t in ("startDate", "endDate", "instant"):
                    per[t] = (p.text or "").strip()
            dims = sorted(f"{m.get('dimension')}={(m.text or '').strip()}" for m in c.iter() if m.tag.endswith("}explicitMember"))
            ctx[c.get("id")] = (per.get("startDate", ""), per.get("endDate", per.get("instant", "")), ";".join(dims))
    for el in root:
        tag = el.tag
        if "}" not in tag or el.get("contextRef") is None:
            continue
        ns, local = tag[1:].split("}")
        if not CONCEPT_RE.search(local) or el.get("unitRef") is None:
            continue
        try:
            val = float(el.text)
        except (TypeError, ValueError):
            continue
        s, e, d = ctx.get(el.get("contextRef"), ("", "", ""))
        prefix = "us-gaap" if "fasb.org/us-gaap" in ns else ns.rstrip("/").split("/")[-2] if ns.count("/") > 3 else ns
        yield dict(concept=f"{prefix}:{local}", start=s, end=e, dims=d, value=val, unit=el.get("unitRef"))


def main(cik):
    os.makedirs(f"{HERE}/sec/facts", exist_ok=True)
    out = f"{HERE}/sec/facts/CIK{cik}.csv"
    rows = []
    for f in filings(cik):
        url = instance_url(cik, f["acc"])
        if not url:
            print(cik, f["acc"], "no instance", file=sys.stderr); continue
        n = 0
        for r in parse(get(url, binary=True)):
            r.update(cik=cik, form=f["form"], accession=f["acc"], filed=f["filed"], report_date=f["report"], source=url)
            rows.append(r); n += 1
        print(cik, f["form"], f["filed"], n, file=sys.stderr)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cik", "form", "accession", "filed", "report_date", "concept", "start", "end", "dims", "value", "unit", "source"])
        w.writeheader(); w.writerows(rows)
    print(cik, "rows", len(rows), "->", out)


if __name__ == "__main__":
    for c in sys.argv[1:]:
        main(int(c))
