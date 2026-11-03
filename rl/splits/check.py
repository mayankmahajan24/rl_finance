"""Verify that splits are disjoint and that every built task obeys them. Exits non-zero on any failure.

  1. every company of a source is in exactly one split
  2. seed ranges never overlap, and every built task's seed is in its split's range and not a
     held-out seed
  3. every built task sits in the folder of its split: train, bench or heldout (its companies all in
     that split), eval (a source with no split assignment yet) or retired (a listed retired case)
  4. held-out tasks record no seed; nothing grader-side sits where the agent can see it
  5. every built task matches its family's committed manifest (same split, fingerprints and
     content_sha256), its files match its checksums.sha256, and it carries a build record
  6. point in time: every built task sets an explicit network policy for the container, the agent
     phase (none) and the verifier phase, matching what [metadata.environment] records; a task of a
     dated family records an as_of, and a dated task's image pins its clock to it
  7. leaks: nothing the agent sees gives away gold, the benchmark's identity, a disguised company or
     the release canary (rl/leakcheck.py, configured per family under `leak_check` in family.yaml)

With --release (before handing tasks to anyone): every task was also built from one clean commit,
with no uncommitted changes to tracked files, and every family with bench or held-out tasks has its
current instrument approved (rl/instrument.py).

Usage:
    python rl/splits/check.py
    python rl/splits/check.py --release
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import tomllib

import yaml

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
import splits  # noqa: E402
import instrument  # noqa: E402
import leakcheck  # noqa: E402
from families._shared import harbor  # noqa: E402
from lib import fingerprint, iter_tasks  # noqa: E402
from sources.txn_panel import panel  # noqa: E402

SOURCES = {"txn_panel": panel}          # sources with a company split
GRADER_ONLY = ("ground_truth", "gold", "draft_rubric", "reference")


def case_key(m: dict) -> str | None:
    """The key a retired case is listed under (kpi_nowcast: series-period)."""
    if m["family"] == "kpi_nowcast":
        return f"{m['meta']['series']}-{m['meta']['target_period'].replace(' ', '')}"
    return None


def checksum_problems(d: pathlib.Path) -> list[str]:
    f = d / "checksums.sha256"
    if not f.exists():
        return [f"{d.name}: no checksums.sha256"]
    listed = dict(reversed(line.split("  ", 1)) for line in f.read_text().splitlines())
    present = {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p != f}
    out = [f"{d.name}: {n} not in checksums.sha256" for n in sorted(present - set(listed))]
    out += [f"{d.name}: {n} listed but missing" for n in sorted(set(listed) - present)]
    out += [f"{d.name}: {n} does not match its checksum" for n in sorted(present & set(listed))
            if hashlib.sha256((d / n).read_bytes()).hexdigest() != listed[n]]
    return out


def sandbox_problems(d: pathlib.Path, m: dict) -> list[str]:
    """Check 6: the task's network policy and clock are explicit and agree with its metadata."""
    tid, cfg = d.name, tomllib.loads((d / "task.toml").read_text())
    env = m.get("environment") or {}
    out = []
    if env.get("internet") is not False:
        out.append(f"{tid}: [metadata.environment] internet must be false")
    for phase in ("environment", "agent"):
        if cfg.get(phase, {}).get("network_mode") != "no-network":
            out.append(f"{tid}: [{phase}] network_mode is {cfg.get(phase, {}).get('network_mode')!r}, not 'no-network'")
    hosts = env.get("verifier_hosts")
    v = cfg.get("verifier", {})
    want = ("allowlist", sorted(hosts)) if hosts else ("no-network", [])
    if hosts is None:
        out.append(f"{tid}: [metadata.environment] records no verifier_hosts")
    elif (v.get("network_mode"), sorted(v.get("allowed_hosts", []))) != want:
        out.append(f"{tid}: [verifier] network policy {v.get('network_mode')!r} {v.get('allowed_hosts', [])} "
                   f"disagrees with [metadata.environment] verifier_hosts {hosts}")
    fam = RL / "families" / m.get("family", "") / "family.yaml"
    as_of = m.get("as_of")
    if as_of is None and fam.exists() and (yaml.safe_load(fam.read_text()) or {}).get("dated"):
        out.append(f"{tid}: {m['family']} is dated but the task records no as_of")
    if as_of is not None:
        docker = (d / "environment" / "Dockerfile").read_text()
        if f"TASK_AS_OF={as_of} " not in docker or f'FAKETIME="@{as_of} ' not in docker:
            out.append(f"{tid}: as_of {as_of} but its image does not pin the clock to it")
    return out


