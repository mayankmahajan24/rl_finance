"""Floor check, not a solution: trusts every row and returns the raw series as the cleaned one."""
import argparse

import pandas as pd

ap = argparse.ArgumentParser(); ap.add_argument('--input'); ap.add_argument('--output'); a = ap.parse_args()
df = pd.read_csv(a.input)
df['confidence'], df['clean_ct'], df['clean_amt'] = 1.0, df.ct, df.amt
df[['date', 'ticker', 'source_id', 'confidence', 'clean_ct', 'clean_amt']].to_csv(a.output, index=False)
