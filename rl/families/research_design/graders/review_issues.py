"""Grader for review-mode tasks: recall of gold's blocking issues, minus a penalty
for objections that do not apply.

Two steps:

1. A scorer model (prompt in review_scorer.md) matches the model's issues to the
   gold issues and buckets every model issue as matched / real_unlisted /
   manufactured / contradicts_gold. This is the semantic step from
   the case study's scripts/score_issues.py (commit a75441c), unchanged.
2. `grade()` turns that into a reward. Deterministic.

    recall   = blocking gold issues surfaced / blocking gold issues
               (1.0 when gold has no blocking issue: raising none is correct)
    penalty  = 0.1 x manufactured + 0.2 x contradicts_gold
    reward   = clamp(recall - penalty, 0, 1)

The penalty is why this reward is hard to game. The case study's shotgun reviewer
(Haiku 4.5) reached 53% recall by raising 28.6 issues per review, 14.3 of them
manufactured; a recall-only reward would pay it for that. Contradicting gold costs
double because the expert ruled that objection out in writing.

The penalty weights are v0. They reproduce the case-study ordering of models but
have not been calibrated against a second expert. Set them per task in
task.yaml `grader.params`.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def grade(gold: dict, scorer_result: dict, penalty_manufactured: float = 0.1,
          penalty_contradicts_gold: float = 0.2) -> dict:
    blocking = [i for i in gold["issues"] if i["label"] == "blocking"]
    seen = {x["gold_ref"]: x for x in scorer_result["gold_recall"]}
    surfaced = []
    for b in blocking:
        hit = seen.get(f"blocking#{b['n']}") or seen.get(str(b["n"])) or {}
        surfaced.append(bool(hit.get("surfaced")))
    recall = sum(surfaced) / len(surfaced) if surfaced else 1.0

    buckets = {k: 0 for k in ("matched", "real_unlisted", "manufactured", "contradicts_gold")}
    uncertain = 0
    for x in scorer_result["issue_buckets"]:
        buckets[x["bucket"]] += 1
        uncertain += bool(x.get("uncertain")) and x["bucket"] == "real_unlisted"
    penalty = (penalty_manufactured * buckets["manufactured"]
               + penalty_contradicts_gold * buckets["contradicts_gold"])

    return {
        "reward": max(0.0, min(1.0, recall - penalty)),
        "breakdown": {
            "recall": recall,
            "blocking_total": len(blocking),
            "blocking_surfaced": sum(surfaced),
            "issues_raised": sum(buckets.values()),
            **buckets,
            "uncertain_real_unlisted": uncertain,
            "penalty": penalty,
        },
    }


def format_gold(rows: list[dict]) -> str:
    tag = {"blocking": "BLOCKING", "secondary": "secondary",
           "anti_objection": "EXPLICITLY RULED OUT BY THE REVIEWER",
           "praise": "praise (not an issue)"}
    return "\n\n".join(f"[{r['label']}#{r['n']}] ({tag[r['label']]})\n{r['text']}" for r in rows)


def format_issues(issues: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] severity={x['severity']} category={x['category']}\n"
        f"    summary: {x['summary']}\n"
        f"    why_it_applies_here: {x['why_it_applies_here']}\n"
        f"    what_breaks: {x['what_breaks']}"
        for i, x in enumerate(issues)
    )


def run_scorer(client, model: str, gold: dict, inp: dict, response: dict,
               max_tokens: int = 48000) -> dict:
    """Call the scorer model on one response. The scorer sees the same context, seed
    and plan the model saw (the task's inputs.json) plus the gold issues."""
    import re
    text = (HERE / "review_scorer.md").read_text()
    m = re.search(r"^## SYSTEM\s*$(.*?)^## USER\s*$(.*)", text, re.S | re.M)
    system, template = m.group(1).strip(), m.group(2).strip()
    issues = response["issues"]
    user = template.format(context=inp["context"], seed=inp["seed"], plan=inp["plan"],
                           gold=format_gold(gold["issues"]),
                           issues=format_issues(issues), n=len(issues))
    schema = json.loads((HERE / "review_scorer_schema.json").read_text())
    with client.messages.stream(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    ) as stream:
        msg = stream.get_final_message()
    return json.loads(next(b.text for b in msg.content if b.type == "text"))