def check(release: bool = False) -> list[str]:
    problems: list[str] = []
    commits: set[str] = set()

    # 1. companies
    for source, mod in SOURCES.items():
        a = splits.assignment(source)["companies"]
        seen: dict[str, str] = {}
        for split, names in a.items():
            if split not in splits.SPLITS:
                problems.append(f"{source}: unknown split {split!r}")
            for n in names:
                if n in seen:
                    problems.append(f"{source}: {n} is in both {seen[n]} and {split}")
                seen[n] = split
        for n in set(mod.companies()) - set(seen):
            problems.append(f"{source}: {n} has no split")
        for n in set(seen) - set(mod.companies()):
            problems.append(f"{source}: {n} in splits but not in entities.yaml")

    # 2. seed ranges (configured order keeps them apart; built seeds must sit inside their range)
    cfg = yaml.safe_load((splits.HERE / "seeds.yaml").read_text())
    bounds = [cfg["train"]["seed_start"], cfg["train"]["control_start"], cfg["bench"]["seed_start"],
              cfg["bench"]["control_start"], 10**8]
    if bounds != sorted(bounds) or len(set(bounds)) != len(bounds):
        problems.append(f"seeds.yaml ranges are not in increasing order: {bounds}")
    if bounds[0] < cfg["retired_below"]:
        problems.append(f"train seeds start below retired_below ({cfg['retired_below']})")
    ranges = {"train": (bounds[0], bounds[2]), "bench": (bounds[2], 10**8), "heldout": (10**8, 10**9)}
    held = {s for f in splits.heldout_seeds().values() for v in f.values() for s in v}

    # 3-5. built tasks
    owner: dict[str, str] = {}
    manifests: dict[str, dict] = {}
    for d, m in iter_tasks():
        tid, folder = d.name, d.parent.name
        if m.get("id") != tid:
            problems.append(f"{tid}: metadata id is {m.get('id')!r}")
        if m.get("split") != folder:
            problems.append(f"{tid}: metadata split {m.get('split')} but built under tasks/{folder}")
        if tid in owner:
            problems.append(f"{tid}: built in both {owner[tid]} and {folder}")
        owner[tid] = folder
        if folder in splits.SPLITS:
            if m.get("source") not in SOURCES:
                problems.append(f"{tid}: source {m.get('source')} has no split assignment, so it can't be in {folder}")
            else:
                extra = set(m.get("companies") or ["(none recorded)"]) - set(splits.companies(m["source"], folder))
                if extra:
                    problems.append(f"{tid}: uses {sorted(extra)}, not in {folder}")
        elif folder == splits.UNSPLIT:
            if m.get("source") in SOURCES:
                problems.append(f"{tid}: source {m['source']} has a split assignment; eval is for sources without one")
        elif folder == splits.RETIRED:
            if case_key(m) not in splits.retired(m["source"], m["family"]):
                problems.append(f"{tid}: in retired/ but its case is not listed as retired")
        else:
            problems.append(f"{tid}: built under tasks/{folder}, which is not a split")
        retired = splits.retired(m["source"], m["family"]) if m.get("source") in SOURCES else {}
        if folder != splits.RETIRED and case_key(m) in retired:
            problems.append(f"{tid}: its case is retired but it is built under {folder}")

        seed = m.get("seed")
        if folder == "heldout" and seed is not None:
            problems.append(f"{tid}: held-out task records its seed")
        elif seed is not None and folder in ranges:
            lo, hi = ranges[folder]
            if not lo <= seed < hi:
                problems.append(f"{tid}: seed {seed} outside the {folder} range [{lo}, {hi})")
            if seed in held:
                problems.append(f"{tid}: seed {seed} is a held-out seed")
        for sub in ("environment", "prompt"):
            if any(p.name.startswith(GRADER_ONLY) for p in (d / sub).rglob("*")):
                problems.append(f"{tid}: grader-only file under {sub}/")

        problems += checksum_problems(d)
        problems += sandbox_problems(d, m)
        problems += leakcheck.task_problems(d, m)
        b = m.get("build")
        if not b:
            problems.append(f"{tid}: no [metadata.build] record")
        else:
            commits.add(b["repo_commit"])
            if release and b["repo_dirty"]:
                problems.append(f"{tid}: built with uncommitted changes to tracked files")

        man = manifests.setdefault(m["family"], splits.manifest(m["family"]))
        entry = man.get(tid)
        fp = m.get("fingerprint") or m.get("prompt", {}).get("fingerprint")
        gold = next((p for p in (d / "tests" / n for n in ("ground_truth.json", "gold.json", "draft_rubric.json"))
                     if p.exists()), None)
        if entry is None:
            problems.append(f"{tid}: not in splits/manifests/{m['family']}.json")
        elif (entry["split"], entry["fingerprint"], entry["gold_fingerprint"], entry.get("content_sha256")) != (
                folder, fp, fingerprint(gold.read_text()) if gold else None, harbor.content_sha256(d)):
            problems.append(f"{tid}: differs from splits/manifests/{m['family']}.json (rebuild, or commit the new manifest)")

    if release and len(commits) > 1:
        problems.append(f"tasks were built from {len(commits)} different commits; rebuild everything from one")
    if release:
        released = sorted({m["family"] for d, m in iter_tasks() if d.parent.name in ("bench", "heldout")})
        problems += [why for ok, why in map(instrument.status, released) if not ok]
    for fam, man in manifests.items():
        for tid, v in man.items():
            if v["split"] == "heldout" and "seed" in v:
                problems.append(f"{fam} manifest: held-out {tid} records its seed")
    return problems


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true", help="also require one clean commit for every task")
    problems = check(ap.parse_args(argv).release)
    status = splits.assignment("txn_panel").get("status")
    if problems:
        print("SPLIT CHECK FAILED\n  " + "\n  ".join(problems))
        raise SystemExit(1)
    print(f"split check passed (txn_panel assignment: {status})")


if __name__ == "__main__":
    main()
