"""Harbor verifier for kpi_nowcast: grade /app/output/answer.md the way run.py grades a final message.

Writes named rewards (reward.json), the metrics run.py records, never one blended number:
schema_ok, abs_pct_error, signed_pct_error, skill_vs_naive, covered, interval_score_pct (grader.py,
programmatic), and writeup_score plus w_C1..w_C12 from the family's pinned model judge (judge.md,
judge.py, judge.json). When the judge can't run (no ANTHROPIC_API_KEY) or fails, the write-up
metrics are left out and details say why; the accuracy metrics stand on their own.
"""
import json

import grader as G
import judge
from common import APP, TESTS, write_rewards


def judge_writeup(writeup, fc, gold):
    ctx = json.loads((TESTS / 'judge_context.json').read_text())
    cfg = judge.config()
    req = G.judge_request(cfg['model'], ctx['user'], ctx['as_of'], writeup, fc, gold)
    schema = req['extra_body']['output_config']['format']['schema']
    votes, meta = judge.judge(req['system'], req['messages'][0]['content'], schema, cfg)
    return judge.majority(votes, 'verdict'), meta


def main():
    gold = json.loads((TESTS / 'gold.json').read_text())
    answer = APP / 'output' / 'answer.md'
    fc, writeup, perr = G.parse_response(answer.read_text() if answer.exists() else '')
    rewards = G.grade_accuracy(fc, gold)
    details = {'answer_found': answer.exists(), 'parse_error': perr, 'forecast': fc}
    why = judge.unavailable()
    if why:
        details['judge'] = why
    else:
        try:
            verdicts, meta = judge_writeup(writeup, fc, gold)
        except judge.JudgeError as e:
            details['judge'] = f'not graded: write-up judge failed: {e}'
        else:
            rewards.update({k: v for k, v in G.grade_writeup(verdicts).items() if v is not None})
            details['judge'] = {**meta, **{i: f"{v['verdict']}: {v['reason']}" for i, v in verdicts.items()}}
    write_rewards(rewards, details)


if __name__ == '__main__':
    main()
