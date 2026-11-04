"""Run a model on built tasks of any family through the API, graded by each task's own verifier.

For every (task, attempt): the model gets the task's instruction.md and the files under /app/data
(uploaded to a code-execution container when the family declares `tools: [code_execution]` in
family.yaml, or skills are on; inline otherwise). It returns each file the instruction asks for
as a <file path="/app/..."> block; the runner writes those into a local copy of the task layout
and runs the task's verifier on it (local.py), the same grader a Harbor run uses.

Records (records.py) are appended to rl/runs/api/<split>/<run_id>/records.jsonl as each attempt
finishes, with transcripts under traces/ (gitignored). Re-running the same --run-id resumes it:
attempts already recorded are skipped, and ones that hit an infrastructure error are retried. A
run's arguments are pinned in its folder; resuming with different ones is refused.

Live runs need --budget (model and judge cost, prices.yaml) and each family's approved instrument
(rl/harness/approve.py); heldout needs --allow-heldout. The judge is the family's pinned one
(family.yaml `judge`); --judge swaps in another model, and the verifier records the override.

    python rl/harness/run_api.py --split bench --model claude-opus-5-5 --budget 20 --k 3
    python rl/harness/run_api.py --split eval --family research_design --model claude-opus-5-5 --skills default --budget 5
    python rl/harness/run_api.py --split bench --model claude-opus-5-5 --dry-run       # print one request, no API call
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import client  # noqa: E402
import instrument  # noqa: E402
import local  # noqa: E402
import records  # noqa: E402
from lib import family  # noqa: E402
from skills import manage as skills  # noqa: E402

RUNNER = "rl/harness/run_api.py"
SYSTEM = """You are doing a task through an API rather than inside its container: you cannot write files \
yourself. The task's files under /app/data are {where}. Whatever the task says to write (files under \
/app/output or /app/solution), put in your final message, each file once, exactly as:

<file path="/app/output/name.ext">
the file's full contents
</file>

Everything else in your final message is ignored."""
FILE = re.compile(r'<file path="(/app/(?:output|solution)/[^"<>]+)">\n?(.*?)\n?</file>', re.S)
lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_files(task: pathlib.Path) -> dict[str, bytes]:
    """The files the agent sees under /app/data, as the container has them (unpacked)."""
    with local.layout(task) as app:
        return {str(p.relative_to(app / "data")): p.read_bytes() for p in sorted((app / "data").rglob("*")) if p.is_file()}


def answer_files(text: str) -> dict[str, str]:
    """{path under /app: contents} from the model's <file> blocks; the last block for a path wins."""
    return {path.removeprefix("/app/"): body for path, body in FILE.findall(text) if ".." not in path.split("/")}


def skills_condition(choice: str, model: str) -> dict:
    if choice == "off":
        return {"enabled": False, "profile": None}
    if not model.startswith("claude-"):
        raise SystemExit("--skills: only Anthropic models get skills")
    cfg = skills.config()
    profile = cfg["default_for_anthropic"] if choice == "default" else choice
    return {"enabled": True, "profile": profile, "source_commit": cfg["source"]["commit"],
            "entries": skills.resolve(profile)}


