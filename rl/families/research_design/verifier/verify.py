"""Harbor verifier for research_design and research_funding tasks.

tests/grader.json says how this task is graded:
  review   the pinned scorer model (judge.json; the case study's claude-opus-5) matches the issues in
           /app/output/response.json to gold through the shared judge (judge.py), then
           review_issues.grade turns that into recall minus penalties. Needs ANTHROPIC_API_KEY;
           without it, or if the scorer fails, nothing is graded and details say why.
  compare  the agent answers the pair in both orders ({"AB": ..., "BA": ...}); pairwise_pick maps each
           pick back to its plan. The reward is 1 only when both picks name gold's plan: a correct,
           order-consistent pick. Always answering "A" scores 0, and answering at random 0.25 in
           expectation, below a consistent coin flip's 0.5. The mean over the two orders (what run.py
           reports) is a diagnostic.

A missing or malformed response scores 0, with details saying what was wrong.
"""
import json

from common import APP, TESTS, load_gold, write_reward, write_rewards

ORDERINGS = ('AB', 'BA')


def malformed(cfg, response):
    """Why the response can't be graded, or None."""
    if not isinstance(response, dict):
        return 'response.json is not an object'
    if cfg['mode'] == 'compare':
        bad = [o for o in ORDERINGS if not isinstance(response.get(o), dict) or response[o].get('winner') not in ('A', 'B')]
        return f'no winner "A" or "B" for ordering {", ".join(bad)}' if bad else None
    issues = response.get('issues')
    if not isinstance(issues, list) or not all(isinstance(i, dict) for i in issues):
        return 'response.json has no list of issue objects under "issues"'
    return None


def main():
    cfg = json.loads((TESTS / 'grader.json').read_text())
    gold = load_gold()
    try:
        response = json.loads((APP / 'output' / 'response.json').read_text())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return write_reward(0.0, {'error': f'no valid /app/output/response.json: {e}'})
    why = malformed(cfg, response)
    if why:
        return write_reward(0.0, {'error': why})
    if cfg['mode'] == 'compare':
        import pairwise_pick
        g = pairwise_pick.grade(gold, {o: response[o] for o in ORDERINGS})
        return write_reward(float(g['breakdown']['both_orderings_correct']),
                            dict(g['breakdown'], mean_over_orderings=g['reward']))
    import judge
    import review_issues
    why = judge.unavailable()
    if why:
        return write_rewards({}, {'status': 'not graded', 'note': f'review grading needs the scorer: {why}'})
    inputs = json.loads((TESTS / 'inputs.json').read_text())
    try:
        scored, meta = review_issues.run_scorer(judge.judge, gold, inputs, response)
    except judge.JudgeError as e:
        return write_rewards({}, {'status': 'not graded', 'note': f'scorer failed: {e}'})
    g = review_issues.grade(gold, scored, **cfg['params'])
    return write_reward(g['reward'], dict(g['breakdown'], scorer=meta, scorer_result=scored))


if __name__ == '__main__':
    main()
