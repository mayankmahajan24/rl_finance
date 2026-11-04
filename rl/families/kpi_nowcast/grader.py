"""Grader for kpi_nowcast produce tasks.

Two parts from one agent response, kept as separate metrics:
  accuracy  programmatic: the forecast JSON block vs the task's tests/gold.json
  writeup   LLM judge: rubric C1-C12 (judge.md), pass/fail/na per item

The reward is skill_vs_naive clamped to [0, 1]: 0 for no better than last year's seasonal step, 1
for a perfect forecast. Everything else is a diagnostic. A response without a valid forecast JSON
gets schema_ok = 0, reward 0 and no other accuracy metrics (no answer is not a wrong number).
"""

from __future__ import annotations

import base64
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ITEMS = [f"C{i}" for i in range(1, 13)]
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


def grade_accuracy(fc: dict | None, gold: dict) -> dict:
    out = {"reward": 0.0, "schema_ok": 1.0 if fc else 0.0}
    if not fc:
        return out
    a = gold["actual"]
    err = abs(fc["point"] - a) / a
    out["abs_pct_error"] = round(err, 5)
    out["signed_pct_error"] = round((fc["point"] - a) / a, 5)
    if gold.get("naive_forecast"):
        naive_err = abs(gold["naive_forecast"] - a) / a
        # bounded skill in [-1, 1]: +1 perfect, 0 same as naive, -1 infinitely worse (1 - err/naive_err is unbounded below)
        out["skill_vs_naive"] = round((naive_err - err) / (naive_err + err), 4) if naive_err + err > 0 else 0.0
        out["reward"] = max(0.0, out["skill_vs_naive"])
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


def judge_prompt(task_user: str, as_of: str, writeup: str, fc: dict | None, gold: dict) -> tuple[str, str]:
    """(system, user) for the write-up judge; ask it with JUDGE_SCHEMA and the family's pinned judge
    config (families/_shared/judge.py `judge`)."""
    facts = {"as_of_date": as_of, "target_period": gold["target_period"], "actual_reported_value": gold["actual"],
             "unit": gold["unit"], "consensus_provided_to_author": gold.get("consensus") is not None,
             **gold["facts"]}
    user = (f"<task>\n{task_user}\n</task>\n\n<grader_facts>\n{json.dumps(facts, indent=2)}\n</grader_facts>\n\n"
            f"<forecast_json>\n{json.dumps(fc, indent=2) if fc else '(missing or invalid)'}\n</forecast_json>\n\n"
            f"<writeup>\n{writeup or '(empty)'}\n</writeup>")
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
