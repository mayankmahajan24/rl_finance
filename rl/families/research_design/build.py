"""Build the research_design and research_funding tasks from rl/sources/research_design_case/.

Idempotent: wipes and regenerates the 6 worlds and the rd-* tasks, and rewrites
splits/manifests/research_design.json. Nothing else is touched.

What gets built (tasks in Harbor layout, families/_shared/harbor.py):

  worlds/<firm>/world.yaml        6 firm briefs from contexts.json
  tasks/eval/rd-review-*          28 review tasks (14 items x 2 plans)
  tasks/eval/rd-funding-*         14 pairwise funding decisions
  tasks/eval/rd-produce-*         10 produce tasks (seed + firm -> plan)

All are split `eval`: one eval set until whole worlds can be held out (FORMAT.md).

prompt/ holds the exact messages run.py sends (system.md, user.md or user.AB.md + user.BA.md,
inputs.json); their template is what the fingerprint covers. instruction.md is the same text for a
Harbor agent, plus where to write the answer; a compare task's Harbor copy shows the AB ordering
only. tests/ holds gold, the graders and verifier/verify.py.

The source data, and what was deliberately left out of it, is described in
rl/sources/research_design_case/README.md.

Usage:
    python rl/families/research_design/build.py
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import splits  # noqa: E402
from families._shared import harbor  # noqa: E402
from lib import RL, TASKS, WORLDS, fingerprint, load_prompt, write_yaml  # noqa: E402

DATA = RL / "sources" / "research_design_case"
GOLD = DATA / "grader_only" / "gold"
SEED_ONLY = DATA / "grader_only" / "seed_only_runs"
SRC = "sources/research_design_case"   # prefix for `sources` paths, relative to rl/
HERE = RL / "families" / "research_design"
PROMPTS = HERE / "prompts"
GRADERS = HERE / "graders"
OUT = TASKS / splits.UNSPLIT

SCHEMA_NOTE = ("---\nWrite your answer as one JSON object matching the schema in /app/data/output_schema.json, "
               "to /app/output/response.json.")
PLAN_NOTE = "---\nWrite your plan, in markdown, to /app/output/plan.md."
SCORER_ENV = ('\n[verifier.env]\n# scorer model for review tasks (matches issues to gold); compare tasks need no key\n'
              'ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY:-}"\nSCORER_MODEL = "${SCORER_MODEL:-claude-opus-5}"\n')

WORLD_NAMES = {
    "systematic": "Systematic trading firm",
    "small_lo": "Small concentrated long-only manager",
    "midsize_ls": "Mid-size fundamental long/short fund",
    "event_desk": "Event-driven pod on a multi-manager platform",
    "market_maker": "Electronic market maker internalizing retail flow",
    "ls_altdata": "Long/short fund with a new European transaction panel",
}

# Seed style decides which analyst role owns the research-design work.
ROLE_BY_STYLE = {"quant": "quant_researcher", "fundamental": "fundamental_analyst"}


def load() -> dict:
    seeds = {s["id"]: s for s in json.loads((DATA / "seeds.json").read_text())["seeds"]}
    ctx = json.loads((DATA / "contexts.json").read_text())
    items = {p.stem: json.loads(p.read_text()) for p in (DATA / "items").glob("*.json")}
    gold = {p.stem: json.loads(p.read_text()) for p in GOLD.glob("S*.json")}
    issues = json.loads((GOLD / "_issues.json").read_text())["items"]
    manifest = json.loads((DATA / "plan_manifest.json").read_text())
    return dict(seeds=seeds, ctx=ctx, items=items, gold=gold, issues=issues,
                manifest=manifest, verdicts=human_verdicts())


def human_verdicts() -> dict[str, str]:
    """The `your_verdict` column of seed_only_runs/findings-table.md — the human read of the
    seed-only plans."""
    out = {}
    for line in (SEED_ONLY / "findings-table.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0].isdigit():
            out[f"S{cells[0]}"] = cells[4]
    return out


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


def base_task(tid, role, workflow, mode, world, status, sources, prompt_file, extra=None):
    system, template = load_prompt(prompt_file)
    t = {
        "id": tid,
        "family": "research_design",
        "source": "research_design_case",
        "role": role,
        "workflow": workflow,
        "mode": mode,
        "world": world,
        "status": status,
        "split": splits.UNSPLIT,
        "prompt": {
            "template": str(prompt_file.relative_to(RL)),
            "fingerprint": fingerprint(system, template),
        },
        "sources": sources,
    }
    t.update(extra or {})
    return t, system, template


def build_worlds(d: dict) -> None:
    firms, assign, flips = d["ctx"]["firms"], d["ctx"]["assignment"], d["ctx"]["flips"]
    used: dict[str, list[str]] = {f: [] for f in firms}
    for sid, f in assign.items():
        used[f].append(sid)
    for sid, v in flips.items():
        if not sid.startswith("_"):
            used[v["firm"]].append(sid)
    for fid, brief in firms.items():
        write_yaml(WORLDS / fid / "world.yaml", {
            "id": fid,
            "name": WORLD_NAMES[fid],
            "kind": "fund",
            "status": "brief_only",
            "brief": brief,
            "source_items": sorted(used[fid], key=order),
            "to_become_a_full_world": [
                "mandate and risk limits",
                "current holdings with sizes",
                "investment theses per position",
                "past research memos and IC notes",
                "point-in-time data snapshot and tool access",
            ],
            "sources": [f"{SRC}/contexts.json"],
        })


def build_review(d: dict, built: list) -> None:
    prompt = PROMPTS / "review.md"
    for sid in sorted(d["items"], key=order):
        it = d["items"][sid]
        base = it.get("flip_of", sid)
        role = ROLE_BY_STYLE[d["seeds"][base]["style"]]
        g = d["gold"].get(sid, {})
        for slot in ("A", "B"):
            gold_issues = d["issues"].get(sid, {}).get(slot)
            graded = bool(gold_issues)
            tid = f"rd-review-{sid}-{slot}"
            t, system, template = base_task(
                tid, role, "research_design", "review", it["firm"],
                "graded" if graded else "ungraded",
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
            if not graded:
                t["status_note"] = ("gold empty: context-flip item, labels never filled "
                                    f"({SRC}/grader_only/gold/HOW-TO-FILL.md)")
            inputs = {"context": it["context"], "seed": it["seed"], "plan": it[f"plan_{slot}"]}
            user = template.format(**inputs)
            tests = {}
            if graded:
                tests["gold.json"] = dumps({
                    "issues": gold_issues,
                    "frame": {"goal_type": g.get("goal_type"),
                              "error_asymmetry": g.get("error_asymmetry")},
                    "critique_prose": g.get(f"critique_{slot}"),
                    "provenance": {
                        "labeller": "human (case-study author), judged blind",
                        "issue_split": "the case study's scripts/split_gold.py (commit a75441c) "
                                       "classified the prose into blocking / secondary / "
                                       "anti_objection / praise",
                    },
                })
                tests |= {"review_issues.py": GRADERS / "review_issues.py",
                          "review_scorer.md": GRADERS / "review_scorer.md",
                          "review_scorer_schema.json": GRADERS / "review_scorer_schema.json"}
            write_task(t, system, {"user.md": user}, inputs, user, SCHEMA_NOTE, tests, built)


def build_funding(d: dict, built: list) -> None:
    prompt = PROMPTS / "funding_decision.md"
    for sid in sorted(d["items"], key=order):
        it = d["items"][sid]
        base = it.get("flip_of", sid)
        g = d["gold"].get(sid, {})
        graded = is_filled(g)
        tid = f"rd-funding-{sid}"
        t, system, template = base_task(
            tid, "pm", "research_funding", "compare", it["firm"],
            "graded" if graded else "ungraded",
            [f"{SRC}/items/{sid}.json", f"{SRC}/grader_only/gold/{sid}.json"],
            prompt,
            {
                "output_schema": "families/research_design/schemas/compare.json",
                "orderings": ["AB", "BA"],
                "grader": {"type": "pairwise_pick", "module": "families/research_design/graders/pairwise_pick.py"},
                "meta": {"seed": base, "context_flip": sid != base,
                         "seed_style": d["seeds"][base]["style"]},
            },
        )
        if not graded:
            t["status_note"] = "gold empty: context-flip item, labels never filled"
        inputs = {"context": it["context"], "seed": it["seed"], "plan_A": it["plan_A"], "plan_B": it["plan_B"]}
        users = {f"user.{tag}.md": template.format(context=it["context"], seed=it["seed"], plan_A=it[a], plan_B=it[b])
                 for tag, (a, b) in {"AB": ("plan_A", "plan_B"), "BA": ("plan_B", "plan_A")}.items()}
        tests = {}
        if graded:
            tests["gold.json"] = dumps({
                k: g[k] for k in ("preference", "preference_strength", "decisive_tenets",
                                  "preference_rationale", "why_loser_was_defensible",
                                  "goal_type", "error_asymmetry")
            } | {"provenance": {"labeller": "human (case-study author), judged blind"}})
            tests["pairwise_pick.py"] = GRADERS / "pairwise_pick.py"
        write_task(t, system, users, inputs, users["user.AB.md"], SCHEMA_NOTE, tests, built)


def build_produce(d: dict, built: list) -> None:
    prompt = PROMPTS / "produce.md"

    firms, assign = d["ctx"]["firms"], d["ctx"]["assignment"]
    for sid in sorted(d["seeds"], key=order):
        s = d["seeds"][sid]
        role = ROLE_BY_STYLE[s["style"]]
        tid = f"rd-produce-{sid}"
        t, system, template = base_task(
            tid, role, "research_design", "produce", assign[sid], "needs_rubric",
            [f"{SRC}/seeds.json", f"{SRC}/grader_only/seed_only_runs/plans/{sid}.md",
             f"{SRC}/grader_only/seed_only_runs/critiques/{sid}.md",
             f"{SRC}/grader_only/seed_only_runs/findings-table.md"],
            prompt,
            {
                "output_schema": None,
                "grader": {"type": "rubric", "module": None,
                           "note": "no grader until an expert rubric exists; see grader/draft_rubric.json"},
                "related_tasks": [f"rd-funding-{sid}", f"rd-review-{sid}-A", f"rd-review-{sid}-B"],
                "meta": {"seed": sid, "seed_style": s["style"], "seed_bucket": s["bucket"]},
            },
        )
        inputs = {"context": firms[assign[sid]], "seed": s["text"]}
        user = template.format(**inputs)
        tests = {"draft_rubric.json": dumps({
            "status": "draft — one human-written item; needs a full expert rubric",
            "items": [{
                "id": "must_address_known_flaw",
                "kind": "must_hit",
                "text": s["discriminator"],
                "source": f"{SRC}/seeds.json `discriminator`, written by the case-study author "
                          "before any plan was generated",
            }],
            "rubric_inputs": {
                "human_verdict_on_claude_plan": d["verdicts"].get(sid),
                "two_competent_approaches_with_human_preference": f"rd-funding-{sid}",
                "blocking_issues_on_those_approaches": [f"rd-review-{sid}-A", f"rd-review-{sid}-B"],
            },
        })}
        tests["reference/claude_plan_no_context.md"] = SEED_ONLY / "plans" / f"{sid}.md"
        tests["reference/claude_critique_no_context.md"] = SEED_ONLY / "critiques" / f"{sid}.md"
        tests["reference/human_verdict.md"] = (
            f"# Human verdict on the Part 1 plan and critique ({sid})\n\n"
            f"{d['verdicts'].get(sid, '(missing)')}\n\n"
            f"Source: `your_verdict` column of `{SRC}/grader_only/seed_only_runs/findings-table.md`. "
            "The plan and critique "
            "in this folder were generated from the seed alone, with no firm context, so they "
            "are reference outputs for this task rather than runs of it.\n")
        write_task(t, system, {"user.md": user}, inputs, user, PLAN_NOTE, tests, built)


def dumps(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_task(t: dict, system: str, users: dict[str, str], inputs: dict, harbor_user: str, note: str,
               tests: dict, built: list) -> None:
    """One task in Harbor layout. `users` are the user messages run.py sends; `harbor_user` is the one
    a Harbor agent gets, followed by `note` on where to write its answer."""
    graded = "gold.json" in tests
    tests = dict(tests, **{"inputs.json": dumps(inputs),
                           "grader.json": dumps({"mode": t["mode"] if graded else None,
                                                 "params": t["grader"].get("params", {}),
                                                 "ordering": "AB" if t.get("orderings") else None,
                                                 "status": t["status"]}),
                           "verify.py": HERE / "verifier" / "verify.py"})
    data = {"output_schema.json": (RL / t["output_schema"]).read_text()} if t.get("output_schema") else {}
    harbor.write(OUT / t["id"], instruction=f"{system}\n\n{harbor_user}\n\n{note}\n", metadata=t,
                 description=f"{t['workflow']} {t['mode']}: {t['id']}", keywords=["research-design", t["mode"]],
                 verifier="verify.py", tests=tests, verifier_env=SCORER_ENV if t["mode"] == "review" else "",
                 data=data, prompt={"system.md": system + "\n", **{k: v + "\n" for k, v in users.items()},
                                    "inputs.json": dumps(inputs)},
                 pip=" anthropic" if t["mode"] == "review" else "")
    gold = tests.get("gold.json") or tests.get("draft_rubric.json")
    built.append(dict(t, gold_fingerprint=fingerprint(gold) if gold else None))


def leak_check(built: list) -> list[str]:
    """No gold text may appear in anything the model sees."""
    problems = []
    for t in built:
        d = OUT / t["id"]
        visible = "\n".join(p.read_text() for p in [d / "instruction.md", *(d / "prompt").iterdir(),
                                                      *(d / "environment" / "data").iterdir()])
        needles = []
        for f in (d / "tests" / "gold.json", d / "tests" / "draft_rubric.json"):
            if not f.exists():
                continue
            g = json.loads(f.read_text())
            needles += [i["text"] for i in g.get("issues", [])]
            needles += [g.get(k) or "" for k in ("preference_rationale", "why_loser_was_defensible",
                                                 "critique_prose")]
            needles += [i["text"] for i in g.get("items", [])]
        for n in needles:
            frag = re.sub(r"\s+", " ", n).strip()[:80]
            if len(frag) >= 40 and frag in re.sub(r"\s+", " ", visible):
                problems.append(f"{t['id']}: gold text visible in prompt: {frag!r}")
    return problems


def main() -> None:
    d = load()
    if WORLDS.exists():
        shutil.rmtree(WORLDS)
    for p in OUT.glob("rd-*"):   # only this builder's tasks
        shutil.rmtree(p)
    build_worlds(d)
    built: list = []
    build_review(d, built)
    build_funding(d, built)
    build_produce(d, built)

    problems = leak_check(built)
    if problems:
        raise SystemExit("LEAK CHECK FAILED\n" + "\n".join(problems))

    splits.write_manifest("research_design", {
        t["id"]: {"split": t["split"], **{k: t[k] for k in ("role", "workflow", "mode", "world", "status")},
                  "fingerprint": t["prompt"]["fingerprint"], "gold_fingerprint": t["gold_fingerprint"]}
        for t in built})
    from collections import Counter
    print(f"{len(built)} tasks, {len(d['ctx']['firms'])} worlds, leak check passed")
    for (role, wf, mode, st), n in sorted(Counter(
            (t["role"], t["workflow"], t["mode"], t["status"]) for t in built).items()):
        print(f"  {role:<20}{wf:<18}{mode:<9}{st:<14}{n:>3}")


if __name__ == "__main__":
    main()
