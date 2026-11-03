"""Shared helpers for the verifiers. Paths default to the Harbor container layout and can be
overridden with environment variables for local runs (see run_local.py)."""
import json
import os
from pathlib import Path

APP = Path(os.environ.get('APP_DIR', '/app'))
TESTS = Path(os.environ.get('TESTS_DIR', '/tests'))
LOGS = Path(os.environ.get('LOGS_DIR', '/logs'))


def load_truth():
    return json.loads((TESTS / 'ground_truth.json').read_text())


def write_reward(reward: float, details: dict):
    reward = float(max(0.0, min(1.0, reward)))
    out = LOGS / 'verifier'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'reward.txt').write_text(f'{reward:.4f}\n')
    (out / 'details.json').write_text(json.dumps(dict(details, reward=reward), indent=1, default=str))
    print(json.dumps(dict(details, reward=round(reward, 4)), indent=1, default=str))
    return reward


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)
