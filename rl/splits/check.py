"""Verify that splits are disjoint and that every built task obeys them. Exits non-zero on any failure.

  1. every company of a source with a company split (source.yaml `company_split`) is in exactly one
     split
  2. seed ranges never overlap, and every built task's seed is in its split's range and not a
     held-out seed
  3. every built task sits in the folder of its split: train, bench or heldout (its companies all in
     that split), eval (a source with no split assignment yet) or retired (its `case` listed as retired)
  4. held-out tasks record no seed; no grader-only file (harbor.GRADER_ONLY) sits where the agent can
     see it
  5. every built task matches its family's committed manifest (same split, fingerprints and
     content_sha256), its files match its checksums.sha256, and it carries a build record
  6. point in time: every built task sets an explicit network policy for the container, the agent
     phase (none) and the verifier phase, matching what [metadata.environment] records; a task of a
     dated family records an as_of, and a dated task's image pins its clock to it
  7. provenance: every family's gold inputs have well-formed provenance entries (rl/provenance.py),
     every task of such a family carries them (tests/provenance.json, [metadata.provenance]), and
     no task claims approved gold that is no longer approved
  8. leaks: nothing the agent sees gives away gold, the benchmark's identity, a disguised company or
     the release canary (rl/leakcheck.py, configured per family under `leak_check` in family.yaml)
  9. environment and clean room: every /app path the instruction names exists in the image or is read
     by the verifier; the reference solution imports only what the agent's image has, reads no
     grader-side file, and its params give nothing the instruction doesn't

With --release (before handing tasks to anyone), over every built task (export.py runs the same rules
over just the tasks it exports): they were all built from one commit, none with uncommitted changes
to tracked files, and for every task in an exportable split (anything but held-out and retired):
its family's current instrument is approved (rl/instrument.py), and its gold is approved, unchanged
since review, and recorded so in the task.

Usage:
    python rl/splits/check.py
    python rl/splits/check.py --release
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import tomllib

import yaml

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
import splits  # noqa: E402
import instrument  # noqa: E402
import lib  # noqa: E402
import provenance  # noqa: E402
import leakcheck  # noqa: E402
from families._shared import harbor  # noqa: E402
from lib import fingerprint, iter_tasks  # noqa: E402


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
    as_of = m.get("as_of")
    if as_of is None and lib.family(m["family"]).get("dated"):
        out.append(f"{tid}: {m['family']} is dated but the task records no as_of")
    if as_of is not None:
        docker = (d / "environment" / "Dockerfile").read_text()
        if f"TASK_AS_OF={as_of} " not in docker or f'FAKETIME="@{as_of} ' not in docker:
            out.append(f"{tid}: as_of {as_of} but its image does not pin the clock to it")
    return out


def provenance_problems(d: pathlib.Path, m: dict) -> list[str]:
    """Check 7 for one task: its gold's provenance is recorded, and it claims no approval it lost."""
    tid, current = d.name, provenance.for_family(m["family"])
    if not current:
        return []
    recorded = m.get("provenance")
    if recorded is None or not (d / "tests" / "provenance.json").exists():
        return [f"{tid}: no gold provenance recorded (rebuild)"]
    now = provenance.summary(current)
    if recorded["status"] == "approved" and now["status"] != "approved":
        return [f"{tid}: built as approved, but {', '.join(now['unapproved'])} no longer is (rebuild)"]
    return []


def gold_approval_problems(d: pathlib.Path, m: dict) -> list[str]:
    """--release, for one task: its gold is approved now, and was recorded so when it was built."""
    tid, current = d.name, provenance.for_family(m["family"])
    if not current:
        return []
    now = provenance.summary(current)
    if now["status"] != "approved":
        return [f"{tid}: gold not approved: {', '.join(now['unapproved'])} (rl/review/review.py)"]
    if m.get("provenance") != now:
        return [f"{tid}: gold approved since it was built (rebuild)"]
    return []


# import name -> pip name, for the packages the agent image installs under another name
PIP_NAMES = {"sklearn": "scikit-learn", "yaml": "PyYAML"}
# what a reference solution must not touch: the grader's files, and the seeds or generator behind them
GRADER_SIDE = re.compile("|".join([r"/tests\b", *map(re.escape, harbor.GRADER_ONLY),
                                   r"seeds?\.ya?ml", r"heldout_seeds", r"\bgenerate\b"]))


def environment_problems(d: pathlib.Path, m: dict) -> list[str]:
    """Check 9: what the instruction names is there, and the reference works from what the agent has."""
    tid, out = d.name, []
    instruction = (d / "instruction.md").read_text()
    data = {p.name.removesuffix(".gz") for p in (d / "environment" / "data").iterdir()}
    verifier = "".join(p.read_text() for p in (d / "tests").glob("*.py"))
    for kind, name in sorted(set(re.findall(r"/app/(data|output|solution)/([\w.-]+\.\w+)", instruction))):
        if kind == "data" and name not in data:
            out.append(f"{tid}: instruction names /app/data/{name}, which the image doesn't have")
        graded = m.get("status") not in ("ungraded", "needs_rubric")    # an ungraded task's verifier reads nothing yet
        if kind != "data" and graded and f"'{name}'" not in verifier and f'"{name}"' not in verifier:
            out.append(f"{tid}: instruction names /app/{kind}/{name}, which the verifier never reads")
    image = (d / "environment" / "Dockerfile").read_text().lower()
    for f in sorted((d / "solution").glob("*")):
        if not f.is_file():
            continue
        text = f.read_text(errors="replace")
        if hit := GRADER_SIDE.search(text):
            out.append(f"{tid}: solution/{f.name} refers to grader-side files ({hit.group(0)!r})")
        if f.suffix == ".py":
            mods = {x.split(".")[0] for x in re.findall(r"^\s*(?:import|from)\s+([\w.]+)", text, re.M)}
            local = {p.stem for p in (d / "solution").glob("*.py")}
            for mod in sorted(mods - set(sys.stdlib_module_names) - local):
                if f"{PIP_NAMES.get(mod, mod).lower()}==" not in image:
                    out.append(f"{tid}: solution/{f.name} imports {mod}, which the agent's image doesn't install")
        if f.name == "params.json":
            out += [f"{tid}: solution/params.json gives {k}={v!r}, which the instruction doesn't state"
                    for k, v in json.loads(text).items() if str(v) not in instruction]
    return out


