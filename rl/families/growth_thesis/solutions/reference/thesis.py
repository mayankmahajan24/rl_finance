"""Reference solution for the artifact-sensitive thesis task.

1. Find ticker-wide breaks (every sensor steps >3x on the same date)  -> airline is unreliable.
2. Find ticker-wide outages (every sensor near-dark for weeks)        -> mask those calendar days in BOTH years.
3. Find a source whose growth disagrees with the other sources across
   every airline (a panel / coverage change)                          -> drop that source.
4. Per airline and remaining source: growth of mean daily volume on matched calendar days,
   then the median across sources (robust to one double-counted sensor).
5. Write answer.json and a short memo that names each data issue.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

APP = Path(os.environ.get('APP_DIR', '/app'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--params', required=True)
    p = json.loads(Path(ap.parse_args().params).read_text())
    y1, y2 = p['year_start'], p['year_end']
    df = pd.read_csv(APP / 'data' / 'transactions.csv', parse_dates=['date'])
    dates = pd.date_range(df.date.min(), df.date.max())
    ct = df.pivot_table(index='date', columns=['ticker', 'source_id'], values='ct', aggfunc='sum').reindex(dates).fillna(0)
    x = np.log(ct.clip(lower=1))
    tickers = sorted(df.ticker.unique()); sources = sorted(df.source_id.unique())
    notes, unreliable, outage_days = [], [], {}

    for t in tickers:
        cons = (x[t] - x[t].median()).median(axis=1)
        fwd = cons[::-1].rolling(28, min_periods=14).median()[::-1]
        back = cons.shift(1).rolling(28, min_periods=14).median()
        step = fwd - back
        # ticker-wide break: a >3x step that stays (an outage recovery returns to the old level, a re-map does not)
        remap = None
        in_window = step[(step.index.year >= y1) & (step.index.year <= y2)]
        if len(in_window) and in_window.max() > np.log(3):
            d = in_window.idxmax()
            after = cons.loc[d + pd.Timedelta(days=7):d + pd.Timedelta(days=60)].median()
            before = cons.loc[d - pd.Timedelta(days=210):d - pd.Timedelta(days=30)].median()
            if after - before > np.log(3):
                remap = d
                unreliable.append(t)
                notes.append(f'{t}: all sources jump ~{np.exp(after - before):.0f}x around {d.date()} and stay there - '
                             f'a ticker-wide structural break (looks like a merchant re-mapping artifact, not real '
                             f'growth). Its {y1}-{y2} growth cannot be trusted from this panel, so I mark it unreliable.')
        # outage: consensus far below its surrounding level for 2+ weeks (not the low period before a re-map)
        base = cons.rolling(240, center=True, min_periods=60).quantile(0.75)
        dark = (cons < base - np.log(5)).rolling(14, center=True, min_periods=7).mean() > 0.7
        if remap is not None:
            dark[:remap + pd.Timedelta(days=30)] = False
        if dark.any():
            d0, d1 = dark[dark].index.min(), dark[dark].index.max()
            outage_days[t] = (d0, d1)
            notes.append(f'{t}: every source goes near-dark from {d0.date()} to {d1.date()} (data outage, not demand); '
                         f'I excluded those calendar days from both years when computing growth.')

    def growth_by_source(t):
        out = {}
        keep = pd.Series(True, index=dates)
        if t in outage_days:
            o0, o1 = outage_days[t]
            doy = dates.dayofyear
            keep &= ~((doy >= o0.dayofyear - 3) & (doy <= o1.dayofyear + 3))
        for s in sources:
            v = ct[(t, s)]
            a = v[(dates.year == y1) & keep].mean(); b = v[(dates.year == y2) & keep].mean()
            out[s] = b / a - 1 if a > 0 else np.nan
        return out

    G = pd.DataFrame({t: growth_by_source(t) for t in tickers}).T          # rows ticker, cols source
    logG = np.log1p(G)
    dev = logG.sub(logG.median(axis=1), axis=0).drop(index=unreliable).median()
    bad_sources = [s for s in sources if abs(dev[s]) > np.log(1.3)]
    for s in bad_sources:
        notes.append(f'Source {s}: shows {np.expm1(dev[s]):+.0%} more growth than the other sources for the typical '
                     f'airline - a source-wide panel / coverage change, so I dropped source {s}.')
    use = [s for s in sources if s not in bad_sources]
    growth = G[use].median(axis=1)
    reliable = growth.drop(index=unreliable)
    fastest = reliable.idxmax()
    second = reliable.drop(index=fastest).idxmax()
    spread = G[use].loc[fastest]

    ans = dict(fastest=fastest, growth={t: round(float(v), 4) for t, v in growth.items()}, unreliable=unreliable)
    memo = [f'# Fastest-growing airline, {y1} to {y2}', '',
            f'**Conclusion: {fastest} grew fastest**, with transactions up about {reliable[fastest]:+.0%} '
            f'(the median across sources {", ".join(map(str, use))}; single-source range '
            f'{spread.min():+.0%} to {spread.max():+.0%}). {second} is next at {reliable[second]:+.0%}.', '',
            '## Data issues that change the answer']
    memo += [f'- {n}' for n in notes] or ['- None found.']
    memo += ['', '## Method',
             f'Growth = mean daily transactions in {y2} / {y1} - 1 per source, on matched calendar days; then the '
             'median across sources so a single double-counted or broken sensor cannot drive the result.']
    out = APP / 'output'; out.mkdir(parents=True, exist_ok=True)
    (out / 'answer.json').write_text(json.dumps(ans, indent=1))
    (out / 'memo.md').write_text('\n'.join(memo) + '\n')
    print(json.dumps(ans))


if __name__ == '__main__':
    main()
