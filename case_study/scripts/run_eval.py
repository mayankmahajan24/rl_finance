"""Run the Part 2 discriminator eval across models.

Same items, same prompt text, different models — that is the whole design. The
eval is the measuring instrument; changing it per model would mean comparing two
instruments rather than two models. Only harness settings (max_tokens) vary, and
they are recorded in the output.

Structured outputs force every model to emit the same shape, so weaker models are
not hand-tuned into parseability.

Pairwise runs each pair BOTH ways (A/B and B/A) to measure position bias.

Usage:
    python scripts/run_eval.py --mode pairwise --model claude-opus-5
    python scripts/run_eval.py --mode pointwise --model claude-haiku-4-5
    python scripts/run_eval.py --mode both --model claude-sonnet-5 --items S1 S2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import time
from concurrent.futures import ThreadPoolExecutor

import anthropic

ROOT = pathlib.Path(__file__).resolve().parent.parent
P2 = ROOT / "part2"

TENET_CATEGORIES = [
    "goal_mismatch",           # 1  answers a different question
    "firm_fit",                # 2  unbuildable, wrong concerns, or wrong sophistication
    "error_asymmetry",         # 2  burden of proof mismatched to the payoff structure
    "no_edge",                 # 3  never establishes what is incremental
    "unnecessary_complexity",  # 4  machinery that has not earned its place
    "proxy_substitution",      # 5  predicts an adjacent quantity, or an unvalidated proxy
    "measure_validity",        # 5  metric breaks or changes meaning across the sample
    "horizon_mismatch",        # 6  horizon follows the data, not the phenomenon
    "evidence_standard",       # 7  over-demanding, or no way to judge the output
    "evidence_hierarchy",      # 7  generalizes where a specific record exists
    "breadth",                 # 8  no negative controls where the mechanism implies them
    "sequencing",              # 9  misordered, non-adaptive, or unjustified spend
    "human_oversight",         # 10 nothing inspectable mid-run; explainability mismatched
    "falsification",           # 11 no stated falsifier, other side not engaged
    "invented_economics",      # 12 magnitude asserted that nothing produces
    "validity",                #    ordinary technical defect
    "other",
]

# One issue list, not parallel arrays — a finding appears exactly once, so precision
# has a clean denominator. `category` maps each issue to the tenet it violates.
ISSUE = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "The defect in one sentence."},
        "severity": {"type": "string", "enum": ["blocking", "secondary"]},
        "category": {"type": "string", "enum": TENET_CATEGORIES},
        "why_it_applies_here": {
            "type": "string",
            "description": (
                "Why this bites THIS design — this data, this construction, this claim. A "
                "justification that would read identically against any plan in the asset class "
                "has not been earned; drop the issue instead."
            ),
        },
        "what_breaks": {
            "type": "string",
            "description": "Which step, and what goes wrong downstream of it.",
        },
        "fix": {"type": "string", "description": "What it would take to fix or kill it."},
    },
    "required": ["summary", "severity", "category", "why_it_applies_here", "what_breaks", "fix"],
    "additionalProperties": False,
}

GOAL_TYPES = ["single_name_kpi", "broad_market_effect", "mechanism_test",
              "blind_fit_oos", "capability_build"]

PAIRWISE_SCHEMA = {
    "type": "object",
    "properties": {
        "winner": {"type": "string", "enum": ["A", "B"]},
        "confidence": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        # --- frame (tenets 1-2): these condition everything below ---
        "goal_type": {"type": "string", "enum": GOAL_TYPES},
        "error_asymmetry": {
            "type": "string",
            "enum": ["type_i_dominant", "type_ii_dominant", "symmetric"],
            "description": (
                "Which error costs more in this setting. type_i_dominant = concentrated, "
                "explicit loss, asymmetric downside. type_ii_dominant = capped downside with "
                "unbounded upside, or symmetric payoff run with breadth."
            ),
        },
        # --- the choice ---
        "decisive_tenets": {
            "type": "array",
            "items": {"type": "string", "enum": TENET_CATEGORIES},
            "description": (
                "Which tenets actually drove the choice, most important first. Usually one or "
                "two. Listing many means nothing decided it."
            ),
        },
        "key_differentiator": {
            "type": "string",
            "description": "The single consideration that decided it, in one sentence.",
        },
        "rationale": {"type": "string"},
        "issues_with_winner": {"type": "array", "items": {"type": "string"}},
        "issues_with_loser": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "winner", "confidence", "goal_type", "error_asymmetry",
        "decisive_tenets", "key_differentiator", "rationale",
        "issues_with_winner", "issues_with_loser",
    ],
    "additionalProperties": False,
}

POINTWISE_SCHEMA = {
    "type": "object",
    "properties": {
        # --- A. frame: read the setting before judging the design ---
        "goal_type": {"type": "string", "enum": GOAL_TYPES},
        "plan_implied_asker": {
            "type": "string",
            "description": (
                "What kind of firm this plan appears WRITTEN for — assumed horizon, "
                "infrastructure, and what it treats as the risk that matters. One short phrase."
            ),
        },
        "fits_firm": {"type": "string", "enum": ["yes", "partly", "no"]},
        "error_asymmetry": {
            "type": "string",
            "enum": ["type_i_dominant", "type_ii_dominant", "symmetric"],
            "description": (
                "Which error costs more here, from the payoff structure. type_i_dominant = "
                "concentrated with explicit loss; a false positive cannot be diversified away. "
                "type_ii_dominant = capped downside with unbounded upside, or symmetric payoff "
                "with breadth; a missed real effect is the expensive error."
            ),
        },
        "edge_basis": {
            "type": "string",
            "enum": ["variant_view", "speed", "better_measurement",
                     "none_established", "not_applicable"],
            "description": (
                "What the edge would be if this worked. none_established = never says what is "
                "incremental, so it confirms what is already priced (blocking). "
                "not_applicable = a capability build."
            ),
        },
        # --- B. design ---
        "error_posture_fit": {
            "type": "string",
            "enum": ["appropriate", "too_permissive", "too_conservative"],
            "description": (
                "Does the burden of proof match the asymmetry above? Judge against the setting, "
                "never against a fixed standard of rigor."
            ),
        },
        "method_sophistication_fit": {
            "type": "string",
            "enum": ["appropriate", "too_sophisticated_for_audience",
                     "too_naive_for_audience", "sophisticated_but_corroborated"],
            "description": (
                "Can the audience evaluate and defend the method? "
                "sophisticated_but_corroborated = complex method plus a simple check they can "
                "verify themselves, which resolves the tension."
            ),
        },
        "target_vs_proxy": {
            "type": "string",
            "enum": ["measures_target", "validated_proxy", "unvalidated_proxy", "wrong_target"],
            "description": (
                "wrong_target = predicts an easier adjacent quantity than the one asked about."
            ),
        },
        "horizon_fit": {
            "type": "string",
            "enum": ["appropriate", "too_long", "too_short", "not_stated"],
        },
        "evidence_standard": {
            "type": "string",
            "enum": ["appropriate", "over_demanding", "under_specified"],
            "description": (
                "over_demanding = requires significance the setting cannot produce, or pools "
                "units to manufacture N. under_specified = low N with no stated way to judge "
                "success."
            ),
        },
        # --- C. execution ---
        "front_loads_kill": {
            "type": "string",
            "enum": ["yes", "no", "not_applicable"],
            "description": (
                "Could the plan be stopped after its early steps and still have taught you "
                "something? no = the first usable output arrives only at the end."
            ),
        },
        "adaptive_flow": {
            "type": "string",
            "enum": ["yes", "partly", "no"],
            "description": (
                "Does it say what changes depending on intermediate results? no = a fixed "
                "pipeline scheduled in advance."
            ),
        },
        "effort_proportionate": {
            "type": "string",
            "enum": ["yes", "over_scoped", "under_scoped"],
        },
        "explainability_fit": {
            "type": "string",
            "enum": ["appropriate", "over_demanded", "under_delivered"],
        },
        # --- D. honesty ---
        "what_would_falsify": {
            "type": "string",
            "description": (
                "The specific result the plan commits to as grounds for abandoning the "
                "hypothesis. 'NONE STATED' if it names none — a blocking gap."
            ),
        },
        "other_side_considered": {
            "type": "string",
            "enum": ["yes", "superficial", "no", "not_applicable"],
        },
        # --- findings ---
        "issues": {"type": "array", "items": ISSUE},
        "overall": {"type": "string", "description": "Two or three sentences. The verdict."},
    },
    "required": [
        "goal_type", "plan_implied_asker", "fits_firm", "error_asymmetry", "edge_basis",
        "error_posture_fit", "method_sophistication_fit", "target_vs_proxy", "horizon_fit",
        "evidence_standard", "front_loads_kill", "adaptive_flow", "effort_proportionate",
        "explainability_fit", "what_would_falsify", "other_side_considered",
        "issues", "overall",
    ],
    "additionalProperties": False,
}


def load_prompt(name: str) -> tuple[str, str]:
    """Split an evaluator prompt file into (system, user_template)."""
    text = (P2 / "evaluator" / f"{name}.md").read_text()
    m = re.search(r"^## SYSTEM\s*$(.*?)^## USER\s*$(.*)", text, re.S | re.M)
    if not m:
        raise SystemExit(f"{name}.md must contain '## SYSTEM' and '## USER' markers")
    return m.group(1).strip(), m.group(2).strip()


def fingerprint(*parts: str) -> str:
    """Short hash of the exact prompt text, so a later run can prove it used the same
    instrument. If this differs between models, the comparison is invalid."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
    return h.hexdigest()[:12]


