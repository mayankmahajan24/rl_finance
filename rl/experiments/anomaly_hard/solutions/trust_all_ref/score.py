"""Grader check only (a lopsided probe): the reference solution's cleaned series, but trusts every row. A real solution
could produce this, so it must not score well."""
import pathlib
import runpy
import sys

import pandas as pd

a = sys.argv
try:
    runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / 'reference' / 'score.py'), run_name='__main__')
except SystemExit as e:                  # the reference ends with sys.exit(main())
    if e.code:
        raise
out = a[a.index('--output') + 1]
o = pd.read_csv(out)
o['confidence'] = o.confidence.where(o.clean_ct.isna() | o.clean_amt.isna(), 1.0)   # blanks stay distrusted (low-signal gate)
o.to_csv(out, index=False)
