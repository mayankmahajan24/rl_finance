"""Verifier for the artifact-sensitive thesis task.

Reads /app/output/answer.json:
  {"fastest": "<ticker>", "growth": {"<ticker>": <float, e.g. 0.12 = +12%>, ...}, "unreliable": ["<ticker>", ...]}
and /app/output/memo.md (the written conclusion).

Reward (continuous, 0..1):
  0.35  fastest-growing airline is correct
  0.25  growth estimates: mean over trustworthy airlines of max(0, 1 - |error| / tolerance)
  0.15  F1 of the "unreliable" list vs truth (airlines whose data cannot support the comparison);
        airlines in `optional_unreliable` are neither credited nor penalised
  0.25  atomic rubric on memo.md, graded by the family's pinned model judge (judge.py, judge.json).
        Without credentials, or if the judge fails, the task is not graded (empty reward.json, details
        say why). JUDGE=keyword opts into a conservative keyword grader instead.
"""
import json
import os
import re

import judge
from common import APP, f1, load_gold, write_reward, write_rewards

W_FASTEST, W_GROWTH, W_UNREL, W_RUBRIC = 0.35, 0.25, 0.15, 0.25
NEG = ('not ', 'no ', "isn't", 'exclud', 'unreliable', 'artifact', 'spurious', 'ignore', 'rather than')


def rubric_items(truth):
    tr = truth['traps']
    if truth['control']:
        return [
            dict(id='names_fastest', text=f"The memo's conclusion names {truth['fastest']} as the fastest-growing airline."),
            dict(id='no_false_artifacts', text='The memo does not claim that any airline or source has a re-mapping, '
                                               'outage, double-counting or panel break (none were present).'),
        ]
    return [
        dict(id='remap_artifact', text=f"The memo identifies that {tr['ticker_remap']['ticker']}'s jump around "
                                       f"{tr['ticker_remap']['start']} is a data artifact (re-mapping / structural break "
                                       f"across all sources), not real growth."),
        dict(id='panel_change', text=f"The memo identifies a source-wide coverage / panel change in source "
                                     f"{tr['panel_ramp']['source_id']} (it inflates growth for every airline in that "
                                     f"source) and avoids or adjusts for it."),
        dict(id='outage', text=f"The memo notes the data gap / outage in {tr['outage']['ticker']} "
                               f"({tr['outage']['start']} to {tr['outage']['end']}) and handles it so the base year "
                               f"is not understated."),
        dict(id='names_fastest', text=f"The memo's conclusion names {truth['fastest']} as the fastest-growing airline "
                                      f"and does not name {tr['ticker_remap']['ticker']} as the fastest."),
    ]


def _sentences(text):
    return [s.lower() for s in re.split(r'(?<=[.!?\n])\s+', text) if s.strip()]


def keyword_judge(memo, truth, items):
    S = _sentences(memo)
    has = lambda s, words: any(w in s for w in words)  # noqa: E731
    out = {}
    fastest = truth['fastest'].lower()
    for it in items:
        i = it['id']
        if i == 'remap_artifact':
            r = truth['traps']['ticker_remap']['ticker'].lower()
            ok = any(r in s and has(s, ['remap', 're-map', 'mapping', 'artifact', 'structural', 'break', 'jump',
                                        'discontinu', 'step change', 'spurious']) for s in S)
        elif i == 'panel_change':
            sid = str(truth['traps']['panel_ramp']['source_id'])
            pat = re.compile(rf'(source[ _-]?(id)?\s*#?\s*{sid}\b|\bs{sid}\b)')
            ok = any(pat.search(s) and has(s, ['panel', 'coverage', 'ramp', 'onboard', 'source-wide', 'across all',
                                               'every airline', 'all airlines', 'methodolog', 'expansion']) for s in S)
        elif i == 'outage':
            o = truth['traps']['outage']['ticker'].lower()
            ok = any(o in s and has(s, ['outage', 'gap', 'missing', 'dark', 'depressed', 'collapse', 'near-zero',
                                        'near zero', 'dropout']) for s in S)
        elif i == 'names_fastest':
            ok = any(fastest in s and has(s, ['fastest', 'highest growth', 'grew the most', 'strongest growth']) for s in S)
            if not truth['control']:
                r = truth['traps']['ticker_remap']['ticker'].lower()
                ok = ok and not any(r in s and 'fastest' in s and not has(s, NEG) for s in S)
        elif i == 'no_false_artifacts':
            ok = not any(has(s, ['remap', 're-map', 'outage', 'double-count', 'double count', 'panel change',
                                 'structural break']) and not has(s, ('no ', 'not ', 'none', 'without')) for s in S)
        else:
            ok = False
        out[i] = dict(passed=bool(ok), evidence='keyword match' if ok else 'no keyword match')
    return out


