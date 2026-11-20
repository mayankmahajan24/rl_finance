"""Merge series-review verdicts into reviewed.yaml: python apply_reviews.py EXPORT_DIR [--by NAME] [--date YYYY-MM-DD]

EXPORT_DIR holds the series review page's database, saved by ArtifactData's list action with out_dir: spans/*.json
(ticker, source_id, start, end, verdict) and series/*.json (reviewed). Each span with a verdict becomes a reviewed
entry (replacing an entry for the same series and dates), and each series ticked as reviewed is added to
reviewed_series. Then rebuild the tasks (build.py) so every task's gold picks them up.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REVIEWED = HERE / 'reviewed.yaml'
VERDICTS = {'real', 'change', 'not_real', 'recurring', 'unsure'}


def load(d: pathlib.Path) -> list[dict]:
    out = []
    for f in sorted(d.glob('*.json')) if d.exists() else []:
        doc = json.loads(f.read_text())
        out.append(dict(doc.get('data', doc), _id=doc.get('id', f.stem)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('export'); ap.add_argument('--by', default='Mayank'); ap.add_argument('--date', required=True)
    a = ap.parse_args()
    root = pathlib.Path(a.export)
    spans = [s for s in load(root / 'spans') if s.get('verdict') in VERDICTS]
    series = [s for s in load(root / 'series') if s.get('reviewed')]
    header = REVIEWED.read_text().split('\nreviewed:')[0]
    cur = yaml.safe_load(REVIEWED.read_text()) or {}
    rows = {(r['ticker'], int(r['source_id']), str(r['start']), str(r['end'])): r for r in cur.get('reviewed') or []}
    for s in spans:
        k = (s['ticker'], int(s['source_id']), s['start'], s['end'])
        rows[k] = dict(ticker=s['ticker'], source_id=int(s['source_id']), start=s['start'], end=s['end'],
                       verdict=s['verdict'], note=s.get('note', ''), reviewed_by=a.by, reviewed_at=a.date)
    done = {(x['ticker'], int(x['source_id'])) for x in cur.get('reviewed_series') or []}
    for s in series:
        tk, src = s['_id'].rsplit('-', 1)          # document id: TICKER-SOURCE
        done.add((tk, int(src)))
    body = yaml.safe_dump(dict(reviewed=sorted(rows.values(), key=lambda r: (r['ticker'], r['source_id'], r['start'])),
                               reviewed_series=[dict(ticker=t, source_id=s) for t, s in sorted(done)]),
                          sort_keys=False, width=120)
    REVIEWED.write_text(header + '\n' + body)
    print(f'{len(spans)} spans merged, {len(series)} series ticked; reviewed.yaml has {len(rows)} entries, '
          f'{len(done)} series reviewed end to end')


if __name__ == '__main__':
    main()
