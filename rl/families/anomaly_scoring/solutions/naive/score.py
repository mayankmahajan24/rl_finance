"""Deliberately naive scorer: full-sample z-score of each series' log count.
Uses the whole history (mean/std include future data), so it fails the no-foresight check."""
import argparse

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--input', required=True)
ap.add_argument('--output', required=True)
a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
x = np.log1p(df.ct)
g = x.groupby([df.ticker, df.source_id])
z = (x - g.transform('mean')) / g.transform('std')
df['anomaly_score'] = (z.abs() / 6).clip(0, 1).fillna(0).round(6)
df[['date', 'ticker', 'source_id', 'anomaly_score']].to_csv(a.output, index=False)
