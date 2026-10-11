"""Build the rl/ task tree from the case study (case_study/part1, part2, seeds.json).

Idempotent: regenerates the six case-study worlds and the research_design /
research_funding task trees, then rewrites rl/catalog.json from every task on
disk. Other workflows under roles/ (earnings_recap, fixed_income, …) are left
alone. Hand-written files (prompts, rubrics, graders, docs) are not touched.

What gets built:

  worlds/<firm>/world.yaml              6 firm briefs from case_study/part2/contexts.json
  roles/*/research_design/rd-review-*   28 review tasks (14 items x 2 plans)
  roles/pm/research_funding/rd-funding-* 14 pairwise funding decisions
  roles/*/research_design/rd-produce-*  10 produce tasks (seed + firm -> plan)

What is deliberately NOT copied:

  case_study/part2/gold/design-intent.json   construction intent, not gold (ISOLATION.md)
  case_study/part2/forks.json                generator-tier methodology briefs
  case_study/part1/scores/                   model-scored, not human; gold must be human

Usage:
    python rl/build_from_case_study.py
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    CASE,
    CASE_STUDY_WORKFLOWS,
    RL,
    ROLES,
    WORLDS,
    fingerprint,
    load_prompt,
    write_catalog,
    write_json,
    write_yaml,
)

P1, P2 = CASE / "part1", CASE / "part2"
PROMPTS = RL / "prompts" / "research_design"

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
    seeds = {s["id"]: s for s in json.loads((CASE / "seeds.json").read_text())["seeds"]}
    ctx = json.loads((P2 / "contexts.json").read_text())
    items = {p.stem: json.loads(p.read_text()) for p in (P2 / "items").glob("*.json")}
    gold = {p.stem: json.loads(p.read_text()) for p in (P2 / "gold").glob("S*.json")}
    issues = json.loads((P2 / "gold" / "_issues.json").read_text())["items"]
    manifest = json.loads((P2 / "plans" / "_manifest.json").read_text())
    return dict(seeds=seeds, ctx=ctx, items=items, gold=gold, issues=issues,
                manifest=manifest, verdicts=human_verdicts())


def human_verdicts() -> dict[str, str]:
    """The `your_verdict` column of case_study/part1/findings-table.md — the human Part 1 read."""
    out = {}
    for line in (P1 / "findings-table.md").read_text().splitlines():
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
        "role": role,
        "workflow": workflow,
        "mode": mode,
        "world": world,
        "status": status,
        "split": "eval",
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
            "case_study_items": sorted(used[fid], key=order),
            "to_become_a_full_world": [
                "mandate and risk limits",
                "current holdings with sizes",
                "investment theses per position",
                "past research memos and IC notes",
                "point-in-time data snapshot and tool access",
            ],
            "sources": ["case_study/part2/contexts.json"],
        })


def build_review(d: dict, catalog: list) -> None:
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
                [f"case_study/part2/items/{sid}.json", f"case_study/part2/gold/{sid}.json", "case_study/part2/gold/_issues.json"],
                prompt,
                {
                    "output_schema": "schemas/research_design_review.json",
                    "grader": {
                        "type": "review_issues",
                        "module": "graders/review_issues.py",
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
                                    "(case_study/part2/gold/HOW-TO-FILL.md)")
            out = ROLES / role / "research_design" / tid
            (out / "prompt").mkdir(parents=True, exist_ok=True)
            (out / "prompt" / "system.md").write_text(system + "\n")
            inputs = {"context": it["context"], "seed": it["seed"], "plan": it[f"plan_{slot}"]}
            write_json(out / "prompt" / "inputs.json", inputs)
            (out / "prompt" / "user.md").write_text(template.format(**inputs) + "\n")
            if graded:
                write_json(out / "grader" / "gold.json", {
                    "issues": gold_issues,
                    "frame": {"goal_type": g.get("goal_type"),
                              "error_asymmetry": g.get("error_asymmetry")},
                    "critique_prose": g.get(f"critique_{slot}"),
                    "provenance": {
                        "labeller": "human (case-study author), judged blind",
                        "issue_split": "case_study/scripts/split_gold.py classified the prose into "
                                       "blocking / secondary / anti_objection / praise",
                    },
                })
            write_yaml(out / "task.yaml", t)
            catalog.append(t)


def build_funding(d: dict, catalog: list) -> None:
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
            [f"case_study/part2/items/{sid}.json", f"case_study/part2/gold/{sid}.json"],
            prompt,
            {
                "output_schema": "schemas/research_funding_compare.json",
                "orderings": ["AB", "BA"],
                "grader": {"type": "pairwise_pick", "module": "graders/pairwise_pick.py"},
                "meta": {"seed": base, "context_flip": sid != base,
                         "seed_style": d["seeds"][base]["style"]},
            },
        )
        if not graded:
            t["status_note"] = "gold empty: context-flip item, labels never filled"
        out = ROLES / "pm" / "research_funding" / tid
        (out / "prompt").mkdir(parents=True, exist_ok=True)
        (out / "prompt" / "system.md").write_text(system + "\n")
        write_json(out / "prompt" / "inputs.json", {"context": it["context"], "seed": it["seed"],
                                                    "plan_A": it["plan_A"], "plan_B": it["plan_B"]})
        for tag, (a, b) in {"AB": ("plan_A", "plan_B"), "BA": ("plan_B", "plan_A")}.items():
            (out / "prompt" / f"user.{tag}.md").write_text(
                template.format(context=it["context"], seed=it["seed"],
                                plan_A=it[a], plan_B=it[b]) + "\n")
        if graded:
            write_json(out / "grader" / "gold.json", {
                k: g[k] for k in ("preference", "preference_strength", "decisive_tenets",
                                  "preference_rationale", "why_loser_was_defensible",
                                  "goal_type", "error_asymmetry")
            } | {"provenance": {"labeller": "human (case-study author), judged blind"}})
        write_yaml(out / "task.yaml", t)
        catalog.append(t)


def build_produce(d: dict, catalog: list) -> None:
    prompt = PROMPTS / "produce.md"
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", CASE / "scripts" / "generate.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    system_here, _ = load_prompt(prompt)
    if system_here != gen.PLAN_SYSTEM.strip():
        raise SystemExit("produce.md SYSTEM drifted from case_study/scripts/generate.py PLAN_SYSTEM")

    firms, assign = d["ctx"]["firms"], d["ctx"]["assignment"]
    for sid in sorted(d["seeds"], key=order):
        s = d["seeds"][sid]
        role = ROLE_BY_STYLE[s["style"]]
        tid = f"rd-produce-{sid}"
        t, system, template = base_task(
            tid, role, "research_design", "produce", assign[sid], "needs_rubric",
            ["case_study/seeds.json", f"case_study/part1/plans/{sid}.md", f"case_study/part1/critiques/{sid}.md",
             "case_study/part1/findings-table.md"],
            prompt,
            {
                "output_schema": None,
                "grader": {"type": "rubric", "module": None,
                           "note": "no grader until an expert rubric exists; see grader/draft_rubric.json"},
                "related_tasks": [f"rd-funding-{sid}", f"rd-review-{sid}-A", f"rd-review-{sid}-B"],
                "meta": {"seed": sid, "seed_style": s["style"], "seed_bucket": s["bucket"]},
            },
        )
        out = ROLES / role / "research_design" / tid
        (out / "prompt").mkdir(parents=True, exist_ok=True)
        (out / "prompt" / "system.md").write_text(system + "\n")
        inputs = {"context": firms[assign[sid]], "seed": s["text"]}
        write_json(out / "prompt" / "inputs.json", inputs)
        (out / "prompt" / "user.md").write_text(template.format(**inputs) + "\n")
        write_json(out / "grader" / "draft_rubric.json", {
            "status": "draft — one human-written item; needs a full expert rubric",
            "items": [{
                "id": "must_address_known_flaw",
                "kind": "must_hit",
                "text": s["discriminator"],
                "source": "case_study/seeds.json `discriminator`, written by the case-study author "
                          "before any plan was generated",
            }],
            "rubric_inputs": {
                "human_verdict_on_claude_plan": d["verdicts"].get(sid),
                "two_competent_approaches_with_human_preference": f"rd-funding-{sid}",
                "blocking_issues_on_those_approaches": [f"rd-review-{sid}-A", f"rd-review-{sid}-B"],
            },
        })
        ref = out / "grader" / "reference"
        ref.mkdir(parents=True, exist_ok=True)
        shutil.copy(P1 / "plans" / f"{sid}.md", ref / "claude_plan_no_context.md")
        shutil.copy(P1 / "critiques" / f"{sid}.md", ref / "claude_critique_no_context.md")
        (ref / "human_verdict.md").write_text(
            f"# Human verdict on the Part 1 plan and critique ({sid})\n\n"
            f"{d['verdicts'].get(sid, '(missing)')}\n\n"
            "Source: `your_verdict` column of `case_study/part1/findings-table.md`. The plan and critique "
            "in this folder were generated from the seed alone, with no firm context, so they "
            "are reference outputs for this task rather than runs of it.\n")
        write_yaml(out / "task.yaml", t)
        catalog.append(t)


def write_schemas() -> None:
    sys.path.insert(0, str(CASE / "scripts"))
    import run_eval as R  # noqa: E402
    import score_issues as S  # noqa: E402
    write_json(RL / "schemas" / "research_design_review.json", R.POINTWISE_SCHEMA)
    write_json(RL / "schemas" / "research_funding_compare.json", R.PAIRWISE_SCHEMA)
    write_json(RL / "graders" / "review_scorer_schema.json", S.SCHEMA)
    (RL / "graders" / "review_scorer.md").write_text(
        "# Review scorer prompt\n\nCopied from `case_study/scripts/score_issues.py` by the build. The "
        "scorer buckets each issue a model raised against the task's gold issues.\n\n"
        f"---\n\n## SYSTEM\n\n{S.SYSTEM}\n\n## USER\n\n{S.USER}\n")


def leak_check(catalog: list) -> list[str]:
    """No gold text may appear in anything the model sees."""
    problems = []
    for t in catalog:
        d = next(ROLES.glob(f"*/*/{t['id']}"))
        visible = "\n".join(p.read_text() for p in (d / "prompt").iterdir())
        gp = d / "grader"
        needles = []
        for f in gp.glob("*.json"):
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


def wipe_case_study_workflows() -> None:
    """Remove only the workflows this script owns. Instrumentation FORMAT
    mirrors (earnings_recap, fixed_income, …) stay on disk."""
    if not ROLES.exists():
        return
    for role_dir in ROLES.iterdir():
        if not role_dir.is_dir():
            continue
        for wf in CASE_STUDY_WORKFLOWS:
            target = role_dir / wf
            if target.exists():
                shutil.rmtree(target)


def main() -> None:
    d = load()
    wipe_case_study_workflows()
    write_schemas()
    build_worlds(d)
    catalog: list = []
    build_review(d, catalog)
    build_funding(d, catalog)
    build_produce(d, catalog)

    problems = leak_check(catalog)
    if problems:
        raise SystemExit("LEAK CHECK FAILED\n" + "\n".join(problems))

    full = write_catalog()
    from collections import Counter
    print(f"{len(catalog)} case-study tasks rebuilt, {len(full)} tasks in catalog, "
          f"{len(d['ctx']['firms'])} case-study worlds, leak check passed")
    for (role, wf, mode, st), n in sorted(Counter(
            (t["role"], t["workflow"], t["mode"], t["status"]) for t in full).items()):
        print(f"  {role:<20}{wf:<18}{mode:<9}{st:<14}{n:>3}")


if __name__ == "__main__":
    main()
