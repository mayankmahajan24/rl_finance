"""Grader check only, not a solution: flags exactly the rows the grader labels bad (grade.label_rows on the gold of
the task folder given in ORACLE_TASK). It should score 1.0 on planted tasks and on controls."""
import argparse
import json
import os
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from grade import label_rows  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
gold = json.loads((pathlib.Path(os.environ['ORACLE_TASK']) / 'tests' / 'gold.json').read_text())
label_rows(gold, df)
df['anomaly_score'] = df.label.astype(float)
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[['date', 'ticker', 'source_id', 'anomaly_score']].to_csv(a.output, index=False)
