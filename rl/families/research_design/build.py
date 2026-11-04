"""Build the research_design and research_funding tasks from rl/sources/research_design_case/.

Idempotent: wipes and regenerates the rd-* tasks, and rewrites splits/manifests/research_design.json.
Nothing else is touched.

What gets built (tasks in Harbor layout, families/_shared/harbor.py), graded tasks only:

  tasks/eval/rd-review-*          review tasks (item x plan) whose gold has blocking-issue labels
  tasks/eval/rd-funding-*         pairwise funding decisions whose gold has a preference

Not built until they can be graded: the context-flip items' tasks (gold never filled,
grader_only/gold/HOW-TO-FILL.md) and produce tasks (seed + firm -> plan; no expert rubric yet).

All are split `eval`: one eval set until whole worlds can be held out (FORMAT.md). A task's `case`
is its research question (the seed): an item and its context flip share it.

prompt/ holds the exact messages the API runner (rl/harness/run_api.py) sends (system.md, user.md or user.AB.md + user.BA.md,
inputs.json); their template is what the fingerprint covers. instruction.md is the same text for a
Harbor agent, plus where to write the answer. A compare task's Harbor copy shows the pair in both
orders and asks for both answers, as the API runner does with two calls, so position bias earns nothing.
tests/ holds gold, the graders and verifier/verify.py; solution/ the reference answer (gold's).

The source data, and what was deliberately left out of it, is described in
rl/sources/research_design_case/README.md.

Usage:
    python rl/build.py research_design   (or this file directly)
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import lib  # noqa: E402
import splits  # noqa: E402
from families._shared import harbor  # noqa: E402
from lib import RL, TASKS, fingerprint, load_prompt  # noqa: E402

DATA = RL / "sources" / "research_design_case"
GOLD = DATA / "grader_only" / "gold"
SRC = "sources/research_design_case"   # prefix for `sources` paths, relative to rl/
HERE = RL / "families" / "research_design"
PROMPTS = HERE / "prompts"
GRADERS = HERE / "graders"
REFERENCE = HERE / "solutions" / "reference"
OUT = TASKS / splits.UNSPLIT
ORDERINGS = {"AB": ("plan_A", "plan_B"), "BA": ("plan_B", "plan_A")}

SCHEMA_NOTE = ("---\nWrite your answer as one JSON object matching the schema in /app/data/output_schema.json, "
               "to /app/output/response.json.")
COMPARE_NOTE = ("---\nYou are shown the same two plans twice, in both orders. Decide each ordering on its own "
                "merits. Write one JSON object to /app/output/response.json with your answer for each ordering, "
                '{"AB": ..., "BA": ...}, each matching its part of the schema in /app/data/output_schema.json. '
                "Only a pick that names the same plan in both orderings can earn credit.")

# Seed style decides which analyst role owns the research-design work.
ROLE_BY_STYLE = {"quant": "quant_researcher", "fundamental": "fundamental_analyst"}


def load() -> dict:
    seeds = {s["id"]: s for s in json.loads((DATA / "seeds.json").read_text())["seeds"]}
    ctx = json.loads((DATA / "contexts.json").read_text())
    items = {p.stem: json.loads(p.read_text()) for p in (DATA / "items").glob("*.json")}
    gold = {p.stem: json.loads(p.read_text()) for p in GOLD.glob("S*.json")}
    issues = json.loads((GOLD / "_issues.json").read_text())["items"]
    manifest = json.loads((DATA / "plan_manifest.json").read_text())
    return dict(seeds=seeds, ctx=ctx, items=items, gold=gold, issues=issues, manifest=manifest)


def is_filled(g: dict) -> bool:
    return any(v not in ("", [], None) for k, v in g.items() if not k.startswith("_"))


def order(sid: str) -> tuple:
    return (sid.endswith("F"), int(sid[1:].rstrip("F")))


def token_for(manifest: dict, seed: str, slot: str) -> str | None:
    rows = manifest.get("tokens", manifest)
    for tok, v in rows.items():
        if isinstance(v, dict) and v.get("seed_id") == seed and v.get("slot") == slot:
            return tok
    return None


def base_task(tid, case, role, workflow, mode, world, sources, prompt_file, extra):
    system, template = load_prompt(prompt_file)
    t = {"id": tid, "family": "research_design", "case": case, "source": "research_design_case", "role": role,
         "workflow": workflow, "mode": mode, "world": world, "status": "graded", "split": splits.UNSPLIT,
         "fingerprint": fingerprint(system, template), "prompt": {"template": str(prompt_file.relative_to(RL))},
         "sources": sources, **extra}
    return t, system, template


def build_review(d: dict, write) -> None:
    prompt = PROMPTS / "review.md"
    for sid in sorted(d["items"], key=order):
        it = d["items"][sid]
        base = it.get("flip_of", sid)
        g = d["gold"].get(sid, {})
        for slot in ("A", "B"):
            gold_issues = d["issues"].get(sid, {}).get(slot)
            if not gold_issues:
                continue
            t, system, template = base_task(
                f"rd-review-{sid}-{slot}", base, ROLE_BY_STYLE[d["seeds"][base]["style"]], "research_design",
                "review", it["firm"],
                [f"{SRC}/items/{sid}.json", f"{SRC}/grader_only/gold/{sid}.json",
                 f"{SRC}/grader_only/gold/_issues.json"],
                prompt,
                {
                    "output_schema": "families/research_design/schemas/review.json",
                    "grader": {
                        "type": "review_issues",
                        "module": "families/research_design/graders/review_issues.py",
                        "params": {"penalty_manufactured": 0.1, "penalty_contradicts_gold": 0.2},
                    },
                    "meta": {
                        "seed": base,
                        "plan_slot": slot,
                        "plan_token": token_for(d["manifest"], base, slot),
                        "context_flip": sid != base,
                        "seed_style": d["seeds"][base]["style"],
                    },
                },
            )
            inputs = {"context": it["context"], "seed": it["seed"], "plan": it[f"plan_{slot}"]}
            user = harbor.render(template, **inputs)
            gold = {
                "issues": gold_issues,
                "frame": {"goal_type": g.get("goal_type"), "error_asymmetry": g.get("error_asymmetry")},
                "critique_prose": g.get(f"critique_{slot}"),
                "provenance": {
                    "labeller": "human (case-study author), judged blind",
                    "issue_split": "the case study's scripts/split_gold.py (commit a75441c) "
                                   "classified the prose into blocking / secondary / "
                                   "anti_objection / praise",
                },
            }
            reference = {"issues": [{"summary": i["gist"], "severity": "blocking", "category": "other",
                                     "why_it_applies_here": i["text"], "what_breaks": i["text"], "fix": ""}
                                    for i in gold_issues if i["label"] == "blocking"]}
            tests = {"review_issues.py": GRADERS / "review_issues.py",
                     "review_scorer.md": GRADERS / "review_scorer.md",
                     "review_scorer_schema.json": GRADERS / "review_scorer_schema.json"}
            schema = (RL / t["output_schema"]).read_text()
            write(t, f"{system}\n\n{user}\n\n{SCHEMA_NOTE}\n", {"system.md": system, "user.md": user}, inputs,
                  schema, gold, reference, tests)


def build_funding(d: dict, write) -> None:
    prompt = PROMPTS / "funding_decision.md"
    schema = json.loads((HERE / "schemas" / "compare.json").read_text())
    both = json.dumps({"type": "object", "properties": {o: schema for o in ORDERINGS}, "required": list(ORDERINGS),
                       "additionalProperties": False}, indent=2) + "\n"
    for sid in sorted(d["items"], key=order):
        it = d["items"][sid]
        base = it.get("flip_of", sid)
        g = d["gold"].get(sid, {})
        if not is_filled(g):
            continue
        t, system, template = base_task(
            f"rd-funding-{sid}", base, "pm", "research_funding", "compare", it["firm"],
            [f"{SRC}/items/{sid}.json", f"{SRC}/grader_only/gold/{sid}.json"],
            prompt,
            {
                "output_schema": "families/research_design/schemas/compare.json",
                "orderings": list(ORDERINGS),
                "grader": {"type": "pairwise_pick", "module": "families/research_design/graders/pairwise_pick.py"},
                "meta": {"seed": base, "context_flip": sid != base, "seed_style": d["seeds"][base]["style"]},
            },
        )
        inputs = {"context": it["context"], "seed": it["seed"], "plan_A": it["plan_A"], "plan_B": it["plan_B"]}
        users = {o: harbor.render(template, context=it["context"], seed=it["seed"], plan_A=it[a], plan_B=it[b])
                 for o, (a, b) in ORDERINGS.items()}
        instruction = (f"{system}\n\n" + "\n\n".join(f"## Ordering {o}\n\n{u}" for o, u in users.items())
                       + f"\n\n{COMPARE_NOTE}\n")
        gold = {k: g[k] for k in ("preference", "preference_strength", "decisive_tenets", "preference_rationale",
                                  "why_loser_was_defensible", "goal_type", "error_asymmetry")}
        gold["provenance"] = {"labeller": "human (case-study author), judged blind"}
        reference = {o: {"winner": g["preference"] if o == "AB" else "AB".replace(g["preference"], ""),
                         "goal_type": g["goal_type"], "error_asymmetry": g["error_asymmetry"]} for o in ORDERINGS}
        write(t, instruction, {"system.md": system, **{f"user.{o}.md": u for o, u in users.items()}}, inputs,
              both, gold, reference, {"pairwise_pick.py": GRADERS / "pairwise_pick.py"})


def dumps(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build(family_id: str, split_names: list[str] | None = None, n: int | None = None,
          controls: int | None = None) -> None:
    """Build every graded task, all in split eval (`split_names` doesn't narrow it)."""
    if n is not None or controls is not None:
        raise SystemExit(f"{family_id} has one task per case: --n and --controls apply to generated families")
    fam = lib.family(family_id)
    d = load()
    for p in OUT.glob(f"{fam['task_prefix']}-*"):   # only this builder's tasks
        shutil.rmtree(p)
    built: dict = {}

    def write(t: dict, instruction: str, prompt: dict[str, str], inputs: dict, schema: str, gold: dict,
              reference: dict, tests: dict) -> None:
        """One task in Harbor layout. `prompt` holds the messages the API runner sends."""
        grader = {"mode": t["mode"], "params": t["grader"].get("params", {})}
        built[t["id"]] = harbor.write(
            OUT / t["id"], family=fam, builder="rl/families/research_design/build.py", instruction=instruction,
            metadata=t, description=f"{t['workflow']} {t['mode']}: {t['id']}", keywords=["research-design", t["mode"]],
            verifier="verify.py", gold=dumps(gold), judged=t["mode"] == "review",
            tests={**tests, "inputs.json": dumps(inputs), "grader.json": dumps(grader),
                   "verify.py": HERE / "verifier" / "verify.py"},
            data={"output_schema.json": schema},
            prompt={**{k: v + "\n" for k, v in prompt.items()}, "inputs.json": dumps(inputs)},
            solution={"solve.sh": REFERENCE / "solve.sh", "response.json": dumps(reference)})

    build_review(d, write)
    build_funding(d, write)
    splits.write_manifest(family_id, built)
    from collections import Counter
    print(f"{len(built)} tasks")
    for (role, wf, mode), k in sorted(Counter((t["role"], t["workflow"], t["mode"]) for t in built.values()).items()):
        print(f"  {role:<20}{wf:<18}{mode:<9}{k:>3}")


if __name__ == "__main__":
    build("research_design")
