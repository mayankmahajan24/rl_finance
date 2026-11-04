"""Write one task directory in Harbor layout. Every family's builder writes through here.

    <task_id>/
      instruction.md                     what a Harbor agent is given
      task.toml                          Harbor config; [metadata] holds the repo's task metadata
      environment/Dockerfile, environment/data/...   what the agent sees, under /app
      prompt/                            exact messages for the repo's API runners (model-visible;
                                         only families with an API runner have it)
      tests/test.sh, tests/<verifier>, tests/common.py, tests/<gold_file>   copied in only after the agent finishes
      tests/judge.py, tests/client.py, tests/judge.json   the shared model judge, its API client and the
                                         family's pinned judge config (judged tasks)
      tests/provenance.json              who produced each of the family's gold inputs and its review state
      tests/CANARY                       the release's contamination canary (rl/canary.txt), never agent-visible
      tests/FILES                        every file tests/ ships; test.sh deletes anything else found in /tests
      solution/solve.sh (+ files)        reference solution for Harbor's oracle agent, where one exists
      checksums.sha256                   sha256 of every other file in the task (`sha256sum -c checksums.sha256`)

Integrity: task.toml [metadata.build] records when and from what the task was built (UTC time, or
SOURCE_DATE_EPOCH when set; repo commit and whether tracked files had uncommitted changes, builder,
Python and library versions, sha256 of the source's files). `content_sha256` hashes everything
except that build record, so it is identical across rebuilds of the same content. `write` returns
the task's manifest entry (splits/manifests/<family>.json): its split, case, fingerprint and the
other metadata in MANIFEST, the gold's fingerprint and content_sha256. The base image is pinned by digest and every pip package by version; packages only the
verifier needs are installed by test.sh, not baked into the agent's image.

Point in time: the agent phase has no network ([agent] network_mode = "no-network"), and neither
does the container between phases ([environment]). A run that needs the agent's model API (Claude
Code, Codex) or an agent install adds those hosts from the run config (`harbor run
--allow-agent-host`, `--allow-environment-host`), never from the task. The verifier reaches only
VERIFIER_HOSTS, and only when it calls a judge (a `judged` task). A dated task (`as_of`) pins the clock: libfaketime
makes `python` and `date` start at the as-of date, and data files carry it as their mtime. The
agent's own process (node, a CLI) keeps the real clock so its TLS still works; test.sh drops the
fake clock before the verifier runs. [metadata.environment] records the policy and
splits/check.py fails when it and task.toml disagree.

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
import re
import shutil
import sys
from datetime import datetime, timezone

import toml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import provenance  # noqa: E402
from lib import fingerprint, git  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

# python:3.12-slim as of 2026-11-03. Change the digest deliberately: it changes every task's environment.
BASE_IMAGE = "python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30"
JUDGE_PIP = "anthropic==0.89.0"   # verifier-only: LLM judge / scorer client, installed by test.sh
# Debian trixie's (the base image's) libfaketime; change it with the base image
FAKETIME_DEB = "libfaketime=0.9.10+2024-06-05+gba9ed5b2-0.6"
# a judged verifier reaches its model API and the package index test.sh installs the client from
VERIFIER_HOSTS = ["api.anthropic.com", "pypi.org", "files.pythonhosted.org"]

DOCKERFILE = """FROM {base}
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3 scipy==1.14.1{extra}
WORKDIR /app
COPY data /app/data
{gunzip}{clock}RUN mkdir -p /app/output /app/solution
"""
# libfaketime for the commands the agent analyses with; the agent's own process keeps the real clock
CLOCK = """RUN touch -d "{as_of} 12:00:00" /app/data/*
RUN apt-get update && apt-get install -y --no-install-recommends {deb} && rm -rf /var/lib/apt/lists/* \\
    && ln -s /usr/lib/*/faketime/libfaketime.so.1 /usr/local/lib/libfaketime.so.1
ENV TZ=UTC TASK_AS_OF={as_of} FAKETIME="@{as_of} 12:00:00" FAKETIME_ONLY_CMDS=python,python3,python3.12,date \\
    LD_PRELOAD=/usr/local/lib/libfaketime.so.1
