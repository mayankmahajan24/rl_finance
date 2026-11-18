"""Grader check only, not a solution: reads the gold of the task folder in ORACLE_TASK. Confidence 0 on exactly the
rows the grader labels untrustworthy (grade.label_rows), 1 elsewhere; the cleaned series is the truth panel. It
should score 1.0 on planted tasks and on controls."""
import argparse
import json
import os
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from grade import KEYS, label_rows  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
task = pathlib.Path(os.environ['ORACLE_TASK'])
gold = json.loads((task / 'tests' / 'gold.json').read_text())
truth = pd.read_csv(task / 'tests' / 'truth_panel.csv.gz', parse_dates=['date'])
label_rows(gold, df, truth)
df['confidence'] = 1.0 - df.label.astype(float)
df = df.merge(truth[KEYS + ['ct', 'amt']].rename(columns={'ct': 'clean_ct', 'amt': 'clean_amt'}), on=KEYS, how='left')
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[KEYS + ['confidence', 'clean_ct', 'clean_amt']].to_csv(a.output, index=False)
