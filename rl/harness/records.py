"""Run records: one row per (task, attempt) for every run, API or Harbor, in one schema.

The schema is run_record.schema.json (versioned by `schema`). A record ties a result to the exact
instrument it was measured with: the task's content_sha256 and prompt fingerprint, the runner and its
version, model and settings, the skills condition and the judge. report.py refuses to aggregate
records whose instruments differ.

Runners write records as they go (`append`). Older result files are converted by the importers:

    python rl/harness/records.py import                        # every known run file under rl/runs/
    python rl/harness/records.py import-harbor <jobs_dir> --out rl/runs/harbor/<tag>/records.jsonl
    python rl/harness/records.py validate rl/runs/**/records.jsonl

Records live beside the files they describe, as records.jsonl (or <name>.records.jsonl).
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
import tomllib

import yaml

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
import splits  # noqa: E402

SCHEMA_FILE = pathlib.Path(__file__).with_name("run_record.schema.json")
SCHEMA = json.loads(SCHEMA_FILE.read_text())
VERSION = SCHEMA["properties"]["schema"]["const"]
STATUSES = SCHEMA["properties"]["status"]["enum"]
PRICES = yaml.safe_load(pathlib.Path(__file__).with_name("prices.yaml").read_text())["models"]
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def instrument(family: str, task_id: str) -> dict:
    """The task's identity from its family's committed manifest: split, mode, content_sha256, fingerprint."""
    e = splits.manifest(family).get(task_id) or {}
    return {"split": e.get("split"), "mode": e.get("mode"), "content_sha256": e.get("content_sha256"),
            "fingerprint": e.get("fingerprint")}


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
    """A record, with the task's identity filled from the manifest unless given, validated."""
    r = {"schema": VERSION, "task_id": task_id, "family": family, "attempt": attempt,
         **{k: v for k, v in instrument(family, task_id).items() if k not in fields},
         "runner": runner, "model": model, "status": status, "rewards": rewards or {}, **fields}
    if "cost_usd" not in r:
        r["cost_usd"] = cost(r.get("served_model") or model, r.get("usage"))
    problems = validate(r)
    if problems:
        raise ValueError(f"{task_id}: invalid run record: {'; '.join(problems)}")
    return r


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


# ---------- converters: one per native run format, shared by the runners and the importers ----------

def from_research_design(rec: dict, *, runner: dict, attempt: int = 0, **fields) -> dict:
    """A research_design run.py or replay.py record."""
    calls = rec.get("calls") or {}
    errors = [c.get("error", "") for c in calls.values() if c.get("status") == "error"]
    status = ("ok" if rec.get("status", "ok") == "ok" else
              "refusal" if any(e.startswith("RuntimeError: refused") for e in errors) else
              "truncated" if any("truncated" in e for e in errors) else "error")
    if status == "ok" and rec.get("reward") is None:
        status = "not_graded"
    usage = {k: sum((c.get("usage") or {}).get(src, 0) for c in calls.values())
             for k, src in (("input_tokens", "in"), ("output_tokens", "out"))} if calls else None
    fp = rec.get("prompt_fingerprint")
    return make(task_id=rec["task"], family="research_design", attempt=attempt, runner=runner, status=status,
                model=rec["model"], rewards={"reward": rec["reward"]} if rec.get("reward") is not None else {},
                **({"fingerprint": fp} if fp else {}),
                **({"skills": rec["skills"]} if "skills" in rec else {}),
                **({"judge_model": rec["scorer"]["model"]} if isinstance(rec.get("scorer"), dict) else {}),
                **({"usage": usage} if usage else {}),
                **({"error": "; ".join(errors)} if errors else {}), **fields)


REPLAY = {"name": "rl/families/research_design/replay.py", "version": "case-study saved runs"}


