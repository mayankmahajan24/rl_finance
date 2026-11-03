"""Write one task directory in Harbor layout. Every family's builder writes through here.

    <task_id>/
      instruction.md                     what a Harbor agent is given
      task.toml                          Harbor config; [metadata] holds the repo's task metadata
      environment/Dockerfile, environment/data/...   what the agent sees, under /app
      prompt/                            exact messages for the repo's API runners (model-visible;
                                         only families with an API runner have it)
      tests/test.sh, tests/<verifier>, tests/common.py, gold   copied in only after the agent finishes
      solution/solve.sh (+ files)        reference solution for Harbor's oracle agent, where one exists
      checksums.sha256                   sha256 of every other file in the task (`sha256sum -c checksums.sha256`)

Integrity: task.toml [metadata.build] records when and from what the task was built (UTC time, or
SOURCE_DATE_EPOCH when set; repo commit and whether tracked files had uncommitted changes, builder,
Python and library versions, sha256 of the source's files). `content_sha256` (returned, and recorded in the family's manifest)
hashes everything except that build record, so it is identical across rebuilds of the same
content. The base image is pinned by digest and every pip package by version; packages only the
verifier needs are installed by test.sh, not baked into the agent's image.

Dockerfile, test.sh and the toml body started as the ~/altdata_evals pilot's.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.metadata
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import toml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib import fingerprint  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

# python:3.12-slim as of 2026-11-03. Change the digest deliberately: it changes every task's environment.
BASE_IMAGE = "python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30"
JUDGE_PIP = "anthropic==0.89.0"   # verifier-only: LLM judge / scorer client, installed by test.sh

DOCKERFILE = """FROM {base}
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3 scipy==1.14.1{extra}
WORKDIR /app
COPY data /app/data
{gunzip}RUN mkdir -p /app/output /app/solution
"""

TEST_SH = """#!/bin/bash
# Harbor copies this directory to /tests after the agent finishes; the reward goes to /logs/verifier/reward.txt.
mkdir -p /logs/verifier
cd /tests
{install}python /tests/{verifier} || echo 0 > /logs/verifier/reward.txt
"""
TEST_PIP = ("pip install --no-cache-dir --quiet {pkgs} "
            "|| echo 'verifier packages not installed; LLM grading will be skipped or fail' >&2\n")

JUDGE_ENV = ('\n[verifier.env]\n# LLM judge for the memo rubric; falls back to keyword grading when no key is set\n'
             'ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY:-}"\nJUDGE = "${JUDGE:-auto}"\n'
             'JUDGE_MODEL = "${JUDGE_MODEL:-claude-opus-5-5}"\n')

COMMON = HERE / "verify_common.py"
RL = HERE.parents[1]
BUILD_PACKAGES = ["pandas", "numpy", "scipy", "PyYAML", "toml"]


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@functools.cache
def _repo() -> tuple[str, bool]:
    def git(*a):
        return subprocess.run(["git", *a], cwd=RL, capture_output=True, text=True).stdout.strip()
    return git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--untracked-files=no"))


@functools.cache
def source_sha256(source: str) -> str:
    """sha256 over every file of rl/sources/<source>/ (path and content), so a task names the exact data."""
    root = RL / "sources" / source
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(str(f.relative_to(root)).encode() + b"\0" + _sha256(f.read_bytes()).encode() + b"\n")
    return h.hexdigest()


def built_at() -> str:
    """UTC build time; SOURCE_DATE_EPOCH (the reproducible-builds convention) pins it, so a release
    build stamped with its commit's time (export.py) is byte-identical when rebuilt."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    t = datetime.fromtimestamp(int(epoch), timezone.utc) if epoch else datetime.now(timezone.utc)
    return t.isoformat(timespec="seconds")


def build_record(builder: str, source: str) -> dict:
    commit, dirty = _repo()
    return {"built_at": built_at(), "repo_commit": commit,
            "repo_dirty": dirty, "builder": builder, "python": platform.python_version(),
            "packages": {p: importlib.metadata.version(p) for p in BUILD_PACKAGES},
            "source": source, "source_sha256": source_sha256(source), "base_image": BASE_IMAGE}


def task_toml(task_id: str, description: str, keywords: list[str], metadata: dict, verifier_timeout: int,
              verifier_env: str = "", authors: list[dict] = (), version: str | None = None) -> str:
    task = {"name": f"rl_finance/{task_id}", "version": version, "description": description,
            "authors": list(authors), "keywords": keywords}
    head = toml.dumps({"task": {k: v for k, v in task.items() if v not in (None, [])}})
    return ('schema_version = "1.3"\n\n' + head + "\n" + toml.dumps({"metadata": metadata})
            + f"\n[verifier]\ntimeout_sec = {verifier_timeout}\n" + verifier_env + """
[agent]
timeout_sec = 3600

[environment]
build_timeout_sec = 900
cpus = 2
memory_mb = 4096
storage_mb = 4096
workdir = "/app"
""")


