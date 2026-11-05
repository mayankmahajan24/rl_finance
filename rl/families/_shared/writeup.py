"""Grade an agent's /app/output/writeup.md against its family's judge.md. Shipped in tests/ of a
generated task whose family has a judge.md.

The result is `writeup_score` (share of applicable rubric items passed) plus one w_<item> per item,
named metrics never blended into the reward. A missing or empty write-up scores 0 without a judge.
When the judge can't run or fails, the metrics are left out and details say why; the reward stands.
"""
import json
import re

import judge
from common import APP, TESTS, write_reward, write_rewards

MAX_CHARS = 30000


def read() -> str:
    f = APP / 'output' / 'writeup.md'
    return f.read_text(errors='replace') if f.is_file() else ''


def schema(items: list[str]) -> dict:
    return {'type': 'object', 'additionalProperties': False, 'required': items,
            'properties': {i: {'type': 'object', 'additionalProperties': False, 'required': ['verdict', 'reason'],
                               'properties': {'verdict': {'type': 'string', 'enum': ['pass', 'fail', 'na']},
                                              'reason': {'type': 'string'}}} for i in items}}


def score(verdicts: dict) -> dict:
    marks = {i: v['verdict'] == 'pass' for i, v in verdicts.items() if v['verdict'] != 'na'}
    if not marks:
        return {}
    return {'writeup_score': round(sum(marks.values()) / len(marks), 4), **{f'w_{i}': float(p) for i, p in marks.items()}}


def grade(text: str, facts: dict, material: dict[str, str]) -> tuple[dict, object]:
    """(metrics, details) for a write-up; `facts` are what the author never saw, `material` the
    author's other deliverables, by tag."""
    rubric = (TESTS / 'judge.md').read_text()
    items = re.findall(r'^- (W\d+):', rubric, re.M)
    if not text.strip():
        return {'writeup_score': 0.0, **{f'w_{i}': 0.0 for i in items}}, 'write-up missing or empty'
    why = judge.unavailable()
    if why:
        return {}, why
    parts = {'task': (TESTS / 'task_instruction.md').read_text(), 'grader_facts': json.dumps(facts, indent=1, default=str),
             **{k: v[:MAX_CHARS] for k, v in material.items()}, 'writeup': text[:MAX_CHARS]}
    try:
        votes, meta = judge.judge(rubric, '\n\n'.join(f'<{k}>\n{v}\n</{k}>' for k, v in parts.items()), schema(items))
    except judge.JudgeError as e:
        return {}, f'not graded: write-up judge failed: {e}'
    verdicts = judge.majority(votes, 'verdict')
    return score(verdicts), {**meta, **{i: f"{v['verdict']}: {v['reason']}" for i, v in verdicts.items()}}


def report(reward: float, details: dict, metrics: dict, judged) -> None:
    """reward.txt as before, and reward.json with the write-up metrics beside the reward."""
    reward = write_reward(reward, details)
    write_rewards({'reward': round(reward, 4), **metrics}, dict(details, writeup=judged))
