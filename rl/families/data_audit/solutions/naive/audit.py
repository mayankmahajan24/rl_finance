"""Deliberately naive audit: the kind of first pass a hurried analyst (or model) writes.
Checks duplicates, then flags the largest single-day z-scores per series as 'level_shift' and any
missing day run as 'outage' - no peer comparison, no ticket-size checks, no notion of what a level shift is."""
import json
import os
from pathlib import Path

import pandas as pd

APP = Path(os.environ.get('APP_DIR', '/app'))


def main():
    df = pd.read_csv(APP / 'data' / 'transactions.csv', parse_dates=['date'])
    issues = []
    dup = df.duplicated(['date', 'ticker', 'source_id'])
    for (t, s), g in df[dup].groupby(['ticker', 'source_id']):
        issues.append(dict(type='duplicate_rows', ticker=t, source_id=int(s), start=str(g.date.min().date()),
                           end=str(g.date.max().date())))
    for (t, s), g in df[~dup].groupby(['ticker', 'source_id']):
        g = g.set_index('date').sort_index()
        z = (g.ct - g.ct.mean()) / g.ct.std()
        for d in z.abs().sort_values(ascending=False).index[:3]:
            issues.append(dict(type='level_shift', ticker=t, source_id=int(s), start=str(d.date()), end=None))
        gaps = g.index.to_series().diff().dt.days
        for d, gap in gaps[gaps > 3].items():
            issues.append(dict(type='outage', ticker=t, source_id=int(s),
                               start=str((d - pd.Timedelta(days=int(gap) - 1)).date()), end=str(d.date())))
    out = APP / 'output'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'issues.json').write_text(json.dumps(issues, indent=1))
    print(f'wrote {len(issues)} issues')


if __name__ == '__main__':
    main()
