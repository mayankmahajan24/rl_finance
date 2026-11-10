"""Every income-statement line, with its segment, product and geographic splits, as each filing reported it.

usage: python assemble_statements.py   (after fetch_xbrl.py and fetch_linkbase.py)
writes ../../raw/statement_facts.csv.gz: one row per (company, line, split, quarter, filing that reported it).
kpi_nowcast tasks take their actuals.csv from it.

A line is a concept the filing's income statement presents (its "Statement" role for operations or
income; a combined "operations and comprehensive income" statement counts). Splits are the same
concepts tagged with one segment, product/service, geography or sales-channel member, wherever in the filing they
appear. Other dimensions (e.g. a subsidiary co-registrant) are left out.

Values are 3-month figures. Q4 is rarely tagged, so for dollar lines it is derived as full year minus
nine months, with the same pairing rule as assemble_gold.py; EPS and share counts can't be derived
that way, so their Q4 is present only when the filing tags it.
"""
import csv
import glob
import gzip
import io
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
XL = "{http://www.w3.org/1999/xlink}"
AXES = {"StatementBusinessSegmentsAxis": "segment", "ProductOrServiceAxis": "product",
        "StatementGeographicalAxis": "geography", "ContractWithCustomerSalesChannelAxis": "channel"}
LABEL_ROLES = ["http://www.xbrl.org/2003/role/terseLabel", "http://www.xbrl.org/2003/role/label"]


def local(c):
    return re.split(r"[:_]", c.split("#")[-1], maxsplit=1)[-1] if "#" in c else c.rsplit(":", 1)[-1]


def income_roles(xsd):
    roles = {}
    for el in ET.parse(xsd).getroot().iter():
        if el.tag.endswith("}roleType"):
            d = next((x.text or "" for x in el if x.tag.endswith("}definition")), "")
            roles[el.get("roleURI")] = d
    cands = {u: d for u, d in roles.items()
             if re.search(r"-\s*Statement\s*-", d) and re.search(r"operations|income|earnings", d, re.I)
             and not re.search(r"parenthetical|balance|cash flow|equity|stockholders|shareholders", d, re.I)}
    plain = {u: d for u, d in cands.items() if "comprehensive" not in d.lower()}
    return plain or cands


def role_concepts(pre, roles):
    out = set()
    for link in ET.parse(pre).getroot():
        if link.get(XL + "role") in roles:
            out |= {local(loc.get(XL + "href")) for loc in link if loc.tag.endswith("}loc")}
    return out


def labels(lab):
    root = ET.parse(lab).getroot()
    out = {}
    for link in root:
        locs = {l.get(XL + "label"): local(l.get(XL + "href")) for l in link if l.tag.endswith("}loc")}
        res = defaultdict(dict)
        for l in link:
            if l.tag.endswith("}label"):
                res[l.get(XL + "label")][l.get(XL + "role")] = (l.text or "").strip()
        for arc in link:
            if arc.tag.endswith("}labelArc") and arc.get(XL + "from") in locs:
                c = locs[arc.get(XL + "from")]
                for role in LABEL_ROLES:
                    if role in res.get(arc.get(XL + "to"), {}):
                        out.setdefault(c, {})[role] = res[arc.get(XL + "to")][role]
    return {c: next(v[r] for r in LABEL_ROLES if r in v) for c, v in out.items()}


def kind(r):
    d = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
    return "Q" if 80 <= d <= 100 else "9M" if 265 <= d <= 285 else "FY" if 355 <= d <= 375 else None


def split(dims):
    """'' -> ('', ''); one member on a kept axis -> (kind, member local name); anything else -> None."""
    if not dims:
        return "", ""
    parts = dims.split(";")
    if len(parts) != 1:
        return None
    axis, member = parts[0].split("=")
    k = next((v for a, v in AXES.items() if axis.endswith(a)), None)
    return (k, local(member)) if k else None


def quarterize(rows):
    q = [dict(r, derived=False) for r in rows if r["kind"] == "Q"]
    have = {(r["end"], r["accession"]) for r in q}
    nine = [r for r in rows if r["kind"] == "9M"]
    for fy in (r for r in rows if r["kind"] == "FY" and r["unit"] == "USD"):
        cands = [n for n in nine if n["start"] == fy["start"] and n["filed"] <= fy["filed"]]
        same = [n for n in cands if n["accession"] == fy["accession"]]
        fy_end = date.fromisoformat(fy["end"])
        if (date.fromisoformat(fy["filed"]) - fy_end).days >= 150:   # a restated full year: pair only with restated 9M
            cands = [n for n in cands if (date.fromisoformat(n["filed"]) - fy_end).days > 200]
        if not (same or cands) or (fy["end"], fy["accession"]) in have:
            continue
        n9 = (same or sorted(cands, key=lambda n: n["filed"]))[-1]
        q.append(dict(fy, start=n9["end"], kind="Q", derived=True, value=fy["value"] - n9["value"]))
    return q


def main():
    out = []
    for f in sorted(glob.glob(f"{HERE}/sec/facts/CIK*.csv")):
        by_acc = defaultdict(list)
        for r in csv.DictReader(open(f)):
            by_acc[r["accession"]].append(r)
        lines = defaultdict(list)              # (concept, split kind, member) -> rows across filings
        label_of = {}
        for acc, rs in by_acc.items():
            d = f"{HERE}/sec/linkbase/{acc}"
            if not os.path.exists(f"{d}/lab.xml"):
                continue
            roles = income_roles(f"{d}/schema.xsd")
            concepts = role_concepts(f"{d}/pre.xml", roles)
            lab = labels(f"{d}/lab.xml")
            for r in rs:
                c = local(r["concept"])
                sp = split(r["dims"])
                if c not in concepts or sp is None or not r["start"] or kind(r) is None:
                    continue
                unit = r["unit"].lower()
                unit = "USD/share" if "share" in unit and "usd" in unit else "USD" if "usd" in unit else \
                       "shares" if "share" in unit else r["unit"]
                label_of[c] = lab.get(c, c)
                if sp[1]:
                    label_of[sp[1]] = lab.get(sp[1], sp[1])
                lines[(c, *sp)].append(dict(cik=r["cik"], concept=c, split_kind=sp[0], member=sp[1], start=r["start"],
                                            end=r["end"], kind=kind(r), unit=unit, value=float(r["value"]),
                                            form=r["form"], accession=acc, filed=r["filed"],
                                            statement="; ".join(sorted(roles.values()))))
        for rows in lines.values():
            for r in quarterize(rows):
                scale = 1e6 if r["unit"] in ("USD", "shares") else 1
                out.append(dict(r, line=label_of[r["concept"]], member_label=label_of.get(r["member"], ""),
                                value=round(r["value"] / scale, 4)))
    out.sort(key=lambda r: (int(r["cik"]), r["concept"], r["split_kind"], r["member"], r["end"], r["filed"]))
    cols = ["cik", "line", "concept", "split_kind", "member", "member_label", "start", "end", "derived", "value",
            "unit", "filed", "form", "accession", "statement"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(out)
    with open(f"{HERE}/../../raw/statement_facts.csv.gz", "wb") as fh:
        fh.write(gzip.compress(buf.getvalue().encode(), mtime=0))
    print(len(out), "rows")


if __name__ == "__main__":
    main()
