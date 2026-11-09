"""Build the kpi_nowcast tasks: nowcast a company's quarterly KPI from transaction data.

One agent run per task. The agent gets a sandbox with code execution (no internet) and files:
  transaction_panel.csv  every panel ticker of the companies in the case's split, truncated at the as-of date
  actuals.csv        every income-statement line the company reported, with its segment, product,
                     geography and sales-channel splits: only values filed on or before the as-of
                     date, including restated comparatives, so the agent sees what an analyst saw
and must choose the metric the sensors can track best (gold: the series' KPI), then return an
investor write-up plus a forecast JSON for that metric's target quarter.
  data_brief.md      a description of the panel and its known data issues
and must return an investor write-up plus a forecast JSON for the target quarter.

Each case exists three times: named; coded (tickers replaced with codes, dollars as reported); and
anon (codes, and every dollar series multiplied by one hidden factor per company). Each brief says
which it is. The score gaps measure how much recognising the name and remembering reported numbers
help.

Inputs (all from the txn_panel source, rl/sources/txn_panel/):
  raw/sensor_panel.csv.gz        the full panel (2014-01-01 .. 2018-12-31)
  assignment/brief.txt           description of the panel, rewritten from the original note
  annotations/company_facts.yaml reporting-basis and structural facts for the judge; low-signal series
  raw/statement_facts.csv.gz     income-statement lines with filing dates (built by build/sec_xbrl/)
  grader_only/kpi_facts.csv      gold KPI facts with filing dates (built by build/sec_xbrl/)
  grader_only/kpi_quarterly.csv  first-reported and restated value per quarter

Each task's split is its company's split (splits/txn_panel.yaml); the variants of a case
(series and quarter, metadata `case`) always share it. Retired cases (listed in that file) get split
"retired".

Tasks are written in Harbor layout to rl/tasks/<split>/<task_id>/ (families/_shared/harbor.py):
prompt/ holds the exact system and user messages the API runner (rl/harness/run_api.py) sends (the fingerprinted instrument), and
instruction.md the same text plus a note on where a Harbor agent finds the files and writes its
answer. solution/ holds the reference (the gold forecast, for Harbor's oracle) and the target the
naive solution (solutions/naive: last year's seasonal step) needs. What was built is recorded in
splits/manifests/kpi_nowcast.json.

usage: python rl/build.py kpi_nowcast   (or this file directly, with [--only UAL-2018Q4 ...])
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import pathlib
import re
import random
import shutil
import sys
from collections import defaultdict
from datetime import date, timedelta

RL = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "sources" / "txn_panel" / "build" / "sec_xbrl"))
import lib  # noqa: E402
import splits  # noqa: E402
from families._shared import harbor  # noqa: E402
from lib import TASKS, fingerprint  # noqa: E402
from series import SERIES  # noqa: E402
from sources.txn_panel import panel  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
PROMPTS = HERE / "prompts"
FIRM = (HERE.parent / "_shared" / "firm.md").read_text().rstrip("\n")
SEED = 20261018

# Harbor delivery: the API runner attaches the files and reads the final message; a Harbor agent
# finds the files under /app/data and leaves its final message in a file for the verifier.
HARBOR_NOTE = ("---\nThe attached files are in /app/data/. When you are done, write your final message "
               "(the brief, then the ```json block) to /app/output/answer.md, the methods note to /app/output/methods.md, and any charts to /app/output/figures/. The container's clock "
               "(`python`, `date`) reads the as-of date, {as_of}, which is also in $TASK_AS_OF.")
VARIANTS = ("named", "coded", "anon")
COPY_NOTE = {
    "named": "Company names, tickers and dollar figures are as they came. Nothing is disguised or rescaled.",
    "coded": ("Company and ticker names are replaced with codes. Dollar figures, in `amt` and in actuals.csv, are not "
              "rescaled, and transaction counts and dates are unchanged."),
    "anon": ("Company and ticker names are replaced with codes. Every dollar figure for a company or segment, in `amt` "
             "and in actuals.csv, is multiplied by one hidden factor between 0.35 and 2.8; each company or segment has "
             "its own. Transaction counts and dates are unchanged. Growth rates and the ratio of a company's `amt` to "
             "its actuals are therefore real. Dollar levels, average ticket size (`amt` / `ct`) and dollar comparisons "
             "between companies are not."),
}
PIP = " statsmodels==0.14.4 scikit-learn==1.5.2 matplotlib==3.9.2"   # agent tooling close to code execution's
REFERENCE = HERE / "solutions" / "reference"

# Target quarters. Calendar series end on the given dates; fiscal (Jan year-end) series use the
# fiscal quarter that ends nearest each anchor.
CALENDAR_TARGETS = ["2017-12-31", "2018-06-30", "2018-12-31"]
FISCAL_ANCHORS = ["2017-10-28", "2018-05-05", "2018-11-03"]
RELEASES = panel.HERE / "raw" / "earnings_releases.csv"   # 8-K Item 2.02 dates (build/sec_xbrl/fetch_releases.py)

# Disguised variants: statement labels that name a company, its brands or its segments, and their stand-ins.
# Longest first, so "Alaska Mainline" is replaced before "Alaska".
LABEL_SWAPS = [
    ("Nordstromrack.com/HauteLook", "Off-price online"), ("Nordstrom full-line stores", "Full-price stores"),
    ("Nordstrom.com", "Full-price online"), ("Nordstrom Rack", "Off-price stores"), ("Nordstrom", "Full-price"),
    ("Alaska Mainline", "Mainline"), ("Alaska Regional", "Regional"), ("Air Group Adjusted", "Adjusted total"),
    ("Mileage Plan", "Loyalty program"), ("Horizon", "Regional subsidiary"), ("Alaska", "Company"),
    ("TJX Canada", "Canada"), ("TJX Europe", "Europe"), ("TJX International", "International"),
    ("HomeGoods", "U.S. home"), ("Marmaxx", "U.S. apparel"), ("A.J. Wright", "Closed chain"), ("TJX", "Company"),
    ("Macy's", "Company"), ("Sephora", "Partner beauty"), ("Refinery", "Non-airline subsidiary"),
]
UNIT_LABEL = {"USD": "USD millions", "USD/share": "USD per share", "shares": "millions of shares"}
ACTUALS_COLS = ["period_start", "period_end", "line", "split", "value", "unit", "reported_on", "report",
                "q4_derived_from_annual"]


def disguise(label: str) -> str:
    for real, stand_in in LABEL_SWAPS:
        label = label.replace(real, stand_in)
    return label


def statement_feed(lines: list[dict], as_of: str, target_end: str) -> list[dict]:
    """actuals.csv rows: every line and split filed on or before the as-of date, for quarters before the target."""
    feed, seen = [], set()
    for r in sorted(lines, key=lambda r: (r["line"], r["split_kind"], r["member_label"], r["end"], r["filed"])):
        if r["filed"] > as_of or r["end"] >= target_end:
            continue
        key = (r["line"], r["split_kind"], r["member_label"], r["end"])
        member = r["member_label"].replace(" [Member]", "")
        feed.append({"period_start": str(d(r["start"]) + timedelta(days=1)) if r["derived"] == "True" else r["start"],
                     "period_end": r["end"], "line": r["line"],
                     "split": f"{r['split_kind']}: {member}" if r["split_kind"] else "",
                     "value": float(r["value"]), "unit": r["unit"], "reported_on": r["filed"],
                     "report": "later filing (comparative, may be restated)" if key in seen else "first report",
                     "q4_derived_from_annual": r["derived"]})
        seen.add(key)
    return feed


INDUSTRY_LABEL = {"airlines": "US airline", "department stores": "US department store / off-price retailer"}

# Grader-side facts per series (C5 reporting basis, C12 structural breaks) and the low-signal series,
# from the source's annotations. Data-quality facts (C4) are computed per case.
SERIES_FACTS, LOW_SIGNAL = panel.company_facts()


def known_facts(sid: str, as_of: str) -> list[str]:
    return [text for text, since in SERIES_FACTS.get(sid, []) if since is None or since <= as_of]


def restatement_facts(feed: list[dict], target_end: str) -> list[str]:
    """Basis changes visible in the case's own actuals feed: periods re-reported with a different value
    in a later filing dated on or before the as-of date. Says whether the target's same-quarter-last-year
    comparable is already on the new basis, since that decides which YoY comparisons are consistent."""
    first, last = {}, {}
    for r in sorted(feed, key=lambda r: r["reported_on"]):
        v = float(r["value_usd_m"])
        first.setdefault(r["period_end"], (v, r["reported_on"]))
        last[r["period_end"]] = (v, r["reported_on"])
    restated = {e: last[e][0] / first[e][0] - 1 for e in first if abs(last[e][0] / first[e][0] - 1) > 0.005}
    if not restated:
        return []
    lo, hi = min(restated.values()), max(restated.values())
    since = min(last[e][1] for e in restated)
    ly = [e for e in first if abs((d(e) - (d(target_end) - timedelta(days=364))).days) <= 10]
    comparable = ("is already in the feed on the new basis" if ly and ly[0] in restated
                  else "is NOT yet available on the new basis (only its original figure is in the feed)")
    return [f"Reporting basis changed: {len(restated)} earlier quarter(s) were re-reported in filings from {since} on, "
            f"by {lo:+.1%} to {hi:+.1%} (e.g. a new accounting standard or a segment redefinition). The target quarter "
            f"will be reported on the new basis; its same-quarter-last-year comparable {comparable}."]


def d(s: str) -> date:
    return date.fromisoformat(s)


def read_csv(p: pathlib.Path) -> list[dict]:
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def to_csv(rows: list[dict], cols: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def quarter_label(s: dict, end: str) -> str:
    e = d(end)
    if s["calendar"] == "calendar":
        return f"{e.year}Q{(e.month - 1) // 3 + 1}"
    fy = e.year - 1 if e.month <= 2 else e.year          # fiscal year named for the January it starts after
    q = {5: 1, 4: 1, 8: 2, 7: 2, 11: 3, 10: 3, 2: 4, 1: 4}[e.month]
    return f"FY{fy} Q{q}"


def anon_codes() -> tuple[dict, dict]:
    """Stable codes and scale factors for every sensor ticker and every series."""
    rng = random.Random(SEED)
    panel_tickers = sorted({r["ticker"] for r in read_csv(panel.RAW)})
    by_ind = defaultdict(list)
    for r in read_csv(panel.RAW):
        by_ind[r["industry"]].append(r["ticker"])
    codes, n = {}, defaultdict(int)
    for t in panel_tickers:
        ind = next(i for i, ts in by_ind.items() if t in ts)
        prefix = "AIR" if ind == "airlines" else "RET"
        n[prefix] += 1
    order = panel_tickers[:]
    rng.shuffle(order)
    n = defaultdict(int)
    for t in order:
        ind = next(i for i, ts in by_ind.items() if t in ts)
        prefix = "AIR" if ind == "airlines" else "RET"
        n[prefix] += 1
        codes[t] = f"{prefix}{n[prefix]:02d}"
    factor = {}
    for s in SERIES:  # one factor per company; the company's sensor tickers and KPI share it
        f = round(math.exp(rng.uniform(math.log(0.35), math.log(2.8))), 6)
        factor[s["id"]] = f
        for t in s["sensors"]:
            factor[t] = f
    for t in panel_tickers:
        factor.setdefault(t, round(math.exp(rng.uniform(math.log(0.35), math.log(2.8))), 6))
    return codes, factor


def sensor_facts(panel: list[dict], tickers: list[str], as_of: str) -> list[str]:
    """Automatically detected data-quality facts for the judge (C4). Not exhaustive."""
    facts = []
    by = defaultdict(dict)
    for r in panel:
        if r["ticker"] in tickers and r["date"] <= as_of:
            by[(r["ticker"], r["source_id"])][r["date"]] = float(r["amt"])
    first = min(min(v) for v in by.values())
    span = (d(as_of) - d(first)).days + 1
    yearly = defaultdict(lambda: defaultdict(float))
    for (t, src), series in by.items():
        missing = span - len(series)
        if missing > 30:
            facts.append(f"{t} source {src}: {missing} of {span} days missing")
        vals = sorted(series.items())
        spikes = 0
        for i in range(28, len(vals)):
            window = sorted(v for _, v in vals[i - 28:i])
            med = window[len(window) // 2]
            if med > 0 and (vals[i][1] > 4 * med or vals[i][1] < med / 4):
                spikes += 1
        if spikes >= 5:
            facts.append(f"{t} source {src}: {spikes} days more than 4x above or below the trailing 4-week median")
        for day, v in series.items():
            yearly[(t, src)][day[:4]] += v
    # level shifts: one source's year-over-year change departs from the other sources' median by >25 points
    for t in tickers:
        srcs = [s for (tt, s) in yearly if tt == t]
        years = sorted({y for s in srcs for y in yearly[(t, s)]})
        for y0, y1 in zip(years, years[1:]):
            g = {s: yearly[(t, s)].get(y1, 0) / yearly[(t, s)][y0] - 1 for s in srcs if yearly[(t, s)].get(y0)}
            for s, v in g.items():
                others = sorted(x for k, x in g.items() if k != s)
                if len(others) >= 2:
                    med = others[len(others) // 2]
                    if abs(v - med) > 0.25:
                        facts.append(f"{t} source {s}: spend changed {v:+.0%} {y0}->{y1} vs {med:+.0%} on the other sources (level shift / panel change)")
    return facts


def naive_forecast(feed: list[dict], target_end: str) -> float | None:
    """Last reported quarter x last year's seasonal step into the target quarter.

    The step (same quarter last year / prior quarter last year) uses both values as first reported
    in that year, so it never mixes an old and a restated basis even when the restated
    comparable for the target quarter isn't published yet."""
    first, latest = {}, {}
    for r in sorted(feed, key=lambda r: r["reported_on"]):
        first.setdefault(r["period_end"], float(r["value_usd_m"]))
        latest[r["period_end"]] = float(r["value_usd_m"])
    ends = sorted(latest)

    def year_ago(e):
        target = d(e) - timedelta(days=364)
        c = [x for x in ends if abs((d(x) - target).days) <= 10]
        return c[0] if c else None

    last = ends[-1]
    t_ly, l_ly = year_ago(target_end), year_ago(last)
    if not (t_ly and l_ly):
        return None
    return latest[last] * first[t_ly] / first[l_ly]


