"""Reference online anomaly scorer: peer-sensor comparison + online level-shift state machine
(model code in anomaly_model.py, strictly causal). anomaly_score = 1 - confidence."""
import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from anomaly_model import run_model  # noqa: E402

warnings.filterwarnings('ignore')

ap = argparse.ArgumentParser()
ap.add_argument('--input', required=True)
ap.add_argument('--output', required=True)
a = ap.parse_args()
df = pd.read_csv(a.input, parse_dates=['date'])
keys = ['date', 'ticker', 'source_id']
res = run_model(df[keys + ['ct', 'amt']].drop_duplicates(keys))
out = df[keys].drop_duplicates().merge(res[keys + ['confidence']], on=keys, how='left')
out['anomaly_score'] = (1 - out.confidence).fillna(0.5).round(6)
out[keys + ['anomaly_score']].to_csv(a.output, index=False)