class Run:
    """One run's settings and shared state: the API client, budget, records file."""

    def __init__(self, args, api, cond: dict, out: pathlib.Path):
        self.args, self.api, self.cond, self.out = args, api, cond, out
        judges = {family(f).get("judge", {}).get("model") for f in args.family or []}
        self.budget = records.Budget(args.budget, args.model, *([args.judge] if args.judge else judges))

    def request(self, task: pathlib.Path, meta: dict) -> tuple[dict, list[str]]:
        """The request for this task, and the ids of files it uploaded."""
        a, files = self.args, data_files(task)
        code = "code_execution" in family(meta["family"]).get("tools", []) or self.cond["enabled"]
        text = (task / "instruction.md").read_text()
        uploaded = client.upload(self.api, files) if code and not a.dry_run else []
        if code:
            where = "attached to your code-execution sandbox (look for them there, not at /app/data)"
            content = [{"type": "text", "text": text}] + [client.file_block(f) for f in uploaded]
        else:
            where = "below"
            content = [{"type": "text", "text": text + "".join(
                f'\n\n<file path="/app/data/{n}">\n{b.decode(errors="replace")}\n</file>' for n, b in files.items())}]
        req = client.request(model=a.model, system=SYSTEM.format(where=where), content=content,
                             max_tokens=a.max_tokens, effort=a.effort, code_execution=code,
                             skills=self.cond.get("entries"))
        return req, uploaded

    def attempt(self, task: pathlib.Path, meta: dict, attempt: int) -> dict:
        a, started, t0 = self.args, now(), time.time()
        fields = {"started_at": started, "effort": a.effort, "max_tokens": a.max_tokens,
                  "skills": self.cond, "repo_commit": records.repo_commit()}
        try:
            req, uploaded = self.request(task, meta)
            try:
                msg, usage, _ = client.stream(req, t0 + a.timeout_s, self.api, f"{meta['id']} #{attempt}")
            finally:
                client.delete(self.api, uploaded)
        except client.DeadlineExceeded as e:
            return dict(fields, status="timeout", error=str(e), latency_s=round(time.time() - t0, 1))
        except Exception as e:  # recorded, never aborts the run
            return dict(fields, status="error", error=f"{type(e).__name__}: {e}", latency_s=round(time.time() - t0, 1))
        text = "\n".join(b.text for b in msg.content if b.type == "text")
        files = answer_files(text)
        trace = self.out / "traces" / f"{meta['id']}__{attempt}.json"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text(json.dumps({"request": {k: v for k, v in req.items() if k != "messages"},
                                     "user": req["messages"][0]["content"], "turn": msg.content, "files": files},
                                    indent=1, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else vars(o)))

        def write(app: pathlib.Path, tests: pathlib.Path) -> None:
            for rel, body in files.items():
                (app / rel).parent.mkdir(parents=True, exist_ok=True)
                (app / rel).write_text(body)

        g = local.grade(task, write, {"JUDGE_MODEL": a.judge} if a.judge else None)
        status = {"refusal": "refusal", "max_tokens": "truncated"}.get(msg.stop_reason, "ok" if files else "parse_error")
        if g.rewards is None:
            status, fields["error"] = "error", f"verifier failed: {g.error}"
        elif not g.rewards:
            status = "not_graded"
        return dict(fields, status=status, rewards=records.numbers(g.rewards), served_model=msg.model, usage=usage,
                    latency_s=round(time.time() - t0, 1), trace=str(trace.relative_to(RL.parent)),
                    **records.judge_fields(g.judge_usage))

    def __call__(self, job: tuple[pathlib.Path, dict, int]) -> None:
        task, meta, attempt = job
        if self.budget.exhausted:
            return
        print(f"  {now()} {meta['id']} #{attempt}: start", flush=True)
        r = records.make(**records.identity(task), attempt=attempt, model=self.args.model,
                         runner={"name": RUNNER, "run_id": self.args.run_id}, **self.attempt(task, meta, attempt))
        with lock:
            records.append(self.out / "records.jsonl", [r])
            self.budget.spend(r["cost_usd"], r.get("judge_cost_usd"))
        print(f"  {now()} {meta['id']} #{attempt}: {r['status']} {r['rewards'].get('reward')} "
              f"${(r['cost_usd'] or 0) + (r.get('judge_cost_usd') or 0):.3f}", flush=True)


def resume(path: pathlib.Path) -> set[tuple[str, int]]:
    """(task_id, attempt) already recorded; drops records of infrastructure errors so they are retried."""
    if not path.exists():
        return set()
    keep = [r for r in records.load([path]) if r["status"] != "error"]
    records.write(path, keep)
    return {(r["task_id"], r["attempt"]) for r in keep}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", required=True)
    ap.add_argument("--allow-heldout", action="store_true", help="run on the heldout split")
    ap.add_argument("--family", action="append", help="only these families (default: every family in the split)")
    ap.add_argument("--tasks", nargs="*", help="only these task ids")
    ap.add_argument("--model", required=True)
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-tokens", type=int, default=64000)
    ap.add_argument("--skills", default="off", help="off, default (config.yaml's default_for_anthropic) or a profile")
    ap.add_argument("--judge", help="judge model in place of each family's pinned one (recorded as an override)")
    ap.add_argument("--k", type=int, default=1, help="attempts per task")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout-s", type=int, default=1800, help="wall-clock ceiling per attempt, retries included")
    ap.add_argument("--budget", type=float, help="USD; stop starting attempts once model and judge cost reach it")
    ap.add_argument("--run-id", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.split == "heldout" and not a.allow_heldout:
        ap.error("heldout is for final evaluation only: pass --allow-heldout to run on it")
    if a.budget is None and not a.dry_run:
        ap.error("a live run needs --budget")
    tasks = [(d, m) for d, m in local.tasks(a.split, a.family) if not a.tasks or m["id"] in a.tasks]
    if not tasks:
        raise SystemExit(f"no built tasks match under tasks/{a.split}/")
    a.family = sorted({m["family"] for _, m in tasks})
    cond = skills_condition(a.skills, a.model) if not a.dry_run else {"enabled": a.skills != "off", "profile": a.skills}
    out = RL / "runs" / "api" / a.split / a.run_id
    run = Run(a, None if a.dry_run else client.connect(), cond, out)

    if a.dry_run:
        d, m = tasks[0]
        req, _ = run.request(d, m)
        print(f"{len(tasks)} tasks x {a.k}; first {m['id']}:")
        print(json.dumps(req, indent=1)[:4000])
        return
    for f in a.family:
        instrument.require_approved(f)
    records.pin_args(out, {k: v for k, v in vars(a).items() if k not in ("budget", "workers", "dry_run", "run_id")})
    done = resume(out / "records.jsonl")
    jobs = [(d, m, k) for d, m in tasks for k in range(a.k) if (m["id"], k) not in done]
    print(f"{a.model} · {a.split} · {len(jobs)} attempts ({len(done)} already recorded) -> {out.relative_to(RL.parent)}")
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(run, jobs))
    if run.budget.exhausted:
        print(f"budget ${a.budget} reached after ${run.budget.spent:.2f}; re-run with the same --run-id to continue")


if __name__ == "__main__":
    main()