def reference_answer(gold: dict) -> str:
    """The reference's final message: the gold actual as the forecast."""
    a = gold["actual"]
    fc = {"target_period": gold["target_period"], "metric": gold["kpi"], "unit": gold["unit"], "point": a,
          "low": round(a * 0.98, 3), "high": round(a * 1.02, 3), "interval_level": 0.95,
          "metric_history": [{"period_end": e, "value": v[-1]} for e, v in gold["metric_history"].items()],
          "in_sample": [], "vs_consensus": "no_consensus"}
    return f"Reference forecast: {a} {gold['unit']} for {gold['target_period']}.\n\n```json\n{json.dumps(fc)}\n```\n"


def build(family_id: str, split_names: list[str] | None = None, n: int | None = None,
          controls: int | None = None, only: list[str] | None = None) -> None:
    """Build every case, each in its company's split (`split_names` doesn't narrow it); `only` rewrites
    just those cases and leaves the manifest alone."""
    if n is not None or controls is not None:
        raise SystemExit(f"{family_id} has one task per case: --n and --controls apply to generated families")
    fam = lib.family(family_id)
    prefix = fam["task_prefix"]

    rows_all = read_csv(panel.RAW)
    facts = read_csv(panel.GRADER_ONLY / "kpi_facts.csv")
    statements = defaultdict(list)
    for r in read_csv(panel.STATEMENTS):
        statements[int(r["cik"])].append(r)
    quarterly = {(r["series"], r["period_end"]): r for r in read_csv(panel.GRADER_ONLY / "kpi_quarterly.csv")}
    releases = defaultdict(list)
    for r in read_csv(RELEASES):
        releases[int(r["cik"])].append(r["filed"])
    panel_end = max(r["date"] for r in rows_all)
    q_first_filed = lambda sid, end: quarterly[(sid, end)]["first_filed"]
    brief = panel.BRIEF.read_text()
    system_t = (PROMPTS / "system.md").read_text().strip()
    user_t = (PROMPTS / "user.md").read_text().strip()
    codes, factor = anon_codes()
    retired = splits.retired("txn_panel", "kpi_nowcast")

    if not only:   # a full build replaces every task of the family; --only rewrites just those cases
        for old in TASKS.glob(f"*/{prefix}-*"):
            shutil.rmtree(old)
    built = {}
    for s in SERIES:
        company_id = panel.company_of_series(s["id"])
        split = splits.split_of("txn_panel", company_id)
        peers = splits.companies("txn_panel", split)     # a task only ever sees its own split's companies
        peer_sensors = set(panel.sensors_of(peers))
        ends = sorted({e for (sid, e) in quarterly if sid == s["id"]})
        if s["calendar"] == "calendar":
            targets = [e for e in CALENDAR_TARGETS if e in ends]
        else:
            targets = [min(ends, key=lambda e: abs((d(e) - d(a)).days)) for a in FISCAL_ANCHORS]
        ciks = sorted({c["cik"] for v in s["variants"] for c in v})
        assert len(ciks) == 1, s["id"]
        for target_end in targets:
            label = quarter_label(s, target_end)
            key = f"{s['id']}-{label.replace(' ', '')}"
            if only and key not in only:
                continue
            # the task runs on the last day before the target quarter's results were first public (its first
            # earnings release after quarter end), or on the panel's last day if that comes first
            released = min(r for r in releases[ciks[0]] if r > target_end)
            assert released <= q_first_filed(s["id"], target_end), (key, released)
            as_of = min(str(d(released) - timedelta(days=1)), panel_end)
            q = quarterly[(s["id"], target_end)]
            actual = float(q["first_value"])
            feed = []
            seen_periods = set()
            for r in sorted((r for r in facts if r["series"] == s["id"]), key=lambda r: (r["end"], r["filed"])):
                if r["filed"] <= as_of and r["end"] < target_end:
                    # a derived Q4's start is the end of the nine months it was derived from
                    start = str(d(r["start"]) + timedelta(days=1)) if r["derived"] == "True" else r["start"]
                    feed.append({"period_start": start, "period_end": r["end"],
                                 "value_usd_m": r["value_musd"], "reported_on": r["filed"],
                                 "report": "first report" if r["end"] not in seen_periods else "later filing (comparative, may be restated)",
                                 "q4_derived_from_annual": r["derived"]})
                    seen_periods.add(r["end"])
            naive = naive_forecast(feed, target_end)
            lines = statement_feed(statements[ciks[0]], as_of, target_end)
            # the metric gate: the KPI's last four reported quarters, every version the feed holds
            history = defaultdict(list)
            for r in feed:
                history[r["period_end"]].append(float(r["value_usd_m"]))
            history = {e: history[e] for e in sorted(history)[-4:]}
            first_quarter = min(r["period_end"] for r in feed)
            prior_label = quarter_label(s, max(r["period_end"] for r in feed))
            dq = sensor_facts(rows_all, s["sensors"], as_of)
            basis = restatement_facts(feed, target_end)

            case_split = "retired" if key in retired else split
            for variant in VARIANTS:
                anon = variant != "named"      # disguised: codes for names, in coded and anon
                f = factor[s["id"]] if variant == "anon" else 1.0
                code = f"{'Airline' if s['calendar'] == 'calendar' else 'Retailer'} {codes[s['sensors'][0]]}"
                company = code if anon else s["id"].split("_")[0]
                tickers_shown = [codes[t] for t in s["sensors"]] if anon else s["sensors"]
                task_id = f"{prefix}-produce-{codes[s['sensors'][0]] if anon else s['id']}-{label.replace(' ', '')}"
                if anon:
                    task_id += f"-{variant}"
                files = {}
                # sensor panel truncated at the as-of date; codes in the disguised variants, scaled dollars in anon
                rows = []
                for r in rows_all:
                    if r["date"] > as_of or r["ticker"] not in peer_sensors:
                        continue
                    rr = dict(r)
                    if anon:
                        rr["ticker"] = codes[r["ticker"]]
                        if variant == "anon":
                            rr["amt"] = f"{float(r['amt']) * factor[r['ticker']]:.2f}"
                    rows.append(rr)
                files["transaction_panel.csv"] = to_csv(rows, ["date", "ct", "amt", "ticker", "industry", "source_id"])
                lines_out = [dict(r, line=disguise(r["line"]) if anon else r["line"],
                                  split=disguise(r["split"]) if anon else r["split"],
                                  value=round(r["value"] * (f if r["unit"] != "shares" else 1.0), 4),
                                  unit=UNIT_LABEL.get(r["unit"], r["unit"])) for r in lines]
                files["actuals.csv"] = to_csv(lines_out, ACTUALS_COLS)
                b = brief
                if anon:
                    b = b.replace("ticker: a company, or a company segment when the ticker contains an underscore",
                                  "ticker: a company or company segment; company and ticker names are replaced with codes in this copy")
                    assert "underscore" not in b
                files["data_brief.md"] = f"{b.rstrip()}\nAbout this copy\n{COPY_NOTE[variant]}\n"

                kw = dict(company=company, industry=INDUSTRY_LABEL["airlines" if s["calendar"] == "calendar" else "department stores"],
                          tickers=", ".join(tickers_shown), target=label, target_end=target_end,
                          as_of=as_of, first_quarter=quarter_label(s, first_quarter), prior=prior_label,
                          fiscal_note=("calendar quarters" if s["calendar"] == "calendar"
                                       else "fiscal quarters (fiscal year ends late January / early February)"))
                system = harbor.render(system_t, firm=FIRM, **kw)
                dq_shown = [re.sub(r"^\S+", lambda m: codes[m.group()], x) for x in dq] if anon else dq
                user = harbor.render(user_t, **kw)
                gold = {"target_period": label, "target_period_end": target_end, "unit": "USD millions",
                        "actual": round(actual * f, 3), "actual_first_filed": q["first_filed"],
                        "actual_source": q["first_source"], "actual_q4_derived": q["first_derived"] == "True",
                        "naive_forecast": round(naive * f, 3) if naive else None,
                        "metric_history": {e: [round(v * f, 3) for v in vs] for e, vs in history.items()},
                        "consensus": None, "consensus_note": "not compiled for v1",
                        "scale_factor": f, "series": s["id"], "kpi": s["kpi"],
                        "facts": {"correct_metric": s["kpi"] + (f" (shown as: {disguise(s['kpi'])})" if anon else ""),
                                  "reporting_basis_and_structural": known_facts(s["id"], as_of) + basis,
                                  "alt_data_quality_auto": dq_shown}}
                fp = fingerprint(system, user, *[files[k] for k in sorted(files)])
                meta = {
                    "id": task_id, "family": family_id, "case": key, "role": "quant_researcher",
                    "workflow": "kpi_nowcast", "mode": "produce", "world": "systematic_consumer", "status": "graded",
                    "source": fam["source"], "split": case_split, "companies": peers, "as_of": as_of,
                    "fingerprint": fp,
                    "prompt": {"template": "families/kpi_nowcast/prompts/{system,user}.md", "files": sorted(files),
                               "file_sha256": {k: hashlib.sha256(files[k].encode()).hexdigest() for k in sorted(files)}},
                    "environment": {"tools": ["code_execution"], "internet": False},
                    "output_schema": "families/kpi_nowcast/schema.json",
                    "grader": {"type": "kpi_nowcast", "module": "families/kpi_nowcast/grader.py",
                               "accuracy": "programmatic (metric gate on gold.metric_history, then forecast vs gold.actual)",
                               "writeup": "LLM judge rubric C1-C38, over the brief and the methods note (families/kpi_nowcast/judge.md)"},
                    "sources": ["rl/sources/txn_panel/raw/sensor_panel.csv.gz", "rl/sources/txn_panel/raw/statement_facts.csv.gz",
                                "rl/sources/txn_panel/grader_only/kpi_facts.csv",
                                q["first_source"]],
                    "tags": [s["calendar"], variant] + ([] if anon else [s["id"]])
                            + (["low_signal"] if s["id"] in LOW_SIGNAL else []),
                    "meta": {"series": s["id"], "company": company_id, "variant": variant, "as_of": as_of, "target_period": label,
                             "sensors": s["sensors"], "low_signal": LOW_SIGNAL.get(s["id"])},
                }
                data = {"transaction_panel.csv.gz": gzip.compress(files["transaction_panel.csv"].encode(), mtime=0),
                        "actuals.csv": files["actuals.csv"], "data_brief.md": files["data_brief.md"]}
                prompt = {"system.md": system + "\n", "user.md": user + "\n",
                          "inputs.json": json.dumps(kw, indent=2, ensure_ascii=False) + "\n"}
                instruction = f"{system}\n\n{user}\n\n{HARBOR_NOTE.format(as_of=as_of)}\n"
                solution = {"solve.sh": REFERENCE / "solve.sh", "answer.md": reference_answer(gold),
                            "params.json": json.dumps({"target_period": label, "target_end": target_end})}
                built[task_id] = harbor.write(
                    TASKS / case_split / task_id, family=fam, builder="rl/families/kpi_nowcast/build.py",
                    instruction=instruction, metadata=meta,
                    description=f"Choose and nowcast {company}'s {label} metric from transaction data",
                    keywords=["alt-data", "kpi-nowcast", variant], verifier="verify.py",
                    tests={"verify.py": HERE / "verifier" / "verify.py", "grader.py": HERE / "grader.py",
                           "judge.md": HERE / "judge.md",
                           "judge_context.json": json.dumps({"user": f"{system}\n\n{user}", "as_of": as_of}, indent=1)},
                    gold=json.dumps(gold, indent=2, ensure_ascii=False) + "\n", judged=True,
                    data=data, prompt=prompt, solution=solution, pip=PIP)
    if only:
        print(f"{len(built)} tasks rewritten (partial build: manifest not updated)")
        return
    mpath = splits.write_manifest(family_id, built)
    print(f"{len(built)} tasks written to {TASKS.relative_to(RL.parent)}/<split>/; {mpath.relative_to(RL.parent)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="series-period keys like UAL-2018Q4 (all three variants built)")
    build("kpi_nowcast", only=ap.parse_args().only)
