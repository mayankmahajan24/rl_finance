"""Harbor verifier for kpi_nowcast: grade /app/output/answer.md as the API runner grades a final message.

Reads the brief and forecast from /app/output/answer.md and the methods note from methods.md.
Writes reward.json: `reward`, accuracy_reward (skill_vs_naive clamped to [0, 1], gated on the metric)
scaled by the write-up score (grader.py `blend`), and diagnostics: schema_ok, abs_pct_error,
signed_pct_error, skill_vs_naive, covered, interval_score_pct (programmatic), and writeup_score plus
w_C1..w_C39 from the family's pinned model judge (judge.md, judge.py, judge.json). When the judge
can't run (no ANTHROPIC_API_KEY) or fails, the write-up metrics are left out, reward is
accuracy_reward alone, and details say why.
"""
import json
import shutil

import grader as G
import judge
from common import APP, LOGS, TESTS, load_gold, write_rewards


def main():
    # keep the documents and charts with the run's logs, so a reviewer sees what the judge saw
    if (APP / 'output').is_dir():
        shutil.copytree(APP / 'output', LOGS / 'verifier' / 'output', dirs_exist_ok=True)
    gold = load_gold()
    answer = APP / 'output' / 'answer.md'
    fc, writeup, perr = G.parse_response(answer.read_text() if answer.exists() else '')
    rewards = G.grade_accuracy(fc, gold)
    details = {'answer_found': answer.exists(), 'parse_error': perr, 'forecast': fc}
    why = judge.unavailable()
    if why:
        details['judge'] = why
    else:
        import client
        ctx = json.loads((TESTS / 'judge_context.json').read_text())
        methods = APP / 'output' / 'methods.md'
        methods_text = methods.read_text(errors='replace') if methods.is_file() else ''
        system, user = G.judge_prompt(ctx['user'], ctx['as_of'], writeup, fc, gold, methods_text)
        figures = G.figure_blocks(APP / 'output' / 'figures')
        # a chart the API rejects must not cost the run its write-up score: judge the text alone
        for content in ([{'type': 'text', 'text': user}] + figures, user) if figures else (user,):
            try:
                votes, meta = judge.judge(system, content, G.JUDGE_SCHEMA)
            except (judge.JudgeError, client.anthropic.BadRequestError) as e:
                details['judge'] = f'not graded: write-up judge failed: {e}'
            else:
                verdicts = judge.majority(votes, 'verdict')
                # no chart saved fails the chart item; charts the API rejected are not counted against it
                n_figures = 0 if not figures else None
                rewards.update({k: v for k, v in G.grade_writeup(verdicts, n_figures, {'brief': writeup, 'methods': methods_text}).items() if v is not None})
                details['judge'] = {**meta, 'figures_judged': content is not user,
                                    **{i: f"{v['verdict']}: {v['reason']}" for i, v in verdicts.items()}}
                break
    if 'writeup_score' not in rewards and 'accuracy_reward' in rewards:
        details['reward_basis'] = 'accuracy only: the write-up was not judged'
    write_rewards(G.blend(rewards), details)


if __name__ == '__main__':
    main()
