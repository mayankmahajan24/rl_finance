"""Harbor verifier for kpi_nowcast: grade /app/output/answer.md as the API runner grades a final message.

Writes reward.json: `reward`, skill_vs_naive clamped to [0, 1] (grader.py), and diagnostics never
blended into it: schema_ok, abs_pct_error, signed_pct_error, skill_vs_naive, covered,
interval_score_pct (programmatic), and writeup_score plus w_C1..w_C12 from the family's pinned model
judge (judge.md, judge.py, judge.json). The reward needs no judge; when the judge can't run (no
ANTHROPIC_API_KEY) or fails, the write-up metrics are left out and details say why.
"""
import json

import grader as G
import judge
from common import APP, TESTS, load_gold, write_rewards


def main():
    gold = load_gold()
    answer = APP / 'output' / 'answer.md'
    fc, writeup, perr = G.parse_response(answer.read_text() if answer.exists() else '')
    rewards = G.grade_accuracy(fc, gold)
    details = {'answer_found': answer.exists(), 'parse_error': perr, 'forecast': fc}
    why = judge.unavailable()
    if why:
        details['judge'] = why
    else:
        ctx = json.loads((TESTS / 'judge_context.json').read_text())
        system, user = G.judge_prompt(ctx['user'], ctx['as_of'], writeup, fc, gold)
        figures = G.figure_blocks(APP / 'output' / 'figures')
        # a chart the API rejects must not cost the run its write-up score: judge the text alone
        for content in ([{'type': 'text', 'text': user}] + figures, user) if figures else (user,):
            try:
                votes, meta = judge.judge(system, content, G.JUDGE_SCHEMA)
            except judge.JudgeError as e:
                details['judge'] = f'not graded: write-up judge failed: {e}'
            else:
                verdicts = judge.majority(votes, 'verdict')
                rewards.update({k: v for k, v in G.grade_writeup(verdicts).items() if v is not None})
                details['judge'] = {**meta, 'figures_judged': content is not user,
                                    **{i: f"{v['verdict']}: {v['reason']}" for i, v in verdicts.items()}}
                break
    write_rewards(rewards, details)


if __name__ == '__main__':
    main()
