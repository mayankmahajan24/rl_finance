"""Naive solution: the benchmark the reward is measured against, so it should score 0.

Forecast = last reported quarter x last year's seasonal step into the target quarter, with both
step values as first reported (the same rule as the build's naive_forecast), and a +-10% range.
"""
import argparse
import csv
import json
import os
from datetime import date, timedelta
from pathlib import Path

APP = Path(os.environ.get('APP_DIR', '/app'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--params', required=True)
    p = json.loads(Path(ap.parse_args().params).read_text())
    rows = sorted(csv.DictReader((APP / 'data' / 'actuals.csv').open()), key=lambda r: r['reported_on'])
    first, latest = {}, {}
    for r in rows:
        first.setdefault(r['period_end'], float(r['value_usd_m']))
        latest[r['period_end']] = float(r['value_usd_m'])
    ends = sorted(latest)

    def year_ago(e):
        target = date.fromisoformat(e) - timedelta(days=364)
        return next(x for x in ends if abs((date.fromisoformat(x) - target).days) <= 10)

    point = latest[ends[-1]] * first[year_ago(p['target_end'])] / first[year_ago(ends[-1])]
    fc = {'target_period': p['target_period'], 'unit': 'USD millions', 'point': round(point, 3),
          'low': round(point * 0.9, 3), 'high': round(point * 1.1, 3), 'interval_level': 0.95,
          'in_sample': [], 'vs_consensus': 'no_consensus'}
    (APP / 'output').mkdir(parents=True, exist_ok=True)
    (APP / 'output' / 'answer.md').write_text(f'Same quarter last year, scaled.\n\n```json\n{json.dumps(fc)}\n```\n')


if __name__ == '__main__':
    main()
