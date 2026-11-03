"""Run a model on kpi_nowcast tasks: one code-execution agent run per (task, rep), then grade it.

Each run uploads the task's files into a fresh code-execution container (no internet), lets the
model work until it ends its turn (following pause_turn continuations), parses the forecast JSON
and write-up from its final message, and grades both (grader.py).

Output, per variant, under rl/runs/kpi_nowcast/<variant>/ (layout read by the claude-api eval
report builder):
  results.jsonl              one row per scored (task, rep), written as each finishes
  traces/<task>_rep<k>.json  full transcript: system, user, every code call and result, final answer
  errors.jsonl               attempts that produced nothing scorable (API error, timeout, model mismatch)
  records.jsonl              both of the above as run records (rl/harness/records.py), one per attempt
A refusal is a graded outcome (row with status "refusal"), not an error. Re-running skips
(task, rep) pairs already in results.jsonl.

The family's instrument (this file, the grader and judge rubric, the prompts, the builder, the
verifier: `instrument` in family.yaml) is hashed; the runner refuses a live run until a human has
approved the current hash with rl/harness/approve.py (rl/instrument.py).

Usage:
    python rl/families/kpi_nowcast/run.py --variant baseline --model claude-opus-5-5 --tasks kn-produce-UAL-2018Q4
    python rl/families/kpi_nowcast/run.py --variant baseline --dry-run       # print one request, no API call
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import random
import sys
import threading
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib import RL, iter_tasks  # noqa: E402
import instrument  # noqa: E402
from families.kpi_nowcast import grader as G  # noqa: E402

sys.path.insert(0, str(RL / "harness"))
import records  # noqa: E402

RUNS = RL / "runs" / "kpi_nowcast"
TOOL = {"type": "code_execution_20260521", "name": "code_execution"}
MAX_CONTINUATIONS = 40
# Per-request HTTP timeouts. `read` is the longest gap allowed between streamed bytes; the server sends
# keepalive pings while code runs, so a gap this long means a stalled connection, not a slow task.
HTTP_TIMEOUT = {"connect": 30.0, "read": 300.0, "write": 120.0, "pool": 30.0}
lock = threading.Lock()


# ---------- one run ----------

def materialize(d: pathlib.Path, t: dict) -> dict[str, bytes]:
    """The attached files, uncompressed, checked against the hashes recorded at build time."""
    files = {}
    for name, sha in t["prompt"]["file_sha256"].items():
        p = d / "environment" / "data" / name
        data = p.read_bytes() if p.exists() else gzip.decompress((d / "environment" / "data" / f"{name}.gz").read_bytes())
        if hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError(f"{name}: sha256 mismatch with task.toml")
        files[name] = data
    return files


class DeadlineExceeded(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stream_with_backoff(client, req: dict, deadline: float, label: str = "", tries: int = 6):
    """One streamed request with jittered backoff on transient errors. Never starts an attempt or sleeps
    past the case's deadline, so retries can't run a case beyond its wall-clock ceiling."""
    import anthropic
    retries = 0
    while True:
        if time.time() >= deadline:
            raise DeadlineExceeded(f"case deadline reached before attempt {retries + 1}")
        try:
            with client.beta.messages.stream(**req) as s:
                return s.get_final_message(), retries
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            retries += 1
            print(f"    {now()} {label} attempt {retries} failed: {type(e).__name__}: {e}", flush=True)
            if retries >= tries:
                raise
            pause = min(60, 2 ** retries) * (0.5 + random.random())
            if time.time() + pause >= deadline:
                raise DeadlineExceeded(f"case deadline reached after {retries} failed attempts; last: {type(e).__name__}: {e}")
            time.sleep(pause)


def block_to_turns(b) -> list[dict]:
    t = b.type
    if t == "text":
        return [{"role": "assistant", "content": b.text}]
    if t == "server_tool_use":
        inp = getattr(b, "input", {}) or {}
        return [{"role": "tool_call", "name": getattr(b, "name", "code_execution"),
                 "content": inp.get("command") or inp.get("code") or json.dumps(inp, indent=2)}]
    if t.endswith("_tool_result"):
        c = b.content
        parts = []
        for k in ("stdout", "stderr", "content", "error_code", "file_type"):
            v = getattr(c, k, None)
            if v not in (None, "", []):
                parts.append(f"[{k}]\n{v if isinstance(v, str) else json.dumps(v, default=str)[:4000]}")
        return [{"role": "tool_result", "content": "\n".join(parts)[:20000]}]
    return []


def run_once(client, args, d: pathlib.Path, t: dict, rep: int) -> dict:
    started_at, deadline = now(), time.time() + (args.timeout_s or 10 ** 9)
    system = (d / "prompt" / "system.md").read_text().strip()
    user = (d / "prompt" / "user.md").read_text().strip()
    files = materialize(d, t)
    uploaded = [client.beta.files.upload(file=(name, data, "text/csv" if name.endswith(".csv") else "text/markdown"))
                for name, data in files.items()]
    content = [{"type": "text", "text": user}] + [{"type": "container_upload", "file_id": f.id} for f in uploaded]
    messages = [{"role": "user", "content": content}]
    req = {"model": args.model, "max_tokens": args.max_tokens, "system": system, "messages": messages,
           "betas": ["files-api-2025-04-14"],
           "extra_body": {"tools": [TOOL], "output_config": {"effort": args.effort}}}
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    turns = [{"role": "system", "content": system}, {"role": "user", "content": user + "\n\n[attached: " + ", ".join(files) + "]"}]
    t0, retries, conts, tool_calls = time.time(), 0, 0, 0
    while True:
        msg, r = stream_with_backoff(client, req, deadline, t["id"])
        retries += r
        if not msg.model.startswith(args.model):
            raise RuntimeError(f"served model {msg.model} != requested {args.model}")
        for k in usage:
            usage[k] += getattr(msg.usage, k, 0) or 0
        for b in msg.content:
            turns += block_to_turns(b)
            tool_calls += b.type == "server_tool_use"
        if msg.stop_reason != "pause_turn":
            break
        conts += 1
        if conts > MAX_CONTINUATIONS:
            raise RuntimeError("pause_turn continuation cap reached")
        messages.append({"role": "assistant", "content": msg.content})
        req["extra_body"]["container"] = msg.container.id
    for f in uploaded:
        try:
            client.beta.files.delete(f.id)
        except Exception:
            pass
    latency = round(time.time() - t0, 1)
    final_text = "\n".join(b.text for b in msg.content if b.type == "text")
    row = {"prompt_id": t["id"], "rep": rep, "started_at": started_at, "prompt": user, "tags": t.get("tags", []), "model": msg.model,
           "usage": usage, "latency_s": latency, "tool_calls": tool_calls, "continuations": conts,
           "retries": retries, "stop_reason": msg.stop_reason, "meta": t["meta"]}
    if msg.stop_reason == "refusal":
        row.update(status="refusal", grade={"refused": 1.0})
        return row, turns
    if msg.stop_reason == "max_tokens":
        row.update(status="truncated", grade={})
        return row, turns
    gold = json.loads((d / "tests" / "gold.json").read_text())
    fc, writeup, perr = G.parse_response(final_text)
    grade = G.grade_accuracy(fc, gold)
    row["parse_error"] = perr
    row["forecast"] = fc
    jreq = G.judge_request(args.judge, user, t["meta"]["as_of"], writeup, fc, gold)
    jmsg, jr = stream_with_backoff(client, jreq, deadline, t["id"] + " judge")
    verdicts = json.loads(next(b.text for b in jmsg.content if b.type == "text"))
    grade.update({k: v for k, v in G.grade_writeup(verdicts).items() if v is not None})
    row.update(status="ok", grade=grade, judge_model=jmsg.model,
               judge_usage={k: getattr(jmsg.usage, k, 0) or 0 for k in usage},
               explanation={f"w_{i}": f"{verdicts[i]['verdict']}: {verdicts[i]['reason']}" for i in G.ITEMS})
    return row, turns


def write_row(vdir: pathlib.Path, name: str, row: dict, args=None) -> None:
    """Append a results or errors row, and the same attempt as a run record; count its cost."""
    rec = None
    if args is not None:
        trace = vdir / "traces" / f"{row['prompt_id']}_rep{row['rep']}.json"
        rec = records.from_kpi(row, runner={"name": "rl/families/kpi_nowcast/run.py", "variant": vdir.name,
                                            "instrument_sha256": instrument.sha256("kpi_nowcast")},
                               trace=str(trace.relative_to(RL.parent)) if trace.exists() else None,
                               model=args.model, effort=args.effort, max_tokens=args.max_tokens,
                               repo_commit=records.repo_commit())
    with lock:
        with open(vdir / name, "a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        if rec is not None:
            records.append(vdir / "records.jsonl", [rec])
            args.budget_.spend(rec["cost_usd"], rec.get("judge_cost_usd"))


def run_case(client, args, vdir, d, t, rep):
    if args.budget_.exhausted:
        print(f"  {t['id']} rep{rep}: not started, budget ${args.budget} reached", flush=True)
        return
    started_at, t0 = now(), time.time()
    stamp = lambda: {"started_at": started_at, "ended_at": now(), "elapsed_s": round(time.time() - t0, 1)}  # noqa: E731
    print(f"  {started_at} {t['id']} rep{rep}: start", flush=True)
    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(run_once, client, args, d, t, rep)
    try:
        # small grace over the case deadline so the cooperative DeadlineExceeded path reports first
        row, turns = fut.result(timeout=(args.timeout_s + 60) if args.timeout_s else None)
    except (FutTimeout, DeadlineExceeded) as e:
        write_row(vdir, "errors.jsonl", {"prompt_id": t["id"], "rep": rep, "failure_class": "timeout",
                                         "error": f"wall-clock ceiling {args.timeout_s}s: {e}", **stamp()}, args)
        print(f"  {now()} {t['id']} rep{rep}: timeout", flush=True)
        pool.shutdown(wait=False)
        return
    except Exception as e:
        cls = "served_model_mismatch" if "served model" in str(e) else "harness_or_serving_error"
        write_row(vdir, "errors.jsonl", {"prompt_id": t["id"], "rep": rep, "failure_class": cls,
                                         "error": f"{type(e).__name__}: {e}", **stamp()}, args)
        print(f"  {now()} {t['id']} rep{rep}: {cls}: {e}", flush=True)
        return
    row["ended_at"] = now()
    (vdir / "traces").mkdir(parents=True, exist_ok=True)
    (vdir / "traces" / f"{t['id']}_rep{rep}.json").write_text(json.dumps(turns, indent=1, default=str))
    write_row(vdir, "results.jsonl", row, args)
    g = row.get("grade", {})
    print(f"  {t['id']} rep{rep}: {row['status']} err={g.get('abs_pct_error')} writeup={g.get('writeup_score')} "
          f"{row['latency_s']}s {row['usage']['input_tokens']}/{row['usage']['output_tokens']} tok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, help="'baseline' or v1, v2, ...")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--judge", default="claude-sonnet-5-5")
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout-s", type=int, default=1800)
    ap.add_argument("--max-tokens", type=int, default=64000)
    ap.add_argument("--budget", type=float, help="stop starting runs once model and judge cost reach this many USD")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tasks = [(d, t) for d, t in iter_tasks("kpi_nowcast") if not args.tasks or t["id"] in args.tasks]
    if not tasks:
        raise SystemExit("no tasks match")
    if args.dry_run:
        d, t = tasks[0]
        files = materialize(d, t)
        print(f"{len(tasks)} tasks; first {t['id']}; files {[(k, len(v)) for k, v in files.items()]}")
        print("system:", (d / "prompt" / "system.md").read_text()[:300])
        print("user:", (d / "prompt" / "user.md").read_text()[:600])
        return
    args.budget_ = records.Budget(args.budget, args.model, args.judge)
    instrument.require_approved("kpi_nowcast")
    vdir = RUNS / args.variant
    vdir.mkdir(parents=True, exist_ok=True)
    done = set()
    if (vdir / "results.jsonl").exists():
        done = {(r["prompt_id"], r["rep"]) for r in map(json.loads, (vdir / "results.jsonl").read_text().splitlines())}
    todo = [(d, t, k) for d, t in tasks for k in range(args.reps) if (t["id"], k) not in done]
    import anthropic
    import httpx
    client = anthropic.Anthropic(max_retries=0, timeout=httpx.Timeout(**HTTP_TIMEOUT))
    print(f"{args.model} effort={args.effort} judge={args.judge} · {len(todo)} runs ({len(done)} already done)")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(lambda x: run_case(client, args, vdir, *x), todo))
    print(f"wall clock {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
