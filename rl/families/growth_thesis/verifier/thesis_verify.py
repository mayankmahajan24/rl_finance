"""Verifier for the artifact-sensitive thesis task.

Reads /app/output/answer.json:
  {"fastest": "<ticker>", "growth": {"<ticker>": <float, e.g. 0.12 = +12%>, ...}, "unreliable": ["<ticker>", ...]}
and /app/output/memo.md (the written conclusion).

Reward (continuous, 0..1):
  0.35  fastest-growing airline is correct
  0.25  growth estimates: mean over trustworthy airlines of max(0, 1 - |error| / tolerance)
  0.15  F1 of the "unreliable" list vs truth (airlines whose data cannot support the comparison);
        airlines in `optional_unreliable` are neither credited nor penalised
  0.25  atomic rubric on memo.md, graded by an LLM judge (Claude) when credentials are available,
        otherwise by a conservative keyword fallback. Set JUDGE=keyword to force the fallback.
"""
import json
import os
import re

from common import APP, f1, load_truth, write_reward

W_FASTEST, W_GROWTH, W_UNREL, W_RUBRIC = 0.35, 0.25, 0.15, 0.25
JUDGE_MODEL = os.environ.get('JUDGE_MODEL', 'claude-opus-5-5')
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
    import anthropic

    client = anthropic.Anthropic()
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'id': {'type': 'string'}, 'passed': {'type': 'boolean'}, 'evidence': {'type': 'string'}},
            'required': ['id', 'passed', 'evidence'], 'additionalProperties': False}}},
        'required': ['items'], 'additionalProperties': False,
    }
    rubric = '\n'.join(f"- id={it['id']}: {it['text']}" for it in items)
    prompt = (
        'You are grading an analyst memo against a rubric. Judge each item independently and strictly: an item '
        'passes only if the memo clearly states it (paraphrase is fine; vague hedging is not). Quote the sentence '
        'you relied on as evidence, or write "none".\n\n'
        f'<rubric>\n{rubric}\n</rubric>\n\n<memo>\n{memo[:30000]}\n</memo>'
    )
    kwargs = dict(model=JUDGE_MODEL, max_tokens=16000,
                  output_config={'effort': 'medium', 'format': {'type': 'json_schema', 'schema': schema}},
                  messages=[{'role': 'user', 'content': prompt}])
    try:
        resp = client.beta.messages.create(betas=['server-side-fallback-2026-07-01'], fallbacks='default', **kwargs)
    except anthropic.BadRequestError:
        resp = client.messages.create(**kwargs)
    if resp.stop_reason == 'refusal':
        raise RuntimeError('judge refused')
    text = next(b.text for b in resp.content if b.type == 'text')
    got = {x['id']: dict(passed=bool(x['passed']), evidence=x['evidence']) for x in json.loads(text)['items']}
    return {it['id']: got.get(it['id'], dict(passed=False, evidence='item missing from judge output')) for it in items}


def main():
    truth = load_truth()
    try:
        ans = json.loads((APP / 'output' / 'answer.json').read_text())
    except Exception as e:  # noqa: BLE001
        return write_reward(0.0, dict(error=f'could not read output/answer.json: {e}'))
    memo_path = APP / 'output' / 'memo.md'
    memo = memo_path.read_text() if memo_path.exists() else ''

    # 1. fastest
    s_fast = 1.0 if str(ans.get('fastest', '')).strip() == truth['fastest'] else 0.0
    # 2. growth accuracy on trustworthy airlines
    growth = {str(k): v for k, v in (ans.get('growth') or {}).items()}
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
    R = {str(x) for x in (ans.get('unreliable') or [])} - O
    if not U and not R:
        s_unrel = 1.0
    else:
        p = len(R & U) / len(R) if R else 0.0; r = len(R & U) / len(U) if U else 0.0
        s_unrel = f1(p, r)
    # 4. rubric on the memo
    items = rubric_items(truth)
    mode = os.environ.get('JUDGE', 'auto')
    judge_used = 'keyword'
    if not memo.strip():
        graded = {it['id']: dict(passed=False, evidence='memo.md missing or empty') for it in items}
    else:
        graded = None
        if mode in ('auto', 'llm'):
            try:
                graded = llm_judge(memo, truth, items); judge_used = f'llm:{JUDGE_MODEL}'
            except Exception as e:  # noqa: BLE001
                if mode == 'llm':
                    return write_reward(0.0, dict(error=f'LLM judge failed: {e}'))
                judge_error = str(e)[:300]
        if graded is None:
            graded = keyword_judge(memo, truth, items)
    s_rubric = sum(v['passed'] for v in graded.values()) / len(graded)

    reward = W_FASTEST * s_fast + W_GROWTH * s_growth + W_UNREL * s_unrel + W_RUBRIC * s_rubric
    det = dict(fastest_correct=bool(s_fast), truth_fastest=truth['fastest'], reported_fastest=ans.get('fastest'),
               growth_score=round(s_growth, 3), growth_per_ticker={k: round(v, 2) for k, v in per.items()},
               unreliable_f1=round(s_unrel, 3), rubric_score=round(s_rubric, 3), rubric=graded, judge=judge_used)
    if judge_used == 'keyword' and mode == 'auto' and 'judge_error' in locals():
        det['judge_fallback_reason'] = judge_error
    return write_reward(reward, det)


if __name__ == '__main__':
    main()
