"""Grader check only, not a solution: the answer key. Reads the gold of the task folder in ORACLE_TASK. Confidence 0 on
the rows the grader labels untrustworthy (grade.label_rows) where the input differs from the truth panel, and on the
thin beginning; 1 elsewhere. The cleaned series is the truth panel, left blank on the thin beginning. Run on its own
cleaned series (the truth) it distrusts nothing new. It should score 1.0 everywhere."""
import argparse
import json
import os
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from grade import KEYS, label_rows  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
tests = pathlib.Path(os.environ.get('ORACLE_TESTS') or pathlib.Path(os.environ['ORACLE_TASK']) / 'tests')   # the panel graded
gold = json.loads((tests / 'gold.json').read_text())
truth = pd.read_csv(tests / 'truth_panel.csv.gz', parse_dates=['date'])
label_rows(gold, df, truth)
df = df.merge(truth[KEYS + ['ct', 'amt']].rename(columns={'ct': 'clean_ct', 'amt': 'clean_amt'}), on=KEYS, how='left')
differs = ~np.isclose(df.ct, df.clean_ct, rtol=1e-6) | ~np.isclose(df.amt, df.clean_amt, rtol=1e-6)
df['confidence'] = 1.0 - ((df.label & differs) | df.thin).astype(float)
df.loc[df.thin, ['clean_ct', 'clean_amt']] = np.nan          # the thin beginning is dropped
df['date'] = df.date.dt.strftime('%Y-%m-%d')
df[KEYS + ['confidence', 'clean_ct', 'clean_amt']].to_csv(a.output, index=False)