def llm_judge(memo, truth, items):
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'id': {'type': 'string'}, 'passed': {'type': 'boolean'}, 'evidence': {'type': 'string'}},
            'required': ['id', 'passed', 'evidence'], 'additionalProperties': False}}},
        'required': ['items'], 'additionalProperties': False,
    }
    rubric = '\n'.join(f"- id={it['id']}: {it['text']}" for it in items)
    system = ('You are grading an analyst memo against a rubric. Judge each item independently and strictly: an item '
              'passes only if the memo clearly states it (paraphrase is fine; vague hedging is not). Quote the sentence '
              'you relied on as evidence, or write "none".')
    outs, meta = judge.judge(system, f'<rubric>\n{rubric}\n</rubric>\n\n<memo>\n{memo[:30000]}\n</memo>', schema)
    votes = []
    for out in outs:
        got = {x['id']: dict(passed=bool(x['passed']), evidence=x['evidence']) for x in out['items']}
        votes.append({it['id']: got.get(it['id'], dict(passed=False, evidence='item missing from judge output'))
                      for it in items})
    return judge.majority(votes, 'passed'), meta


def main():
    truth = load_gold()
    try:
        ans = json.loads((APP / 'output' / 'answer.json').read_text())
    except Exception as e:  # noqa: BLE001
        return write_reward(0.0, dict(error=f'could not read output/answer.json: {e}'))
    if not isinstance(ans, dict):
        return write_reward(0.0, dict(error=f'output/answer.json is a {type(ans).__name__}, not an object'))
    memo_path = APP / 'output' / 'memo.md'
    memo = memo_path.read_text() if memo_path.exists() else ''

    # 1. fastest
    s_fast = 1.0 if str(ans.get('fastest', '')).strip() == truth['fastest'] else 0.0
    # 2. growth accuracy on trustworthy airlines
    growth = ans.get('growth') if isinstance(ans.get('growth'), dict) else {}
    tol = truth['growth_tolerance']; per = {}
    for t, g in truth['true_growth'].items():
        if t in truth['unreliable']:
            continue
        try:
            per[t] = max(0.0, 1 - abs(float(growth[t]) - g) / tol)
        except (KeyError, TypeError, ValueError):
            per[t] = 0.0
    s_growth = sum(per.values()) / len(per)
    # 3. unreliable list
    U = set(truth['unreliable']); O = set(truth['optional_unreliable'])
    R = {str(x) for x in ans.get('unreliable') if isinstance(ans.get('unreliable'), list)} - O
    if not U and not R:
        s_unrel = 1.0
    else:
        p = len(R & U) / len(R) if R else 0.0; r = len(R & U) / len(U) if U else 0.0
        s_unrel = f1(p, r)
    # 4. rubric on the memo
    items = rubric_items(truth)
    det = dict(fastest_correct=bool(s_fast), truth_fastest=truth['fastest'], reported_fastest=ans.get('fastest'),
               growth_score=round(s_growth, 3), growth_per_ticker={k: round(v, 2) for k, v in per.items()},
               unreliable_f1=round(s_unrel, 3))
    if not memo.strip():
        graded, det['judge'] = {it['id']: dict(passed=False, evidence='memo.md missing or empty') for it in items}, 'none'
    elif os.environ.get('JUDGE', 'auto') == 'keyword':
        graded, det['judge'] = keyword_judge(memo, truth, items), 'keyword'
    else:
        why = judge.unavailable()
        if why:
            return write_rewards({}, dict(det, status='not graded', note=f'{why}; JUDGE=keyword opts into the keyword grader'))
        try:
            graded, det['judge_meta'] = llm_judge(memo, truth, items)
        except judge.JudgeError as e:
            return write_rewards({}, dict(det, status='not graded', note=f'memo judge failed: {e}'))
        det['judge'] = 'llm:' + ','.join(det['judge_meta']['served_model'])
    s_rubric = sum(v['passed'] for v in graded.values()) / len(graded)

    reward = W_FASTEST * s_fast + W_GROWTH * s_growth + W_UNREL * s_unrel + W_RUBRIC * s_rubric
    return write_reward(reward, dict(det, rubric_score=round(s_rubric, 3), rubric=graded))


if __name__ == '__main__':
    main()
