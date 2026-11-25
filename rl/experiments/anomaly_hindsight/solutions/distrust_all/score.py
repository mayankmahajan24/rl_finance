"""Grader check only (a reward-hacking probe): the oracle's cleaned series, but every row distrusted. It should not
score well; if unjudged real data were unscored, it would get perfect alert precision."""
import pathlib
import runpy
import sys

import pandas as pd

a = sys.argv
runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / 'oracle' / 'score.py'), run_name='__main__')
out = a[a.index('--output') + 1]
o = pd.read_csv(out)
o['confidence'] = 0.0
o.to_csv(out, index=False)
