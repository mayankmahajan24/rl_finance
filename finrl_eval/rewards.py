"""Reward export.

`rewards.jsonl` has one record per sample. `reward` is the rubric aggregate from
0 to 1. Per-dimension rewards let a trainer re-weight a miss, such as a GAAP
and non-GAAP mix-up, without running the eval again. `hard_constraint_violation`
lets a later step apply a floor penalty for unparseable or rule-breaking output.
"""

from __future__ import annotations

from pathlib import Path

from finrl_eval.schema import RewardRecord


def write_rewards(run_dir: Path, rewards: list[RewardRecord]) -> Path:
    path = run_dir / "rewards.jsonl"
    with path.open("w") as fh:
        for r in rewards:
            fh.write(r.model_dump_json() + "\n")
    return path


def shaped_reward(
    record: RewardRecord,
    dimension_weights: dict[str, float] | None = None,
    hard_violation_penalty: float = 0.5,
) -> float:
    """Example reward-shaping helper: reweight dimensions and penalise hard violations.

    Returns a value in [-hard_violation_penalty, 1]."""
    if not dimension_weights:
        base = record.reward
    else:
        total = sum(w for d, w in dimension_weights.items() if d in record.dimension_rewards)
        base = (
            sum(
                record.dimension_rewards[d] * w
                for d, w in dimension_weights.items()
                if d in record.dimension_rewards
            )
            / total
            if total
            else record.reward
        )
    if record.hard_constraint_violation:
        base -= hard_violation_penalty
    return round(max(-hard_violation_penalty, min(1.0, base)), 4)
