"""Shared helpers for the verifiers. Paths default to the Harbor container layout and can be
overridden with environment variables for local runs (see rl/harness/run_solutions.py)."""
import json
import os
from pathlib import Path

APP = Path(os.environ.get('APP_DIR', '/app'))
TESTS = Path(os.environ.get('TESTS_DIR', '/tests'))
LOGS = Path(os.environ.get('LOGS_DIR', '/logs'))


def load_gold():
    # every family declares `gold_file: gold.json` (family.yaml), so the verifiers share this name
    return json.loads((TESTS / 'gold.json').read_text())


def write_reward(reward: float, details: dict):
    reward = float(max(0.0, min(1.0, reward)))
    out = LOGS / 'verifier'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'reward.txt').write_text(f'{reward:.4f}\n')
    (out / 'details.json').write_text(json.dumps(dict(details, reward=reward), indent=1, default=str))
    print(json.dumps(dict(details, reward=round(reward, 4)), indent=1, default=str))
    return reward


def write_rewards(rewards: dict, details: dict):
    """The reward in [0, 1] under `reward`, plus named diagnostic metrics, to reward.json (Harbor reads
    it in place of reward.txt). An empty dict means the reward could not be graded here (its judge is
    unavailable); details say why."""
    assert not rewards or 0 <= rewards['reward'] <= 1, rewards
    out = LOGS / 'verifier'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'reward.json').write_text(json.dumps(rewards))
    (out / 'details.json').write_text(json.dumps(dict(details, rewards=rewards), indent=1, default=str))
    print(json.dumps(dict(details, rewards=rewards), indent=1, default=str))
    return rewards


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)