def _put(path: pathlib.Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, pathlib.Path):
        shutil.copy(content, path)
    elif isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def write(dest: pathlib.Path, *, family: dict, builder: str, instruction: str, metadata: dict, description: str,
          keywords: list[str], verifier: str, tests: dict, verifier_timeout: int = 600, verifier_env: str = "",
          data: dict | None = None, prompt: dict | None = None, solution: dict | None = None,
          pip: str = "", test_pip: str = "") -> str:
    """Write the task and return its content_sha256. `family` is the family.yaml (authors, version);
    `tests`, `data`, `prompt` and `solution` map file names to text, bytes, or a path to copy;
    `verifier` names the file in `tests` that test.sh runs. `pip` adds pinned packages to the agent's
    image, `test_pip` pinned packages test.sh installs for the verifier only. Data files ending in
    .gz are unpacked when the image is built, so the agent sees them uncompressed."""
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "environment" / "data").mkdir(parents=True)
    for name, c in (data or {}).items():
        _put(dest / "environment" / "data" / name, c)
    gunzip = "RUN gunzip /app/data/*.gz\n" if any(n.endswith(".gz") for n in data or {}) else ""
    (dest / "environment" / "Dockerfile").write_text(DOCKERFILE.format(base=BASE_IMAGE, extra=pip, gunzip=gunzip))
    (dest / "instruction.md").write_text(instruction)
    for name, c in (prompt or {}).items():
        _put(dest / "prompt" / name, c)
    (dest / "tests").mkdir()
    install = TEST_PIP.format(pkgs=test_pip.strip()) if test_pip.strip() else ""
    (dest / "tests" / "test.sh").write_text(TEST_SH.format(verifier=verifier, install=install))
    (dest / "tests" / "test.sh").chmod(0o755)
    _put(dest / "tests" / "common.py", COMMON)
    for name, c in tests.items():
        _put(dest / "tests" / name, c)
    (dest / "solution").mkdir()
    for name, c in (solution or {}).items():
        _put(dest / "solution" / name, c)
    meta = dict(metadata, build=build_record(builder, metadata["source"]))
    (dest / "task.toml").write_text(task_toml(dest.name, description, keywords, meta, verifier_timeout, verifier_env,
                                              family.get("authors", []), family.get("version")))
    files = sorted(p for p in dest.rglob("*") if p.is_file())
    (dest / "checksums.sha256").write_text(
        "".join(f"{_sha256(p.read_bytes())}  {p.relative_to(dest)}\n" for p in files))
    return content_sha256(dest)


def content_sha256(dest: pathlib.Path) -> str:
    """Hash of a task's content: every file except task.toml and checksums.sha256, plus task.toml's
    parsed config without [metadata.build]. Identical across rebuilds of the same content."""
    import tomllib
    top = {dest / "task.toml", dest / "checksums.sha256"}
    lines = [f"{_sha256(p.read_bytes())}  {p.relative_to(dest)}"
             for p in sorted(dest.rglob("*")) if p.is_file() and p not in top]
    cfg = tomllib.loads((dest / "task.toml").read_text())
    cfg.get("metadata", {}).pop("build", None)
    return _sha256(("\n".join(lines) + "\n" + json.dumps(cfg, sort_keys=True)).encode())


def write_panel_task(dest: pathlib.Path, fam_dir: pathlib.Path, fam: dict, instruction: str, data: dict[str, str],
                     truth: dict, meta: dict, solution_params: dict | None = None) -> dict:
    """A generated txn_panel task; returns manifest info (fingerprint of what the agent sees, ground-truth hash)."""
    gt = json.dumps(truth, indent=1, default=str)
    verifier = pathlib.Path(fam["verifier"]).name
    solution = {f.name: f for f in (fam_dir / "solutions" / "reference").iterdir() if f.is_file()}
    if solution_params is not None:
        solution["params.json"] = json.dumps(solution_params)
    fp = fingerprint(instruction, *[data[k] for k in sorted(data)])
    content = write(dest, family=fam, builder="rl/families/_shared/build_panel.py", instruction=instruction,
                    metadata=dict(meta, fingerprint=fp), description=fam["description"],
                    keywords=["alt-data", "data-science", fam["task_prefix"]], verifier=verifier,
                    tests={verifier: fam_dir / fam["verifier"], "ground_truth.json": gt},
                    verifier_timeout=fam["verifier_timeout_sec"],
                    verifier_env=JUDGE_ENV if fam.get("llm_judge") else "", data=data, solution=solution,
                    test_pip=JUDGE_PIP if fam.get("llm_judge") else "")
    return {"fingerprint": fp, "gold_fingerprint": fingerprint(gt), "content_sha256": content}
