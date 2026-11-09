"""Grader for kpi_nowcast produce tasks.

Two parts from one agent's output:
  accuracy  programmatic: the forecast JSON block (end of the brief, answer.md) vs the task's tests/gold.json
  writeup   LLM judge: rubric C1-C38 (judge.md), pass/fail/na per item, over the brief and the
            methods note (methods.md); each item grades the brief, the note, or both

The agent chooses the metric to nowcast, and each task has one right metric (gold: the series' KPI).
`metric_history` (the chosen metric's last four reported quarters) must match the gold KPI's
reported values, or the reward is 0 (metric_ok = 0). With the right metric, accuracy_reward is
skill_vs_naive clamped to [0, 1]: 0 for no better than last year's seasonal step, 1 for a perfect
forecast. The write-up scales it: reward = accuracy_reward * (0.5 + 0.5 * writeup_score), so a
good write-up can't earn reward for a forecast with no skill, and a poor one halves it at most.
When the judge can't run, reward is accuracy_reward alone and the verifier's details say so.
Everything else is a diagnostic. A response without a valid forecast JSON gets
schema_ok = 0, reward 0 and no other accuracy metrics (no answer is not a wrong number).
"""

from __future__ import annotations

import base64
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ITEMS = [f"C{i}" for i in range(1, 39)]
MATCH = 0.005          # a metric_history value matches a reported value within 0.5%
INTERVAL_LEVEL = 0.95
MAX_FIGURES = 4
MAX_FIGURE_BYTES = 3_500_000   # the API's 5 MB image limit applies after base64
PNG = b"\x89PNG\r\n\x1a\n"
JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)
REQUIRED = ["target_period", "point", "low", "high", "interval_level", "in_sample"]


def parse_response(text: str) -> tuple[dict | None, str, str | None]:
    """(forecast, writeup, parse_error). The forecast is the last ```json block; the write-up is the text before it."""
    blocks = list(JSON_BLOCK.finditer(text or ""))
    if not blocks:
        return None, (text or "").strip(), "no ```json block"
    m = blocks[-1]
    writeup = text[:m.start()].strip()
    try:
        fc = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return None, writeup, f"invalid JSON: {e}"
    missing = [k for k in REQUIRED if k not in fc]
    if missing:
        return None, writeup, f"missing fields: {missing}"
    try:
        for k in ("point", "low", "high", "interval_level"):
            fc[k] = float(fc[k])
    except (TypeError, ValueError) as e:
        return None, writeup, f"non-numeric field: {e}"
    if not (fc["low"] <= fc["point"] <= fc["high"]) or fc["interval_level"] != INTERVAL_LEVEL:
        return None, writeup, f"range does not contain point, or interval_level is not {INTERVAL_LEVEL}"
    return fc, writeup, None


def winkler(low: float, high: float, actual: float, level: float) -> float:
    """Interval score: width, plus 2/alpha times the miss distance when the actual falls outside."""
    alpha = 1 - level
    s = high - low
    if actual < low:
        s += 2 / alpha * (low - actual)
    elif actual > high:
        s += 2 / alpha * (actual - high)
    return s


def metric_ok(fc: dict, gold: dict) -> bool:
    """True when metric_history gives, for each of the gold KPI's last four quarters, a value that matches
    one of that quarter's reported values (first report or a restatement): the agent tracked the right metric."""
    given = {}
    for h in fc.get("metric_history") or []:
        try:
            given[str(h["period_end"])] = float(h["value"])
        except (KeyError, TypeError, ValueError):
            continue
    return all(e in given and any(abs(given[e] - v) <= MATCH * abs(v) for v in vs)
               for e, vs in gold["metric_history"].items())


