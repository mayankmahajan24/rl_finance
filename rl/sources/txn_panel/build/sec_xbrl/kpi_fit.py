"""How well does sensor spend growth track each candidate KPI's growth?

For each series and candidate KPI: YoY growth of the KPI (first-reported values, 2015-2017 quarters,
so both years are on the same reporting basis) vs YoY growth of sensor spend summed over the same
reporting period. Sensor growth = median across the four sources (robust to one source's panel
shifting). Reports correlation and mean absolute gap in percentage points.
"""
import os, sys
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_gold import facts_for, quarterize  # noqa: E402
from series import SERIES, one, P606  # noqa: E402

panel = pd.read_csv(sys.argv[1], parse_dates=["date"])

ALT = {  # candidate KPIs beyond the current mapping, same variant structure as series.py
    "UAL": {"Total revenue": [one(100517, ("us-gaap:Revenues", ""))],
            "Mainline passenger only": [one(100517, ("us-gaap:PassengerRevenueMainline", ""))]},
    "DAL": {"Total revenue": [one(27904, ("us-gaap:Revenues", ""))]},
    "AAL": {"Total revenue": [one(6201, ("us-gaap:Revenues", ""))],
            "Mainline passenger only": [one(6201, ("us-gaap:PassengerRevenueMainline", ""))]},
    "LUV": {"Total revenue": [one(92380, ("us-gaap:Revenues", ""))]},
    "ALK": {"Total revenue": [one(766421, ("us-gaap:Revenues", ""))]},
    "JBLU": {"Total revenue": [one(1158463, ("us-gaap:Revenues", ""))]},
    "SAVE": {"Total revenue": [one(1498710, ("us-gaap:SalesRevenueNet", ""))]},
    "HA": {"Total revenue": [one(1172222, ("us-gaap:Revenues", ""))]},
    "ALGT": {"Scheduled service + ancillary": [[{"cik": 1362468, "selectors": [("us-gaap:PassengerRevenue", "")]},
                                                {"cik": 1362468, "selectors": [("*:TotalAncillaryRevenue", "")]}]],
             "Total revenue": [one(1362468, ("us-gaap:Revenues", ""))]},
    "DDS": {"Retail operations segment": [one(28917, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=dds:RetailOperationsMember"))],
            "Total revenue (incl. credit, other)": [one(28917, ("us-gaap:Revenues", ""))]},
    "KSS": {"Total revenue (incl. credit)": [one(885639, ("us-gaap:Revenues", ""))]},
    "JCP": {"Total revenue (incl. credit)": [one(1166126, ("us-gaap:Revenues", ""), (P606, ""))]},
    "JWN_FP": {"Nordstrom full-line stores only": [one(72333, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:NordstromFullLineStoresMember"))]},
    "JWN_OP": {"Rack stores only": [one(72333, ("us-gaap:SalesRevenueNet", "us-gaap:StatementBusinessSegmentsAxis=jwn:NordstromRackMember"))]},
}


def first_quarters(s):
    q = {}
    for r in sorted(quarterize(facts_for(s)), key=lambda r: r["filed"]):
        q.setdefault(r["end"], r)
    return q


def sensor_spend(tickers, start, end):
    m = panel[panel.ticker.isin(tickers) & (panel.date > pd.Timestamp(start) - pd.Timedelta(days=0)) & (panel.date <= pd.Timestamp(end))]
    return m.groupby("source_id").amt.sum()


def fit(s, variants):
    q = first_quarters(dict(s, variants=variants))
    rows = []
    for end, r in q.items():
        if not ("2015-01-01" <= end <= "2017-12-31"):
            continue
        prior = [e for e in q if abs((date.fromisoformat(e) - (date.fromisoformat(end) - timedelta(days=364))).days) <= 10]
        if not prior:
            continue
        p = q[prior[0]]
        if not p["value_musd"] or not r["value_musd"]:
            continue
        kpi_g = r["value_musd"] / p["value_musd"] - 1
        # sensor period: day after prior quarter's end of the same length; use the KPI's own start/end
        st = (date.fromisoformat(r["start"]) - timedelta(days=1)).isoformat()
        pst = (date.fromisoformat(p["start"]) - timedelta(days=1)).isoformat()
        cur, prev = sensor_spend(s["sensors"], st, end), sensor_spend(s["sensors"], pst, p["end"])
        g = (cur / prev - 1).dropna()
        rows.append((end, kpi_g, g.median()))
    df = pd.DataFrame(rows, columns=["end", "kpi", "sensor"])
    if len(df) < 6:
        return None
    return len(df), df.kpi.corr(df.sensor), (df.kpi - df.sensor).abs().mean() * 100, df.kpi.std() * 100


out = []
for s in SERIES:
    cands = {f"CURRENT: {s['kpi']}": s["variants"], **ALT.get(s["id"], {})}
    for name, v in cands.items():
        r = fit(s, v)
        if r:
            n, c, mae, sd = r
            out.append((s["id"], name, n, c, mae, sd))
        else:
            out.append((s["id"], name, 0, float("nan"), float("nan"), float("nan")))
df = pd.DataFrame(out, columns=["series", "kpi", "n_qtrs", "corr", "mean_abs_gap_pp", "kpi_yoy_sd_pp"])
pd.set_option("display.width", 200, "display.max_colwidth", 60)
print(df.round(2).to_string(index=False))
