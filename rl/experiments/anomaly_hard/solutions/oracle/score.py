"""Grader check only, not a solution: flags exactly the gold's labelled days (reads tests/gold.json from the
task folder given in ORACLE_TASK). It should score 1.0 on planted tasks and on controls."""
import argparse
import json
import os
import pathlib

import pandas as pd

ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
gold = json.loads((pathlib.Path(os.environ['ORACLE_TASK']) / 'tests' / 'gold.json').read_text())
df['anomaly_score'] = 0.0
for e in gold['events']:
    m = (df.ticker == e['ticker']) & (df.source_id == e['source_id']) & df.date.between(e['start'], e['end'])
    df.loc[m, 'anomaly_score'] = 1.0
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[['date', 'ticker', 'source_id', 'anomaly_score']].to_csv(a.output, index=False)