def from_replay(rec: dict) -> dict:
    """A replay.py record: a case-study run re-graded. replay.py checks every fingerprint against the
    case-study runs, so the record keeps the task's; the task bundles did not exist then, so no
    content_sha256. The case-study runs were all skills-off."""
    return from_research_design(rec, runner=REPLAY, content_sha256=None, skills={"enabled": False, "profile": None},
                                note="case-study run re-graded by replay.py")


def write(path: pathlib.Path, recs: list[dict]) -> None:
    """Replace `path` with these records (deterministic: sorted keys, no timestamps added)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True, default=str) + "\n" for r in recs))


def from_kpi(row: dict, *, runner: dict, trace: str | None = None, **fields) -> dict:
    """A kpi_nowcast run.py results.jsonl or errors.jsonl row."""
    if "failure_class" in row:
        status = "timeout" if row["failure_class"] == "timeout" else "error"
        return make(task_id=row["prompt_id"], family="kpi_nowcast", attempt=row["rep"], runner=runner,
                    status=status, error=f"{row['failure_class']}: {row.get('error', '')}",
                    **{k: row[k] for k in ("started_at",) if k in row},
                    **({"latency_s": row["elapsed_s"]} if "elapsed_s" in row else {}), **fields)
    status = {"ok": "ok", "refusal": "refusal", "truncated": "truncated"}.get(row.get("status"), "error")
    if status == "ok" and row.get("parse_error"):
        status = "parse_error"
    usage = {k: (row.get("usage") or {}).get(k, 0) for k in USAGE_KEYS}
    judge_cost = cost(row.get("judge_model"), row.get("judge_usage"))
    return make(task_id=row["prompt_id"], family="kpi_nowcast", attempt=row["rep"], runner=runner, status=status,
                model=fields.pop("model", row.get("model")), served_model=row.get("model"),
                rewards=numbers(row.get("grade")) if status != "refusal" else {},
                judge_model=row.get("judge_model"), usage=usage, latency_s=row.get("latency_s"),
                **({"judge_cost_usd": judge_cost} if judge_cost is not None else {}),
                **({"started_at": row["started_at"]} if "started_at" in row else {}),
                **({"error": row["parse_error"]} if row.get("parse_error") else {}),
                **({"trace": trace} if trace else {}), **fields)


def from_solutions(row: dict, *, runner: dict) -> dict:
    """A runs/solutions/<split>.csv row (reference or naive solver, run locally)."""
    rewards = numbers({k: float(v) for k, v in row.items()
                       if k not in ("task", "solver", "family", "judge", "note", "no_foresight", "fastest_correct")
                       and v not in ("", None)})
    return make(task_id=row["task"], family=row["family"], attempt=0, runner=dict(runner, agent=row["solver"]),
                status="ok" if not row.get("note") else "error", rewards=rewards,
                **({"judge_model": row["judge"]} if row.get("judge") else {}))


def from_harbor_trial(trial: pathlib.Path) -> dict:
    """One Harbor trial directory (result.json, verifier/reward.txt or reward.json)."""
    res = json.loads((trial / "result.json").read_text()) if (trial / "result.json").exists() else {}
    cfg = res.get("config") or {}
    agent = cfg.get("agent") or {}
    task_dir = pathlib.Path((cfg.get("task") or {}).get("path") or "")
    meta = (tomllib.loads((task_dir / "task.toml").read_text()).get("metadata", {})
            if (task_dir / "task.toml").exists() else {})
    task_id = meta.get("id") or res.get("task_name") or trial.name.split("__")[0]
    rewards = numbers((res.get("verifier_result") or {}).get("rewards"))
    v = trial / "verifier"
    if not rewards and (v / "reward.json").exists():
        rewards = numbers(json.loads((v / "reward.json").read_text()))
    elif not rewards and (v / "reward.txt").exists():
        rewards = {"reward": float((v / "reward.txt").read_text())}
    exc = res.get("exception_info")
    status = "ok" if not exc else ("timeout" if "Timeout" in str(exc.get("exception_type", "")) else "error")
    info = res.get("agent_info") or {}
    ar = res.get("agent_result") or {}
    usage = {k: x for k, x in {"input_tokens": ar.get("n_input_tokens"), "output_tokens": ar.get("n_output_tokens"),
                               "cache_read_input_tokens": ar.get("n_cache_tokens")}.items() if x is not None}
    ident = {"content_sha256": None, "fingerprint": None}
    if meta:
        from families._shared import harbor
        ident = {"content_sha256": harbor.content_sha256(task_dir),
                 "fingerprint": meta.get("fingerprint") or (meta.get("prompt") or {}).get("fingerprint"),
                 "split": meta.get("split"), "mode": meta.get("mode")}
    model = (info.get("model_info") or {}).get("name") or agent.get("model_name")
    return make(task_id=task_id, family=meta.get("family") or "unknown", attempt=0,
                runner={"name": "harbor", "agent": info.get("name") or agent.get("name") or agent.get("import_path"),
                        "version": info.get("version")},
                status=status, rewards=rewards, model=model, trace=str(trial),
                **({"usage": usage} if usage else {}),
                **({"error": f"{exc.get('exception_type')}: {str(exc.get('exception_message', ''))[:500]}"} if exc else {}),
                **({"started_at": res["started_at"]} if res.get("started_at") else {}), **ident)


# ---------- importers for the run files already in the repo ----------

def import_all() -> list[pathlib.Path]:
    """Convert every run file under rl/runs/ into records beside it; returns the files written."""
    runs, written = RL / "runs", []

    def out(path: pathlib.Path, recs: list[dict]) -> None:
        write(path, recs)
        written.append(path)

    for f in sorted((runs / "research_design").glob("*/*.jsonl")):
        if f.name.endswith(".records.jsonl"):
            continue
        native = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        convert = (from_replay if f.parent.name == "baseline" else
                   lambda r: from_research_design(r, runner={"name": "rl/families/research_design/run.py"},
                                                  note="imported"))
        out(f.with_name(f.stem + ".records.jsonl"), [convert(r) for r in native])
    for vdir in sorted(p for p in (runs / "kpi_nowcast").iterdir() if (p / "results.jsonl").exists()):
        rows = [json.loads(line) for name in ("results.jsonl", "errors.jsonl") if (vdir / name).exists()
                for line in (vdir / name).read_text().splitlines() if line.strip()]
        # the pilot predates fingerprints, and its prompts have changed since: instrument unknown
        unknown = {"fingerprint": None, "content_sha256": None,
                   "note": f"imported from runs/kpi_nowcast/{vdir.name}; instrument not recorded"}
        recs = []
        for r in rows:
            tr = vdir / "traces" / f"{r['prompt_id']}_rep{r['rep']}.json"
            recs.append(from_kpi(r, runner={"name": "rl/families/kpi_nowcast/run.py", "variant": vdir.name},
                                 trace=str(tr.relative_to(RL.parent)) if tr.exists() else None, **unknown))
        out(vdir / "records.jsonl", recs)
    for f in sorted((runs / "solutions").glob("*.csv")):
        runner = {"name": "rl/harness/run_solutions.py"}
        out(f.with_suffix(".records.jsonl"), [from_solutions(r, runner=runner) for r in csv.DictReader(f.open())])
    return written


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import", help="convert the run files under rl/runs/")
    h = sub.add_parser("import-harbor", help="convert a Harbor jobs directory")
    h.add_argument("jobs", type=pathlib.Path)
    h.add_argument("--out", type=pathlib.Path, required=True)
    v = sub.add_parser("validate")
    v.add_argument("files", nargs="+", type=pathlib.Path)
    a = ap.parse_args(argv)
    if a.cmd == "import":
        for p in import_all():
            print(f"{p.relative_to(RL.parent)}: {len(p.read_text().splitlines())} records")
    elif a.cmd == "import-harbor":
        trials = sorted({p.parent for p in a.jobs.rglob("result.json") if (p.parent / "verifier").is_dir()})
        recs = [from_harbor_trial(t) for t in trials]
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
