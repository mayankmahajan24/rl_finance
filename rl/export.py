"""Export a release: the versioned bundle a lab receives. Refuses anything that must not leave the repo.

    python rl/export.py --split bench --out dist/rl_finance-bench.tar.gz
    python rl/export.py --split eval --family research_design --out dist/rd/          # a folder instead
    python rl/export.py --split bench --preview --out /tmp/preview/                  # licence gate off, stamped

Before writing anything it refuses:
  - held-out and retired tasks, always
  - a failing `splits/check.py --release` (a dirty build, mixed commits, a task that differs from its
    manifest, a broken sandbox policy)
  - a task whose source's licence (`licence.status` in sources/<source>/source.yaml) doesn't clear
    the use (--use eval or training), or whose company split is still `proposed`
  - a release version with no entry in release/CHANGELOG.md
  - tasks not stamped with the commit's time (built without SOURCE_DATE_EPOCH), which would make the
    archive differ between two exports of the same commit

The bundle:

    rl_finance-<version>-<split>/
      release.json     version, use, commit, families and versions, sources and licences, and every
                       task's content_sha256 and fingerprints, so two releases diff task by task
      CHANGELOG.md     release/CHANGELOG.md
      DATASHEET.md     generated from metadata: sources, provenance and licence, what the agent sees
                       vs what graders see, splits, rewards, limitations, validation and calibration status
      cards/<family>.md   per family: what it measures, reward, an example instruction, baseline scores
      tasks/<task_id>/    the built tasks, unchanged (each verifies with its own checksums.sha256)

A .tar.gz output is reproducible: sorted entries, fixed mtimes, owner and modes, no gzip timestamp,
and its sha256 written to <out>.sha256. The same commit and seeds give a byte-identical archive.
Build for a release with the commit's time:

    SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python rl/build.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import pathlib
import re
import shutil
import sys
import tarfile
from collections import defaultdict
from datetime import datetime, timezone

import yaml

RL = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RL))
import splits  # noqa: E402
from lib import iter_tasks  # noqa: E402
from splits import check  # noqa: E402

RELEASE = RL / "release"
LICENCES = ("unknown", "internal_only", "licensed_for_eval", "licensed_for_training", "public")
CLEARS = {"eval": {"licensed_for_eval", "licensed_for_training", "public"},
          "training": {"licensed_for_training", "public"}}
NEVER = {"heldout", splits.RETIRED}
PREVIEW = "PREVIEW: the licence gate was off for this export. Not for distribution."


class Refused(SystemExit):
    pass


def source_yaml(source: str) -> dict:
    return yaml.safe_load((RL / "sources" / source / "source.yaml").read_text())


def family_yaml(family: str) -> dict:
    return yaml.safe_load((RL / "families" / family / "family.yaml").read_text())


def release_config() -> dict:
    return yaml.safe_load((RELEASE / "release.yaml").read_text())


def changelog_entry(version: str) -> str | None:
    text = (RELEASE / "CHANGELOG.md").read_text()
    m = re.search(rf"^## {re.escape(version)}\b.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0).strip() if m else None


def select(split: str, families: list[str] | None) -> list[tuple[pathlib.Path, dict]]:
    return [(d, m) for d, m in iter_tasks() if d.parent.name == split and (not families or m["family"] in families)]


def refusals(split: str, use: str, tasks, version: str, preview: bool, run_check=check.check) -> list[str]:
    """Every reason this export must not happen; empty when it may."""
    out = []
    if split in NEVER:
        return [f"{split} tasks are never exported"]
    if not tasks:
        return [f"no built tasks under tasks/{split}/ (build them first)"]
    out += [f"split check --release: {p}" for p in run_check(release=True)]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        out.append(f"release version {version!r} is not semver (release/release.yaml)")
    elif changelog_entry(version) is None:
        out.append(f"release/CHANGELOG.md has no '## {version}' entry")
    for source in sorted({m["source"] for _, m in tasks}):
        lic = (source_yaml(source).get("licence") or {}).get("status")
        if lic not in LICENCES:
            out.append(f"source {source}: licence.status {lic!r} is not one of {', '.join(LICENCES)}")
        elif lic not in CLEARS[use] and not preview:
            out.append(f"source {source}: licence.status {lic} does not clear {use} use "
                       f"(needs {' or '.join(sorted(CLEARS[use]))})")
        if source in check.SOURCES and splits.assignment(source).get("status") != "approved":
            out.append(f"source {source}: its company split is {splits.assignment(source).get('status')}, not approved")
    stamps = {m["build"]["built_at"] for _, m in tasks}
    commit_time = commit_timestamp(next(iter({m["build"]["repo_commit"] for _, m in tasks})))
    if stamps != {commit_time}:
        out.append(f"tasks are stamped {sorted(stamps)[:3]}, not the commit's time {commit_time}: rebuild with "
                   "SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python rl/build.py so the archive is reproducible")
    return out


def commit_timestamp(commit: str) -> str:
    import subprocess
    t = subprocess.run(["git", "show", "-s", "--format=%ct", commit], cwd=RL, capture_output=True, text=True).stdout
    if not t.strip():
        return f"(commit {commit} not found)"
    return datetime.fromtimestamp(int(t), timezone.utc).isoformat(timespec="seconds")


def baselines(family: str, split: str) -> list[str]:
    """Baseline lines for a card: solver means from runs/solutions/<split>.csv, model runs from runs/<family>/."""
    lines = []
    f = RL / "runs" / "solutions" / f"{split}.csv"
    if f.exists():
        by = defaultdict(list)
        for r in csv.DictReader(f.open()):
            if r["family"] == family:
                by[r["solver"]].append(float(r["reward"]))
        lines += [f"| {s} solution | {sum(v) / len(v):.3f} | {len(v)} tasks | `runs/solutions/{split}.csv` |"
                  for s, v in sorted(by.items())]
    f = RL / "runs" / family / "baseline" / "summary.json"
    if f.exists():
        for model, s in json.loads(f.read_text()).items():
            nums = ", ".join(f"{k} {v}" for k, v in s.items() if k != "n_records")
            lines.append(f"| {model} | {nums} | {s.get('n_records', '?')} records | `runs/{family}/baseline/` |")
    return lines


def card(family: str, tasks, split: str) -> str:
    fam = family_yaml(family)
    example = min(tasks, key=lambda t: t[0].name)
    rows = baselines(family, split)
    modes = ", ".join(sorted({m.get("mode", "?") for _, m in tasks}))
    return "\n".join([
        f"# {family} (version {fam['version']})", "",
        fam["description"] + ".", "",
        "| | |", "|---|---|",
        f"| Source | {fam['source']} |",
        f"| Role, workflow, mode | {fam['role']}; {fam['workflow']}; {modes} |",
        f"| Tasks in this release | {len(tasks)} ({split}) |",
        f"| Reward | {' '.join(str(fam['reward']).split())} |",
        f"| Verifier | `tests/` of each task (`{fam['verifier']}`) |", "",
        "## Baseline scores", "",
        *(["| Solver or model | Score | Over | Record |", "|---|---|---|---|", *rows] if rows
          else ["None recorded for this family yet."]), "",
        "Calibration against frontier models (pass@k, noise floor, keep/drop per task) is not in this "
        "release yet.", "",
        f"## Example instruction ({example[0].name})", "",
        "````markdown", (example[0] / "instruction.md").read_text().rstrip(), "````", ""])


def datasheet(manifest: dict, tasks) -> str:
    fams = manifest["families"]
    out = [f"# Datasheet: rl_finance {manifest['version']} ({manifest['split']}, {manifest['use']} use)", "",
           f"Built from commit `{manifest['commit']}` at {manifest['built_at']}; {len(tasks)} tasks in "
           f"{len(fams)} families. Every task verifies on its own: `sha256sum -c checksums.sha256` in its "
           "folder, and its `content_sha256` is listed in `release.json`.", "",
           "## Sources", ""]
    for s, v in manifest["sources"].items():
        y = source_yaml(s)
        out += [f"### {s}", "", f"{y.get('name', s)} ({y.get('kind', '')}).", "",
                f"- Licence: **{v['licence']}**. {' '.join(str(v['licence_note']).split())}",
                f"- Provenance: {' '.join(str((y.get('data') or {}).get('original') or y.get('provenance', '')).split())}",
                f"- Content hash of the source folder: `{v['source_sha256']}`"]
        if s in check.SOURCES:
            a = splits.assignment(s)
            out.append(f"- Company split: {a.get('status')} on {a.get('approved', '?')}; this release's companies: "
                       f"{', '.join(sorted({c for _, m in tasks if m['source'] == s for c in m.get('companies', [])}))}")
        out.append("")
    out += ["## What the agent sees, and what only graders see", "",
            "| Agent (model-visible) | Graders only |", "|---|---|",
            "| `instruction.md`, `environment/` (data under /app/data), `prompt/` (API messages) | `tests/`: "
            "verifier, gold or ground truth, reference outputs; copied in only after the agent finishes |", "",
            "Every builder runs a leak check and `splits/check.py` fails if a grader-only file sits where the "
            "agent can see it. Network and clock policy per phase is in each `task.toml` and "
            "`[metadata.environment]`.", "",
            "## Splits", "",
            "Tasks are assigned to train, bench or held-out by company (every task containing a company's data "
            "goes to that company's split, in every family and disguise) and, for generated families, by seed "
            "range. Held-out seeds are secret and held-out tasks are never exported. Sources without a company "
            "split are one `eval` set.", "",
            "| Family | Version | Tasks | Reward |", "|---|---|---|---|"]
    out += [f"| {f} | {v['version']} | {v['tasks']} | {' '.join(str(family_yaml(f)['reward']).split())} |"
            for f, v in fams.items()]
    out += ["", "## Known limitations and validation status", "",
            "- Grader–expert agreement: not yet measured; one expert labelled all gold.",
            "- Calibration (pass@k, noise floor, ceiling per task): not yet run.",
            "- LLM-judged rewards (see each card) depend on the pinned judge model and need an API key.",
            "- Per-family limitations: `cards/<family>.md` and each family's `family.yaml`.", ""]
    return "\n".join(out)


def bundle(split: str, families: list[str] | None, use: str, preview: bool = False) -> tuple[dict, dict[str, bytes]]:
    """(release manifest, {path in bundle: bytes}) after every refusal check has passed."""
    cfg = release_config()
    tasks = select(split, families)
    problems = refusals(split, use, tasks, cfg["version"], preview)
    if problems:
        raise Refused("EXPORT REFUSED\n  " + "\n  ".join(problems))
    by_fam = defaultdict(list)
    for t in tasks:
        by_fam[t[1]["family"]].append(t)
    b = tasks[0][1]["build"]
    manifest = {
        "name": "rl_finance", "version": cfg["version"], "split": split, "use": use, "commit": b["repo_commit"],
        "built_at": b["built_at"], **({"preview": PREVIEW} if preview else {}),
        "families": {f: {"version": family_yaml(f)["version"], "tasks": len(v)} for f, v in sorted(by_fam.items())},
        "sources": {s: {"licence": (source_yaml(s).get("licence") or {}).get("status"),
                        "licence_note": (source_yaml(s).get("licence") or {}).get("note", ""),
                        "source_sha256": next(m["build"]["source_sha256"] for _, m in tasks if m["source"] == s)}
                    for s in sorted({m["source"] for _, m in tasks})},
        "tasks": {d.name: {"family": m["family"], "content_sha256": splits.manifest(m["family"])[d.name]["content_sha256"],
                           "fingerprint": m.get("fingerprint") or m.get("prompt", {}).get("fingerprint"),
                           "gold_fingerprint": splits.manifest(m["family"])[d.name]["gold_fingerprint"]}
                  for d, m in sorted(tasks, key=lambda t: t[0].name)},
    }
    stamp = f"> {PREVIEW}\n\n" if preview else ""
    files = {"release.json": (json.dumps(manifest, indent=1) + "\n").encode(),
             "CHANGELOG.md": (RELEASE / "CHANGELOG.md").read_bytes(),
             "DATASHEET.md": (stamp + datasheet(manifest, tasks)).encode()}
    for f, ts in by_fam.items():
        files[f"cards/{f}.md"] = (stamp + card(f, ts, split)).encode()
    for d, _ in tasks:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                files[f"tasks/{d.name}/{p.relative_to(d)}"] = p.read_bytes()
    return manifest, files


def is_executable(path: str) -> bool:
    return path.endswith(".sh")


def write_tar(out: pathlib.Path, root: str, files: dict[str, bytes], mtime: int) -> str:
    """A reproducible .tar.gz; returns its sha256."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(files):
            info = tarfile.TarInfo(f"{root}/{path}")
            info.size, info.mtime, info.mode = len(files[path]), mtime, 0o755 if is_executable(path) else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(files[path]))
    data = gzip.compress(buf.getvalue(), compresslevel=9, mtime=0)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    out.with_name(out.name + ".sha256").write_text(f"{digest}  {out.name}\n")
    return digest


