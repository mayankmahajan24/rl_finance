"""Grader check only, not a solution: reads the gold of the task folder in ORACLE_TASK. Confidence 0 on the rows the
grader labels untrustworthy (grade.label_rows) where the input actually differs from the truth panel, and on reviewed
real problems; 1 elsewhere. The cleaned series is the truth panel, with reviewed real problems
replaced by the grader's hindsight reference. Run on its own cleaned series (the truth) it
distrusts only the real problems, as on the truth panel. Thin stretches are distrusted and left blank. It should score 1.0
everywhere."""
import argparse
import json
import os
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from grade import KEYS, hindsight_ref, label_rows  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
task = pathlib.Path(os.environ['ORACLE_TASK'])
gold = json.loads((task / 'tests' / 'gold.json').read_text())
truth = pd.read_csv(task / 'tests' / 'truth_panel.csv.gz', parse_dates=['date'])
label_rows(gold, df, truth)
df = df.merge(truth[KEYS + ['ct', 'amt']].rename(columns={'ct': 'clean_ct', 'amt': 'clean_amt'}), on=KEYS, how='left')
ref = hindsight_ref(gold, truth)
df = df.merge(ref[KEYS + ['ref_ct', 'ref_amt']], on=KEYS, how='left')
df['clean_ct'] = df.ref_ct.fillna(df.clean_ct)
df['clean_amt'] = df.ref_amt.fillna(df.clean_amt)
differs = ~np.isclose(df.ct, df.clean_ct, rtol=1e-6) | ~np.isclose(df.amt, df.clean_amt, rtol=1e-6)
real = pd.Series(False, index=df.index)
for e in gold['events']:
    if e['type'] in ('real', 'real_change'):
        real |= (df.ticker == e['ticker']) & (df.source_id == e['source_id']) & df.date.between(e['start'], e['end'])
df['confidence'] = 1.0 - ((df.label & (differs | real)) | df.thin).astype(float)
df.loc[df.thin, ['clean_ct', 'clean_amt']] = np.nan          # thin stretches are dropped
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[KEYS + ['confidence', 'clean_ct', 'clean_amt']].to_csv(a.output, index=False)