def grade_accuracy(fc: dict | None, gold: dict) -> dict:
    out = {"reward": 0.0, "schema_ok": 1.0 if fc else 0.0}
    if not fc:
        return out
    a = gold["actual"]
    err = abs(fc["point"] - a) / a
    out["metric_ok"] = 1.0 if metric_ok(fc, gold) else 0.0
    out["abs_pct_error"] = round(err, 5)
    out["signed_pct_error"] = round((fc["point"] - a) / a, 5)
    if gold.get("naive_forecast"):
        naive_err = abs(gold["naive_forecast"] - a) / a
        # bounded skill in [-1, 1]: +1 perfect, 0 same as naive, -1 infinitely worse (1 - err/naive_err is unbounded below)
        out["skill_vs_naive"] = round((naive_err - err) / (naive_err + err), 4) if naive_err + err > 0 else 0.0
        out["reward"] = max(0.0, out["skill_vs_naive"]) if out["metric_ok"] else 0.0
        out["accuracy_reward"] = out["reward"]
    if gold.get("consensus"):
        cons_err = abs(gold["consensus"] - a) / a
        out["skill_vs_consensus"] = round((cons_err - err) / (cons_err + err), 4) if cons_err + err > 0 else 0.0
        truth = "above" if a > gold["consensus"] else "below"
        out["direction_vs_consensus"] = 1.0 if fc.get("vs_consensus") == truth else 0.0
    out["covered"] = 1.0 if fc["low"] <= a <= fc["high"] else 0.0
    # interval score in % of actual, so cases of different size are comparable
    out["interval_score_pct"] = round(winkler(fc["low"], fc["high"], a, fc["interval_level"]) / a, 5)
    return {k: v for k, v in out.items() if v is not None}


JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ITEMS,
    "properties": {i: {"type": "object", "additionalProperties": False, "required": ["verdict", "reason"],
                       "properties": {"verdict": {"type": "string", "enum": ["pass", "fail", "na"]},
                                      "reason": {"type": "string"}}} for i in ITEMS},
}


def judge_prompt(task_user: str, as_of: str, writeup: str, fc: dict | None, gold: dict,
                 methods: str = "") -> tuple[str, str]:
    """(system, user) for the write-up judge; ask it with JUDGE_SCHEMA and the family's pinned judge
    config (families/_shared/judge.py `judge`)."""
    facts = {"as_of_date": as_of, "target_period": gold["target_period"], "actual_reported_value": gold["actual"],
             "metric_history_matches_correct_metric": metric_ok(fc, gold) if fc else None,
             "unit": gold["unit"], "consensus_provided_to_author": gold.get("consensus") is not None,
             **gold["facts"]}
    user = (f"<task>\n{task_user}\n</task>\n\n<grader_facts>\n{json.dumps(facts, indent=2)}\n</grader_facts>\n\n"
            f"<forecast_json>\n{json.dumps(fc, indent=2) if fc else '(missing or invalid)'}\n</forecast_json>\n\n"
            f"<brief>\n{writeup or '(empty)'}\n</brief>\n\n<methods_note>\n{methods.strip() or '(missing or empty)'}\n</methods_note>")
    return (HERE / "judge.md").read_text(), user


def figure_blocks(folder: pathlib.Path) -> list[dict]:
    """Content blocks for the author's charts: the first MAX_FIGURES valid PNGs, each after its name."""
    blocks = []
    for f in sorted(folder.glob("*.png"))[:MAX_FIGURES] if folder.is_dir() else []:
        data = f.read_bytes()
        if data.startswith(PNG) and len(data) <= MAX_FIGURE_BYTES:
            blocks += [{"type": "text", "text": f"figures/{f.name}"},
                       {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                    "data": base64.b64encode(data).decode()}}]
    return blocks


def grade_writeup(verdicts: dict) -> dict:
    applicable = [i for i in ITEMS if verdicts[i]["verdict"] != "na"]
    passed = [i for i in applicable if verdicts[i]["verdict"] == "pass"]
    out = {"writeup_score": round(len(passed) / len(applicable), 4) if applicable else None}
    for i in ITEMS:
        v = verdicts[i]["verdict"]
        if v != "na":
            out[f"w_{i}"] = 1.0 if v == "pass" else 0.0
    return out


def blend(rewards: dict) -> dict:
    """Scale the accuracy reward by the write-up score, once the judge has graded it."""
    if "accuracy_reward" in rewards and rewards.get("writeup_score") is not None:
        rewards["reward"] = round(rewards["accuracy_reward"] * (0.5 + 0.5 * rewards["writeup_score"]), 4)
    return rewards
