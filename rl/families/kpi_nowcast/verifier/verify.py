"""Harbor verifier for kpi_nowcast: grade /app/output/answer.md the way run.py grades a final message.

Writes named rewards (reward.json), the metrics run.py records, never one blended number:
schema_ok, abs_pct_error, signed_pct_error, skill_vs_naive, covered, interval_score_pct (grader.py,
programmatic), and writeup_score plus w_C1..w_C12 from the LLM judge (judge.md). Without
ANTHROPIC_API_KEY the write-up is not judged and its metrics are left out.
"""
import json
import os

import grader as G
from common import APP, TESTS, write_rewards


def judge(writeup, fc, gold):
    import anthropic
    ctx = json.loads((TESTS / 'judge_context.json').read_text())
    req = G.judge_request(os.environ.get('JUDGE_MODEL', 'claude-sonnet-5-5'), ctx['user'], ctx['as_of'], writeup, fc, gold)
    with anthropic.Anthropic().messages.stream(**req) as stream:
        msg = stream.get_final_message()
    return msg.model, json.loads(next(b.text for b in msg.content if b.type == 'text'))


def main():
    gold = json.loads((TESTS / 'gold.json').read_text())
    answer = APP / 'output' / 'answer.md'
    fc, writeup, perr = G.parse_response(answer.read_text() if answer.exists() else '')
    rewards = G.grade_accuracy(fc, gold)
    details = {'answer_found': answer.exists(), 'parse_error': perr, 'forecast': fc}
    if os.environ.get('ANTHROPIC_API_KEY'):
        model, verdicts = judge(writeup, fc, gold)
        rewards.update({k: v for k, v in G.grade_writeup(verdicts).items() if v is not None})
        details['judge'] = {'model': model, **{i: f"{v['verdict']}: {v['reason']}" for i, v in verdicts.items()}}
    else:
        details['judge'] = 'skipped: no ANTHROPIC_API_KEY'
    write_rewards(rewards, details)


if __name__ == '__main__':
    main()