"""

# Harbor uploads tests/ by merging it into whatever the agent left at /tests: remove every file the
# task didn't ship (tests/FILES), so nothing planted there is imported by the verifier.
TEST_CLEANUP = "cd /tests && find . -type f | sed 's|^\\./||' | grep -vxF -f FILES | tr '\\n' '\\0' | xargs -0 rm -f --"
TEST_SH = """#!/bin/bash
# Harbor copies this directory to /tests after the agent finishes; the verifier writes /logs/verifier/reward.txt
# or reward.json. A verifier that crashes writes neither, so Harbor records an error, never a zero.
mkdir -p /logs/verifier
""" + TEST_CLEANUP + """
cd /tests
unset LD_PRELOAD FAKETIME   # the verifier runs on the real clock (a dated task fakes it for the agent)
unset PYTHONPATH PYTHONSTARTUP PYTHONHOME; export PYTHONNOUSERSITE=1
{install}python /tests/{verifier}
"""
# a judged verifier installs the judge client; if that fails, the judge reports itself unavailable
JUDGE_INSTALL = ("pip install --no-cache-dir --quiet " + JUDGE_PIP
                 + " || echo 'judge client not installed; judged metrics will not be graded' >&2\n")
JUDGE_ENV = ('\n[verifier.env]\n# the pinned model judge (tests/judge.json); without a key, judged metrics are not\n'
             '# graded (JUDGE=keyword opts growth_thesis into its keyword grader)\n'
             'ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY:-}"\nJUDGE = "${JUDGE:-auto}"\n')

# file names under tests/ that only the grader may see: the gold (every family's `gold_file`) and the canary
GRADER_ONLY = ("gold.json", "CANARY")
# task metadata recorded in the family's manifest, where the task has it
MANIFEST = ("split", "case", "role", "workflow", "mode", "world", "status", "seed", "control", "companies", "fingerprint")

COMMON = HERE / "verify_common.py"
JUDGE = HERE / "judge.py"
RL = HERE.parents[1]
CLIENT = RL / "harness" / "client.py"   # the model client judge.py calls
CANARY = RL / "canary.txt"            # contamination canary: grader-side only (leakcheck.py)
BUILD_PACKAGES = ["pandas", "numpy", "scipy", "PyYAML", "toml"]


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@functools.cache
def _repo() -> tuple[str, bool]:
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


def network(verifier_hosts: list[str]) -> str:
    """The verifier's network policy lines: no network unless it calls out to the listed hosts."""
    if not verifier_hosts:
        return 'network_mode = "no-network"\n'
    return 'network_mode = "allowlist"\n' + toml.dumps({"allowed_hosts": list(verifier_hosts)})


