"""Verify that splits are disjoint and that every built task obeys them. Exits non-zero on any failure.

  1. every company of a source is in exactly one split
  2. seed ranges never overlap across splits, and every built task's seed is in its split's range
  3. every built task's companies are all in its split
  4. kpi_nowcast tasks carry their company's split, or "retired" for retired cases
  5. no task id appears in two splits; nothing grader-side sits in a Harbor task's environment/

Usage:
    python rl/splits/check.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tomllib

import yaml

RL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RL))
import splits  # noqa: E402
from lib import iter_tasks  # noqa: E402
from sources.txn_panel import panel  # noqa: E402

SOURCES = {"txn_panel": panel}


def check() -> list[str]:
    problems: list[str] = []

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
    ranges = {"train": (bounds[0], bounds[2]), "bench": (bounds[2], 10**8),
              "heldout": (10**8, 10**9)}
    held = {s for f in splits.heldout_seeds().values() for v in f.values() for s in v}

    # 3 and 5. Harbor tasks
    owner: dict[str, str] = {}
    for toml in sorted((RL / "tasks").glob("*/*/task.toml")):
        d, split_dir = toml.parent, toml.parent.parent.name
        m = tomllib.loads(toml.read_text())["metadata"]
        tid = d.name
        if m.get("split") != split_dir:
            problems.append(f"{tid}: metadata split {m.get('split')} but built under tasks/{split_dir}")
        if tid in owner:
            problems.append(f"{tid}: built in both {owner[tid]} and {split_dir}")
        owner[tid] = split_dir
        if split_dir not in splits.SPLITS:
            problems.append(f"{tid}: built under tasks/{split_dir}, which is not a split")
            continue
        allowed = set(splits.companies(m["source"], split_dir))
        extra = set(m.get("companies", [])) - allowed
        if extra:
            problems.append(f"{tid}: uses {sorted(extra)}, not in {split_dir}")
        seed = m.get("seed")
        if split_dir == "heldout":
            if seed is not None:
                problems.append(f"{tid}: held-out task records its seed")
        elif seed is not None:
            lo, hi = ranges[split_dir]
            if not lo <= seed < hi:
                problems.append(f"{tid}: seed {seed} outside the {split_dir} range [{lo}, {hi})")
            if seed in held:
                problems.append(f"{tid}: seed {seed} is a held-out seed")
        if any("ground_truth" in p.name for p in (d / "environment").rglob("*")):
            problems.append(f"{tid}: ground truth inside environment/")

    # manifests agree with the secrets file (held-out seeds really are the drawn ones)
    hman = splits.SECRETS / "manifests" / "txn_panel_heldout.json"
    if hman.exists():
        for tid, v in json.loads(hman.read_text()).items():
            if v["seed"] not in held:
                problems.append(f"{tid}: held-out manifest seed not in secrets/heldout_seeds.yaml")

    # 4. kpi_nowcast (repo task format); retired cases carry split "retired"
    retired_kpi = splits.retired("txn_panel", "kpi_nowcast")
    for d, t in iter_tasks():
        if t.get("workflow") != "kpi_nowcast":
            continue
        want = splits.split_of("txn_panel", panel.company_of_series(t["meta"]["series"]))
        if f"{t['meta']['series']}-{t['meta']['target_period'].replace(' ', '')}" in retired_kpi:
            want = "retired"
        if t.get("split") != want:
            problems.append(f"{t['id']}: split {t.get('split')}, company split is {want}")
    return problems


def main() -> None:
    problems = check()
    status = splits.assignment("txn_panel").get("status")
    if problems:
        print("SPLIT CHECK FAILED\n  " + "\n  ".join(problems))
        raise SystemExit(1)
    print(f"split check passed (txn_panel assignment: {status})")


if __name__ == "__main__":
    main()
