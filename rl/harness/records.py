"""Run records: one row per (task, attempt) for every run, API or Harbor, in one schema.

The schema is run_record.schema.json (versioned by `schema`). A record ties a result to the exact
instrument it was measured with: the built task's content_sha256 (hashed from the task folder that
was run) and fingerprint, the family's instrument hash, the runner, model and settings, the skills
condition and the judge. report.py refuses to aggregate records whose instruments differ.

Runners write records as they go (`append`): rl/harness/run_api.py, run_solutions.py, and Harbor
jobs through `import-harbor` (calibrate.py runs it for its own jobs). Records carry rewards only:
no answers, gold, breakdowns or task metadata, so they are safe to commit.

    python rl/harness/records.py import-harbor <jobs_dir> --out rl/runs/harbor/<run_id>/records.jsonl
    python rl/harness/records.py validate rl/runs/**/records.jsonl
"""

from __future__ import annotations

import argparse
import functools
import json
import pathlib
import sys
from collections import defaultdict

import yaml

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
sys.path.insert(0, str(RL / "harness"))
import instrument  # noqa: E402
from client import USAGE_KEYS  # noqa: E402
from families._shared import harbor  # noqa: E402
from lib import task_meta  # noqa: E402

SCHEMA = json.loads(pathlib.Path(__file__).with_name("run_record.schema.json").read_text())
VERSION = SCHEMA["properties"]["schema"]["const"]
PRICES = yaml.safe_load(pathlib.Path(__file__).with_name("prices.yaml").read_text())["models"]
FAILED = {"parse_error", "refusal", "truncated", "timeout"}   # the model failed: scored 0
UNSCORED = {"error", "not_graded"}                            # infrastructure or no grader: never scored


def identity(task_dir: pathlib.Path) -> dict:
    """The task as it was run: id, family, split and mode from its metadata, content_sha256 hashed
    from the folder itself, and the fingerprint of what the model sees."""
    m = task_meta(task_dir)
    return {"task_id": m["id"], "family": m["family"], "split": m.get("split"), "mode": m.get("mode"),
            "content_sha256": harbor.content_sha256(task_dir), "fingerprint": m.get("fingerprint")}


@functools.cache
def instrument_sha256(family: str) -> str | None:
    """The family's instrument hash now (rl/instrument.py); None for a family not in the repo."""
    return instrument.sha256(family) if (RL / "families" / family / "family.yaml").exists() else None


def score(r: dict, metric: str = "reward") -> float | None:
    """A record's score on `metric`: the verifier's value; 0 for a failed attempt it gave none; None
    when the record isn't scored (infrastructure error, no grader) or an ok answer has no such metric."""
    if r["status"] in UNSCORED:
        return None
    v = r["rewards"].get(metric)
    return float(v) if v is not None else (0.0 if r["status"] in FAILED else None)


def repo_commit() -> str | None:
    import subprocess
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RL, capture_output=True, text=True).stdout.strip() or None


class Budget:
    """A USD ceiling for a run: `spend` adds a record's cost; `exhausted` once the total reaches it.
    Refuses a model with no price, since its spend can't be counted."""

    def __init__(self, usd: float | None, *models: str):
        missing = [m for m in models if m and m not in PRICES]
        if usd is not None and missing:
            raise SystemExit(f"--budget needs a price for {', '.join(missing)} in rl/harness/prices.yaml")
        self.usd, self.spent = usd, 0.0

    def spend(self, *usd: float | None) -> None:
        self.spent += sum(u or 0.0 for u in usd)

    @property
    def exhausted(self) -> bool:
        return self.usd is not None and self.spent >= self.usd


def cost(model: str | None, usage: dict | None) -> float | None:
    """USD from the pinned price table (prices.yaml); None when the model or usage is unknown."""
    p = PRICES.get(model or "")
    if not p or not usage:
        return None
    rate = {"input_tokens": p["input"], "output_tokens": p["output"],
            "cache_read_input_tokens": p["cache_read"], "cache_creation_input_tokens": p["cache_write"]}
    return round(sum((usage.get(k) or 0) * rate[k] for k in USAGE_KEYS) / 1e6, 6)


def make(*, task_id: str, family: str, attempt: int, runner: dict, status: str, rewards: dict | None = None,
         model: str | None = None, **fields) -> dict:
    """A validated record. Pass the task's identity (`identity(task_dir)`); what isn't known stays null."""
    r = {"schema": VERSION, "task_id": task_id, "family": family, "attempt": attempt, "split": None, "mode": None,
         "content_sha256": None, "fingerprint": None, "instrument_sha256": instrument_sha256(family),
         "runner": runner, "model": model, "status": status, "rewards": rewards or {}, **fields}
    if "cost_usd" not in r:
        r["cost_usd"] = cost(model or r.get("served_model"), r.get("usage"))
    problems = validate(r)
    if problems:
        raise ValueError(f"{task_id}: invalid run record: {'; '.join(problems)}")
    return r


def judge_fields(usage: dict[str, dict]) -> dict:
    """judge_model and judge_cost_usd from a verifier's judge_usage.json ({model: usage})."""
    if not usage:
        return {}
    costs = [cost(m, u) for m, u in usage.items()]
    return {"judge_model": ",".join(sorted(usage)),
            "judge_cost_usd": None if None in costs else round(sum(costs), 6)}