def task_toml(task_id: str, description: str, keywords: list[str], metadata: dict, verifier_timeout: int,
              verifier_env: str = "", authors: list[dict] = (), version: str | None = None) -> str:
    task = {"name": f"rl_finance/{task_id}", "version": version, "description": description,
            "authors": [{"name": a["name"]} for a in authors], "keywords": keywords}
    head = toml.dumps({"task": {k: v for k, v in task.items() if v not in (None, [])}})
    hosts = metadata["environment"]["verifier_hosts"]
    return ('schema_version = "1.3"\n\n' + head + "\n" + toml.dumps({"metadata": metadata})
            + f"\n[verifier]\ntimeout_sec = {verifier_timeout}\n" + network(hosts) + verifier_env + """
[agent]
timeout_sec = 3600
network_mode = "no-network"   # a run adds its model API host with --allow-agent-host

[environment]
network_mode = "no-network"   # between phases too; agent installs add hosts with --allow-environment-host
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


def render(template: str, **kw) -> str:
    """Fill a template's {name} placeholders in one pass. Braces that aren't a placeholder (JSON
    examples) need no escaping; every placeholder must be given."""
    missing = sorted(set(re.findall(r"\{(\w+)\}", template)) - set(kw))
    assert not missing, f"no value for placeholders {missing}"
    return re.sub(r"\{(\w+)\}", lambda m: str(kw[m.group(1)]), template)


def write(dest: pathlib.Path, *, family: dict, builder: str, instruction: str, metadata: dict, description: str,
          keywords: list[str], verifier: str, tests: dict, gold: str, judged: bool = False,
          data: dict | None = None, prompt: dict | None = None, solution: dict | None = None, pip: str = "") -> dict:
    """Write the task and return its manifest entry. `family` is the family.yaml (authors, version,
    verifier timeout, judge); `metadata` must hold the task's `fingerprint` (what the agent sees) and
    `case` (the unit that never straddles splits). `gold` is the text of the gold, written to
tests/<family["gold_file"]>; `tests`,
    `data`, `prompt` and `solution` map file names to text, bytes, or a path to copy; `verifier` names
    the file in `tests` that test.sh runs. A `judged` task's verifier calls the family's pinned judge:
    it gets judge.py and judge.json, test.sh installs the judge client, and the verifier may reach
    VERIFIER_HOSTS; every other verifier gets no network. `pip` adds pinned packages to the agent's
    image. Data files ending in .gz are unpacked when the image is built, so the agent sees them
    uncompressed. A `metadata["as_of"]` date pins the container's clock to it."""
    gold_file = family["gold_file"]
    assert gold_file in GRADER_ONLY and gold_file not in tests, gold_file
    assert {"fingerprint", "case"} <= set(metadata), "metadata needs the task's fingerprint and case"
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "environment" / "data").mkdir(parents=True)
    for name, c in (data or {}).items():
        _put(dest / "environment" / "data" / name, c)
    gunzip = "RUN gunzip /app/data/*.gz\n" if any(n.endswith(".gz") for n in data or {}) else ""
    as_of = metadata.get("as_of")
    clock = CLOCK.format(as_of=as_of, deb=FAKETIME_DEB) if as_of else ""
    (dest / "environment" / "Dockerfile").write_text(
        DOCKERFILE.format(base=BASE_IMAGE, extra=pip, gunzip=gunzip, clock=clock))
    (dest / "instruction.md").write_text(instruction)
    for name, c in (prompt or {}).items():
        _put(dest / "prompt" / name, c)
    (dest / "tests").mkdir()
    (dest / "tests" / "test.sh").write_text(TEST_SH.format(verifier=verifier, install=JUDGE_INSTALL if judged else ""))
    (dest / "tests" / "test.sh").chmod(0o755)
    _put(dest / "tests" / "common.py", COMMON)
    if judged:
        _put(dest / "tests" / "judge.py", JUDGE)
        _put(dest / "tests" / "client.py", CLIENT)
        _put(dest / "tests" / "judge.json", json.dumps(family["judge"], indent=1) + "\n")
    _put(dest / "tests" / "CANARY", CANARY)
    for name, c in {**tests, gold_file: gold}.items():
        _put(dest / "tests" / name, c)
    (dest / "solution").mkdir()
    for name, c in (solution or {}).items():
        _put(dest / "solution" / name, c)
    prov = provenance.for_family(metadata["family"]) if family.get("gold_inputs") else []
    if prov:
        _put(dest / "tests" / "provenance.json", json.dumps(prov, indent=1, ensure_ascii=False) + "\n")
    shipped = {str(p.relative_to(dest / "tests")) for p in (dest / "tests").rglob("*") if p.is_file()} | {"FILES"}
    _put(dest / "tests" / "FILES", "".join(f"{f}\n" for f in sorted(shipped)))   # after every other tests/ file
    env = dict(metadata.get("environment", {}), internet=False, verifier_hosts=VERIFIER_HOSTS if judged else [])
    meta = dict(metadata, environment=env, **({"provenance": provenance.summary(prov)} if prov else {}),
                build=build_record(builder, metadata["source"]))
    (dest / "task.toml").write_text(task_toml(dest.name, description, keywords, meta, family["verifier_timeout_sec"],
                                              JUDGE_ENV if judged else "", family.get("authors", []),
                                              family.get("version")))
    files = sorted(p for p in dest.rglob("*") if p.is_file())
    (dest / "checksums.sha256").write_text(
        "".join(f"{_sha256(p.read_bytes())}  {p.relative_to(dest)}\n" for p in files))
    return {**{k: metadata[k] for k in MANIFEST if k in metadata},
            "gold_fingerprint": fingerprint(gold), "content_sha256": content_sha256(dest)}


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
