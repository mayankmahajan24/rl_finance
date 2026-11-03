"""Run a model on research_design and research_funding tasks and grade it.

Anthropic models get the financial-services skills profile from
rl/skills/config.yaml by default (`default_for_anthropic`). `--skills off` runs the
same tasks without them, and `--profile` picks another profile. The skills
condition is recorded on every record, so skills-on and skills-off runs are never
mixed in one result file.

Skills apply to output generation only: the review scorer always runs without
skills, so both conditions are graded by the same instrument.

Usage:
    python rl/families/research_design/run.py --model claude-opus-5-5                      # graded tasks, skills on
    python rl/families/research_design/run.py --model claude-opus-5-5 --skills off
    python rl/families/research_design/run.py --model claude-opus-5-5 --mode compare --tasks rd-funding-S1
    python rl/families/research_design/run.py --model claude-opus-5-5 --dry-run            # print one request, no API call
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib import RL, fingerprint, iter_tasks, write_json  # noqa: E402
from families.research_design.graders import pairwise_pick, review_issues  # noqa: E402
from skills import manage as skills  # noqa: E402

sys.path.insert(0, str(RL / "harness"))
import records  # noqa: E402

SKILL_PATH = re.compile(r"/skills/([a-z0-9-]+)")


def select(args) -> list[tuple[pathlib.Path, dict]]:
    out = []
    for d, t in iter_tasks("research_design"):   # other families have their own runners
        if args.tasks and t["id"] not in args.tasks:
            continue
        if not args.tasks and t["status"] not in args.status:
            continue
        if args.mode and t["mode"] != args.mode:
            continue
        if args.workflow and t["workflow"] != args.workflow:
            continue
        out.append((d, t))
    return out


def skills_condition(args) -> dict:
    cfg = skills.config()
    is_anthropic = args.model.startswith("claude-")
    if args.skills == "off" or not is_anthropic:
        return {"enabled": False, "profile": None,
                "reason": "disabled by --skills off" if is_anthropic else "non-Anthropic model"}
    profile = args.profile or cfg["default_for_anthropic"]
    entries = ([{"type": "custom", "skill_id": f"<{r}>", "version": "<pinned>"}
                for r in cfg["profiles"][profile]] if args.dry_run else skills.resolve(profile))
    return {"enabled": bool(entries), "profile": profile,
            "source_commit": cfg["source"]["commit"], "entries": entries,
            "request": cfg["request"]}


def build_request(args, system: str, user: str, schema: dict | None, cond: dict) -> dict:
    req = {"model": args.model, "max_tokens": args.max_tokens, "system": system,
           "messages": [{"role": "user", "content": user}]}
    extra = {}
    output_config = {}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    if args.effort:
        output_config["effort"] = args.effort
    if output_config:
        extra["output_config"] = output_config
    if cond["enabled"]:
        req["tools"] = [cond["request"]["tool"]]
        req["betas"] = cond["request"]["betas"]
        extra["container"] = {"skills": cond["entries"]}
    if extra:
        req["extra_body"] = extra
    return req


def call(client, req: dict, cond: dict) -> dict:
    """One task call, following pause_turn continuations in the same container."""
    req = json.loads(json.dumps(req))
    api = client.beta.messages if cond["enabled"] else client.messages
    if not cond["enabled"]:
        req.pop("betas", None)
    usage = {"in": 0, "out": 0}
    continuations = 0
    blocks = []
    while True:
        with api.stream(**req) as stream:
            msg = stream.get_final_message()
        usage["in"] += msg.usage.input_tokens
        usage["out"] += msg.usage.output_tokens
        blocks += msg.content
        if msg.stop_reason != "pause_turn" or not cond["enabled"]:
            break
        continuations += 1
        if continuations > cond["request"]["max_pause_turn_continuations"]:
            raise RuntimeError("pause_turn continuation cap reached")
        req["messages"].append({"role": "assistant", "content": msg.content})
        req["extra_body"]["container"] = {"id": msg.container.id, "skills": cond["entries"]}
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"refused: {getattr(msg, 'stop_details', None)}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("truncated: raise --max-tokens")

    texts = [b.text for b in msg.content if b.type == "text"]
    touched, n_exec = set(), 0
    for b in blocks:
        if b.type == "server_tool_use":
            n_exec += 1
            touched |= set(SKILL_PATH.findall(json.dumps(getattr(b, "input", {}))))
    return {"text": texts[-1] if texts else "", "stop_reason": msg.stop_reason, "usage": usage,
            "continuations": continuations, "code_exec_calls": n_exec,
            "skills_read": sorted(touched),
            "container_id": getattr(getattr(msg, "container", None), "id", None)}


def run_task(client, args, cond: dict, d: pathlib.Path, t: dict) -> dict:
    system = (d / "prompt" / "system.md").read_text().strip()
    schema = json.loads((RL / t["output_schema"]).read_text()) if t.get("output_schema") else None
    variants = ({o: (d / "prompt" / f"user.{o}.md").read_text().strip() for o in t["orderings"]}
                if t.get("orderings") else {"single": (d / "prompt" / "user.md").read_text().strip()})
    rec = {"task": t["id"], "mode": t["mode"], "model": args.model,
           "prompt_fingerprint": t["prompt"]["fingerprint"],
           "skills": {k: v for k, v in cond.items() if k != "request"},
           "calls": {}}
    parsed = {}
    for name, user in variants.items():
        try:
            out = call(client, build_request(args, system, user, schema, cond), cond)
            out["response"] = json.loads(out["text"]) if schema else out["text"]
            out["status"] = "ok"
            parsed[name] = out["response"]
        except Exception as e:  # record, never abort the sweep
            out = {"status": "error", "error": f"{type(e).__name__}: {e}"}
        if schema and out["status"] == "ok":
            out.pop("text")  # parsed into `response`
        rec["calls"][name] = out

    rec["status"] = "ok" if all(c["status"] == "ok" for c in rec["calls"].values()) else "error"
    if rec["status"] != "ok" or t["status"] != "graded":
        rec["reward"] = None
        return rec
    gold = json.loads((d / "tests" / "gold.json").read_text())
    if t["mode"] == "compare":
        rec.update(pairwise_pick.grade(gold, parsed))
    elif t["mode"] == "review":
        # The scorer is a grader, never output generation: no skills.
        inputs = json.loads((d / "prompt" / "inputs.json").read_text())
        scored = review_issues.run_scorer(client, args.scorer, gold, inputs, parsed["single"])
        rec["scorer"] = {"model": args.scorer, **scored}
        rec.update(review_issues.grade(gold, scored, **t["grader"].get("params", {})))
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--skills", choices=["default", "off"], default="default",
                    help="default = config profile for Anthropic models, none for others")
    ap.add_argument("--profile", help="skills profile from rl/skills/config.yaml")
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--mode", choices=["review", "compare", "produce"])
    ap.add_argument("--workflow")
    ap.add_argument("--status", nargs="*", default=["graded"])
    ap.add_argument("--max-tokens", type=int, default=32000)   # case-study setting
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--scorer", default="claude-opus-5")       # case-study scorer
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--budget", type=float, help="stop starting tasks once the model's cost reaches this many USD (the scorer reports no usage)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tasks = select(args)
    if not tasks:
        raise SystemExit("no tasks match")
    cond = skills_condition(args)
    label = f"skills-{cond['profile']}" if cond["enabled"] else "skills-off"

    if args.dry_run:
        d, t = tasks[0]
        schema = json.loads((RL / t["output_schema"]).read_text()) if t.get("output_schema") else None
        user_file = sorted((d / "prompt").glob("user*.md"))[0]
        req = build_request(args, "<system.md>", f"<{user_file.name}>", schema and {"...": "schema"}, cond)
        print(f"{len(tasks)} tasks, condition {label}, first task {t['id']}:")
        print(json.dumps(req, indent=2))
        return

    import anthropic
    client = anthropic.Anthropic()
    budget = records.Budget(args.budget, args.model, args.scorer)
    runner = {"name": "rl/families/research_design/run.py", "tag": args.tag}
    settings = {"effort": args.effort, "max_tokens": args.max_tokens, "repo_commit": records.repo_commit()}
    print(f"{args.model} · {label} · {len(tasks)} tasks")

    def one(dt):
        if budget.exhausted:
            return None
        r = run_task(client, args, cond, *dt)
        rec = records.from_research_design(r, runner=runner, **settings)
        budget.spend(rec["cost_usd"], records.cost(args.scorer, (r.get("scorer") or {}).get("usage")))
        return r, rec

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        done = [x for x in pool.map(one, tasks) if x]
    records_, run_records = [r for r, _ in done], [rec for _, rec in done]
    if len(done) < len(tasks):
        print(f"budget ${args.budget} reached after ${budget.spent:.2f}: {len(tasks) - len(done)} tasks not started")
    for r in records_:
        print(f"  {r['task']:<22} {r['status']:<6} reward={r.get('reward')}")

    out = RL / "runs" / "research_design" / args.tag / f"{args.model}__{label}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in records_))
    records.append(out.with_suffix(".records.jsonl"), run_records)
    graded = [r["reward"] for r in records_ if r.get("reward") is not None]
    write_json(out.with_suffix(".summary.json"), {
        "model": args.model, "skills": {k: v for k, v in cond.items() if k != "entries"},
        "n_tasks": len(records_), "n_errors": sum(r["status"] == "error" for r in records_),
        "mean_reward": sum(graded) / len(graded) if graded else None,
        "max_tokens": args.max_tokens, "effort": args.effort, "scorer": args.scorer,
        "config_fingerprint": fingerprint(json.dumps(cond.get("entries", []), sort_keys=True)),
    })
    print(f"-> {out.relative_to(RL.parent)}")


if __name__ == "__main__":
    main()
