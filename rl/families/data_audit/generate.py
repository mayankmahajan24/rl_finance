"""data_audit generator: one disguised panel with planted data-quality problems, and its ground truth.

Ported from make_audit_variant in ~/altdata_evals/generator.py. With every company in the panel it
reproduces the pilot exactly; on a split's smaller panel it plants fewer problems when it runs out
of untouched companies (the pilot code would have crashed there instead).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from families._shared import panel_perturb as P
from families._shared.panel_perturb import Frame, inj_series_swap


def make_variant(seed: int, control: bool, raw: pd.DataFrame, artifacts=((), ())):
    rng = np.random.default_rng(seed)
    F = Frame(raw, rng, artifacts=artifacts)
    planted, used_series, used_tickers = [], set(), set()
    if not control:
        n = int(rng.integers(3, 6))
        for typ in rng.choice(P.AUDIT_TYPES, n, replace=False):
            cands = F.candidates(exclude_tickers=used_tickers, exclude_series=used_series)
            if not cands:          # a small split ran out of untouched companies: plant fewer problems
                break
            t, s = cands[int(rng.integers(len(cands)))]
            if typ == 'series_swap':
                partners = [c for c in cands if c[1] == s and c[0] != t]
                if not partners:   # no second company on this sensor: skip the swap
                    continue
                t2 = partners[int(rng.integers(len(partners)))][0]
                item = inj_series_swap(F, t, s, t2); used_tickers |= {t, t2}
            else:
                item = getattr(P, f'inj_{typ}')(F, t, s); used_tickers.add(t)
            used_series.add((t, s))
            planted.append(dict(item, origin='planted'))
    req, opt = F.natural()
    truth = dict(family='audit', seed=seed, control=control, required=planted + req, optional=opt,
                 ignore_series=F.low_volume_series(), date_tolerance_days=10)
    df = F.df.sort_values(['date', 'ticker', 'source_id']).reset_index(drop=True)
    return df, truth