def write_dir(out: pathlib.Path, files: dict[str, bytes]) -> None:
    if out.exists():
        shutil.rmtree(out)
    for path, data in files.items():
        p = out / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        if is_executable(path):
            p.chmod(0o755)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", required=True, help="bench, train or eval (held-out and retired are refused)")
    ap.add_argument("--family", action="append", help="only these families (default: every family built in the split)")
    ap.add_argument("--use", choices=sorted(CLEARS), default="eval", help="what the lab may do with it (licence gate)")
    ap.add_argument("--out", required=True, type=pathlib.Path, help="a .tar.gz path, or a folder")
    ap.add_argument("--preview", action="store_true",
                    help="skip the licence gate only, to review a bundle; folder output only, every document stamped")
    a = ap.parse_args(argv)
    tar = a.out.name.endswith(".tar.gz")
    if a.preview and tar:
        ap.error("--preview writes a folder, never an archive")
    manifest, files = bundle(a.split, a.family, a.use, a.preview)
    root = f"rl_finance-{manifest['version']}-{a.split}"
    if tar:
        mtime = int(datetime.fromisoformat(manifest["built_at"]).timestamp())
        digest = write_tar(a.out, root, files, mtime)
        print(f"{a.out}: {len(manifest['tasks'])} tasks, sha256 {digest}")
    else:
        write_dir(a.out / root, files)
        print(f"{a.out / root}: {len(manifest['tasks'])} tasks" + (" (PREVIEW: licence gate off)" if a.preview else ""))


if __name__ == "__main__":
    main()
