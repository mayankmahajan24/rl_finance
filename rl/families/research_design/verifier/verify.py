"""Harbor verifier for research_design and research_funding tasks.

tests/grader.json says how this task is graded:
  review   a scorer model (SCORER_MODEL, the case study's claude-opus-5 by default) matches the
           issues in /app/output/response.json to gold, then review_issues.grade turns that into
           recall minus penalties. Needs ANTHROPIC_API_KEY; without it nothing is graded.
  compare  pairwise_pick on the one ordering a Harbor agent sees (AB). run.py shows both orderings
           and averages them, which also cancels position bias; a Harbor score does not.
  none     no gold yet (context-flip items) or no rubric yet (produce): empty reward.json, and
           details say why.
"""
import json
import os

from common import APP, TESTS, write_reward, write_rewards


def main():
    cfg = json.loads((TESTS / 'grader.json').read_text())
    if cfg['mode'] is None:
        write_rewards({}, {'status': cfg['status'], 'note': 'no grader for this task yet'})
        return
    gold = json.loads((TESTS / 'gold.json').read_text())
    out = APP / 'output' / 'response.json'
    try:
        response = json.loads(out.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        write_reward(0.0, {'error': f'no valid /app/output/response.json: {e}'})
        return
    if cfg['mode'] == 'compare':
        import pairwise_pick
        g = pairwise_pick.grade(gold, {cfg['ordering']: response})
        write_reward(g['reward'], g['breakdown'])
        return
    if not os.environ.get('ANTHROPIC_API_KEY'):
        write_rewards({}, {'status': 'not graded', 'note': 'review grading needs ANTHROPIC_API_KEY for the scorer'})
        return
    import anthropic
    import review_issues
    model = os.environ.get('SCORER_MODEL', 'claude-opus-5')
    inputs = json.loads((TESTS / 'inputs.json').read_text())
    scored = review_issues.run_scorer(anthropic.Anthropic(), model, gold, inputs, response)
    g = review_issues.grade(gold, scored, **cfg['params'])
    write_reward(g['reward'], dict(g['breakdown'], scorer=model, scorer_result=scored))


if __name__ == '__main__':
    main()