def validate(r: dict) -> list[str]:
    """Check a record against the schema's required fields, types and enums (no jsonschema dependency)."""
    out = [f"missing {k}" for k in SCHEMA["required"] if k not in r]
    out += [f"unknown field {k}" for k in r if k not in SCHEMA["properties"]]
    types = {"string": str, "integer": int, "number": (int, float), "object": dict, "boolean": bool, "array": list}
    for k, v in r.items():
        spec = SCHEMA["properties"].get(k, {})
        if "enum" in spec and v not in spec["enum"]:
            out.append(f"{k} {v!r} not in {spec['enum']}")
        allowed = spec.get("type")
        if allowed is None or v is None and "null" in (allowed if isinstance(allowed, list) else [allowed]):
            continue
        ts = tuple(types[t] for t in (allowed if isinstance(allowed, list) else [allowed]) if t != "null")
        if not isinstance(v, ts) or isinstance(v, bool) and bool not in ts:
            out.append(f"{k} has type {type(v).__name__}, not {allowed}")
    if r.get("schema") != VERSION:
        out.append(f"schema {r.get('schema')!r}, not {VERSION}")
    for name, v in (r.get("rewards") or {}).items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            out.append(f"reward {name} is not a number")
    return out


def append(path: pathlib.Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")


def load(paths) -> list[dict]:
    out = []
    for p in paths:
        out += [json.loads(line) for line in pathlib.Path(p).read_text().splitlines() if line.strip()]
    return out


def numbers(d: dict | None) -> dict:
    return {k: float(v) for k, v in (d or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def write(path: pathlib.Path, recs: list[dict]) -> None:
    """Replace `path` with these records (deterministic: sorted keys, no timestamps added)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True, default=str) + "\n" for r in recs))


def pin_args(run_dir: pathlib.Path, args: dict) -> None:
    """Record a run's arguments in its folder; refuse to resume it with different ones."""
    f = run_dir / "args.json"
    if f.exists() and json.loads(f.read_text()) != args:
        raise SystemExit(f"{run_dir} was started with {f.read_text().strip()}; resume it with the same arguments "
                         f"or use another --run-id")
    run_dir.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(args, indent=1) + "\n")


def from_harbor_trial(trial: pathlib.Path, attempt: int, run_id: str | None = None) -> dict:
    """One Harbor trial directory (result.json, verifier/reward.json or reward.txt, judge_usage.json)."""
    res = json.loads((trial / "result.json").read_text()) if (trial / "result.json").exists() else {}
    cfg = res.get("config") or {}
    agent = cfg.get("agent") or {}
    task_dir = pathlib.Path((cfg.get("task") or {}).get("path") or "")
    task_id = res.get("task_name") or trial.name.split("__")[0]
    ident = identity(task_dir) if (task_dir / "task.toml").exists() else {"task_id": task_id, "family": "unknown"}
    v = trial / "verifier"
    rewards = numbers((res.get("verifier_result") or {}).get("rewards"))
    if not rewards and (v / "reward.json").exists():
        rewards = numbers(json.loads((v / "reward.json").read_text()))
    elif not rewards and (v / "reward.txt").exists():
        rewards = {"reward": float((v / "reward.txt").read_text())}
    exc = res.get("exception_info")
    status = ("timeout" if exc and "Timeout" in str(exc.get("exception_type", "")) else "error" if exc else
              "ok" if rewards else "not_graded")
    info = res.get("agent_info") or {}
    ar = res.get("agent_result") or {}
    usage = {k: x for k, x in {"input_tokens": ar.get("n_input_tokens"), "output_tokens": ar.get("n_output_tokens"),
                               "cache_read_input_tokens": ar.get("n_cache_tokens")}.items() if x is not None}
    judge = json.loads((v / "judge_usage.json").read_text()) if (v / "judge_usage.json").exists() else {}
    model = (info.get("model_info") or {}).get("name") or agent.get("model_name")
    return make(**ident, attempt=attempt, status=status, rewards=rewards, model=model, trace=str(trial),
                runner={"name": "harbor", "agent": info.get("name") or agent.get("name") or agent.get("import_path"),
                        "version": info.get("version"), "run_id": run_id},
                **({"usage": usage} if usage else {}), **judge_fields(judge),
                **({"error": f"{exc.get('exception_type')}: {str(exc.get('exception_message', ''))[:500]}"} if exc else {}),
                **({"started_at": res["started_at"]} if res.get("started_at") else {}))


def import_harbor(jobs: pathlib.Path, run_id: str | None = None) -> list[dict]:
    """Every trial under a Harbor jobs folder; attempts are numbered per task and model in start order."""
    trials = sorted({p.parent for p in jobs.rglob("result.json") if (p.parent / "verifier").is_dir()})
    starts = {t: (json.loads((t / "result.json").read_text()).get("started_at") or "", str(t)) for t in trials}
    out, seen = [], defaultdict(int)
    for t in sorted(trials, key=starts.get):
        r = from_harbor_trial(t, 0, run_id)
        k = (r["task_id"], r["model"])
        r["attempt"], seen[k] = seen[k], seen[k] + 1
        out.append(r)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("import-harbor", help="convert a Harbor jobs directory")
    h.add_argument("jobs", type=pathlib.Path)
    h.add_argument("--out", type=pathlib.Path, required=True)
    v = sub.add_parser("validate")
    v.add_argument("files", nargs="+", type=pathlib.Path)
    a = ap.parse_args(argv)
    if a.cmd == "import-harbor":
        recs = import_harbor(a.jobs, a.out.parent.name)
        append(a.out, recs)
        print(f"{a.out}: {len(recs)} records from {a.jobs}")
    else:
        bad = [(f, i, p) for f in a.files for i, r in enumerate(load([f])) for p in validate(r)]
        for f, i, p in bad:
            print(f"{f}:{i + 1}: {p}")
        if bad:
            raise SystemExit(1)
        print(f"{len(a.files)} files valid")


if __name__ == "__main__":
    main()
