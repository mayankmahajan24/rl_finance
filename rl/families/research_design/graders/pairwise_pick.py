"""Grader for compare-mode tasks: did the model pick the plan gold prefers?

Deterministic. Each task is shown in both orderings (AB and BA); a response's
`winner` is mapped back to the original slot before comparison, so a model that
always picks one position gets no credit for it.

    reward per ordering   1.0 if the pick matches gold, else 0.0
    reward per task       mean over the orderings supplied

Frame fields (goal_type, error_asymmetry) are reported as diagnostics only. They
are not in the reward because the case study found the pick is what the
human-confidence split discriminates on (sources/research_design_case/baseline_runs/GRADED.md).
"""

from __future__ import annotations


def original_pick(winner: str, ordering: str) -> str:
    """Winner in terms of the original slot, undoing the B/A swap."""
    return winner if ordering == "AB" else ("B" if winner == "A" else "A")


def grade(gold: dict, responses: dict[str, dict]) -> dict:
    """`responses` maps ordering ("AB"/"BA") to the parsed structured output."""
    picks = {o: original_pick(r["winner"], o) for o, r in responses.items()}
    hits = {o: p == gold["preference"] for o, p in picks.items()}
    return {
        "reward": sum(hits.values()) / len(hits),
        "breakdown": {
            "gold_preference": gold["preference"],
            "gold_strength": gold["preference_strength"],
            "picks": picks,
            "correct": hits,
            "both_orderings_correct": len(hits) == 2 and all(hits.values()),
            "goal_type_correct": {o: r.get("goal_type") == gold["goal_type"] for o, r in responses.items()},
            "error_asymmetry_correct": {o: r.get("error_asymmetry") == gold["error_asymmetry"]
                                        for o, r in responses.items()},
        },
    }