def check() -> list[str]:
    problems: list[str] = provenance.problems()

    # 1. companies
    split_sources = splits.split_sources()
    for source in split_sources:
        a = splits.assignment(source)["companies"]
        seen: dict[str, str] = {}
        for split, names in a.items():
            if split not in splits.SPLITS:
                problems.append(f"{source}: unknown split {split!r}")
            for n in names:
                if n in seen:
                    problems.append(f"{source}: {n} is in both {seen[n]} and {split}")
                seen[n] = split
        entities = lib.entities(source)
        for n in set(entities) - set(seen):
            problems.append(f"{source}: {n} has no split")
        for n in set(seen) - set(entities):
            problems.append(f"{source}: {n} in splits but not in its entities file")

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
        has_split = m["source"] in split_sources
        retired = splits.retired(m["source"], m["family"]) if has_split else {}
        if folder in splits.SPLITS:
            if not has_split:
                problems.append(f"{tid}: source {m['source']} has no split assignment, so it can't be in {folder}")
            else:
                extra = set(m.get("companies") or ["(none recorded)"]) - set(splits.companies(m["source"], folder))
                if extra:
                    problems.append(f"{tid}: uses {sorted(extra)}, not in {folder}")
        elif folder == splits.UNSPLIT:
            if has_split:
                problems.append(f"{tid}: source {m['source']} has a split assignment; eval is for sources without one")
        elif folder == splits.RETIRED:
            if m["case"] not in retired:
                problems.append(f"{tid}: in retired/ but its case is not listed as retired")
        else:
            problems.append(f"{tid}: built under tasks/{folder}, which is not a split")
        if folder != splits.RETIRED and m["case"] in retired:
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
            if any(p.name in harbor.GRADER_ONLY for p in (d / sub).rglob("*")):
                problems.append(f"{tid}: grader-only file under {sub}/")

        problems += checksum_problems(d)
        problems += sandbox_problems(d, m)
        problems += provenance_problems(d, m)
        problems += leakcheck.task_problems(d, m)
        problems += environment_problems(d, m)
        if not m.get("build"):
            problems.append(f"{tid}: no [metadata.build] record")

        man = manifests.setdefault(m["family"], splits.manifest(m["family"]))
        entry = man.get(tid)
        gold = d / "tests" / lib.family(m["family"])["gold_file"]
        if entry is None:
            problems.append(f"{tid}: not in splits/manifests/{m['family']}.json")
        elif (entry["split"], entry["fingerprint"], entry["gold_fingerprint"], entry.get("content_sha256")) != (
                folder, m["fingerprint"], fingerprint(gold.read_text()) if gold.exists() else None,
                harbor.content_sha256(d)):
            problems.append(f"{tid}: differs from splits/manifests/{m['family']}.json (rebuild, or commit the new manifest)")

    for fam, man in manifests.items():
        for tid, v in man.items():
            if v["split"] == "heldout" and "seed" in v:
                problems.append(f"{fam} manifest: held-out {tid} records its seed")
    return problems


def release_problems(tasks: list[tuple[pathlib.Path, dict]]) -> list[str]:
    """The --release rules over the given tasks: one clean commit, and for every task in an exportable
    split, an approved instrument and approved gold."""
    builds = {d.name: m["build"] for d, m in tasks if m.get("build")}     # a missing record fails check()
    problems = [f"{tid}: built with uncommitted changes to tracked files" for tid, b in builds.items() if b["repo_dirty"]]
    commits = {b["repo_commit"] for b in builds.values()}
    if len(commits) > 1:
        problems.append(f"tasks were built from {len(commits)} different commits; rebuild everything from one")
    gated = [(d, m) for d, m in tasks if d.parent.name not in splits.NEVER]
    for d, m in gated:
        problems += gold_approval_problems(d, m)
    problems += [why for ok, why in map(instrument.status, sorted({m["family"] for _, m in gated})) if not ok]
    return problems


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true",
                    help="also require one clean commit, and approved instruments and gold (see above)")
    problems = check()
    if ap.parse_args(argv).release:
        problems += release_problems(list(iter_tasks()))
    if problems:
        print("SPLIT CHECK FAILED\n  " + "\n  ".join(problems))
        raise SystemExit(1)
    print("split check passed (" + ", ".join(f"{s} assignment: {splits.assignment(s).get('status')}"
                                             for s in splits.split_sources()) + ")")


if __name__ == "__main__":
    main()