def call(client, model: str, system: str, user: str, schema: dict, max_tokens: int) -> dict:
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("truncated: raise --max-tokens")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text), {"in": msg.usage.input_tokens, "out": msg.usage.output_tokens}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["pairwise", "pointwise", "both"], default="both")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--items", nargs="*", help="seed ids; default all")
    ap.add_argument("--max-tokens", type=int, default=32000)  # weaker models emit very long issue lists; same cap for every model
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    def order(p):  # S1..S10 then flips (S5F, S8F, ...)
        s = p.stem
        return (s.endswith("F"), int(s[1:].rstrip("F")))

    paths = sorted((P2 / "items").glob("*.json"), key=order)
    items = [json.loads(p.read_text()) for p in paths]
    if args.items:
        keep = set(args.items)
        items = [i for i in items if i["id"] in keep]

    client = anthropic.Anthropic()
    outdir = P2 / "runs" / args.model
    outdir.mkdir(parents=True, exist_ok=True)
    modes = ["pairwise", "pointwise"] if args.mode == "both" else [args.mode]

    for mode in modes:
        system, template = load_prompt(mode)
        jobs = []

        if mode == "pairwise":
            for it in items:
                # Both orders: catches an evaluator that just prefers a position.
                jobs.append((it["id"], "AB", template.format(
                    context=it["context"], seed=it["seed"],
                    plan_A=it["plan_A"], plan_B=it["plan_B"])))
                jobs.append((it["id"], "BA", template.format(
                    context=it["context"], seed=it["seed"],
                    plan_A=it["plan_B"], plan_B=it["plan_A"])))
            schema = PAIRWISE_SCHEMA
        else:
            for it in items:
                for slot in ("A", "B"):
                    jobs.append((it["id"], slot, template.format(
                        context=it["context"], seed=it["seed"],
                        plan=it[f"plan_{slot}"])))
            schema = POINTWISE_SCHEMA

        def run(job):
            iid, tag, user = job
            usage = {}
            try:
                out, usage = call(client, args.model, system, user, schema, args.max_tokens)
                status = "ok"
            except Exception as e:  # record rather than abort the sweep
                out, status = {"error": f"{type(e).__name__}: {e}"}, "error"
            print(f"  {mode:9s} {iid:>4} {tag}  {status}")
            return {"id": iid, "tag": tag, "status": status, "usage": usage, "result": out}

        print(f"{args.model} · {mode} · {len(jobs)} calls")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(run, jobs))

        n_err = sum(1 for r in results if r["status"] == "error")
        payload = {
            "model": args.model,
            "mode": mode,
            "max_tokens": args.max_tokens,
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "prompt_fingerprint": fingerprint(system, template),
            "schema_fingerprint": fingerprint(json.dumps(schema, sort_keys=True)),
            "n_calls": len(results),
            "n_errors": n_err,
            "tokens_in": sum(r["usage"].get("in", 0) for r in results),
            "tokens_out": sum(r["usage"].get("out", 0) for r in results),
            "results": results,
        }
        out = outdir / f"{mode}.json"
        out.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"  -> {out.relative_to(ROOT)}  ({len(results)} calls, {n_err} errors, "
              f"{payload['tokens_out']:,} out)")


if __name__ == "__main__":
    main()
