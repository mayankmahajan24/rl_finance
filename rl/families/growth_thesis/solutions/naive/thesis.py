"""Deliberately naive solution: total transactions across all sources, year over year."""
import argparse
import json
import os
from pathlib import Path

import pandas as pd

APP = Path(os.environ.get('APP_DIR', '/app'))
ap = argparse.ArgumentParser(); ap.add_argument('--params', required=True)
p = json.loads(Path(ap.parse_args().params).read_text())
y1, y2 = p['year_start'], p['year_end']
df = pd.read_csv(APP / 'data' / 'transactions.csv', parse_dates=['date'])
tot = df.groupby([df.ticker, df.date.dt.year]).ct.sum().unstack()
g = tot[y2] / tot[y1] - 1
fastest = g.idxmax()
out = APP / 'output'; out.mkdir(parents=True, exist_ok=True)
(out / 'answer.json').write_text(json.dumps(dict(fastest=fastest, growth=g.round(4).to_dict(), unreliable=[])))
(out / 'memo.md').write_text(f'# Answer\n\n{fastest} grew fastest: total transactions rose {g[fastest]:+.0%} '
                             f'from {y1} to {y2}, the highest of any airline.\n')
