"""Write one task directory in Harbor layout (schema_version 1.3).

    <task_id>/
      instruction.md
      task.toml                          harness metadata; never shown to the agent
      environment/Dockerfile, environment/data/...   what the agent sees, under /app
      tests/test.sh, tests/<verifier>, tests/common.py, tests/ground_truth.json   copied in only after the agent finishes
      solution/solve.sh (+ files)        reference solution, run by Harbor's oracle agent

Dockerfile, test.sh and the toml body are the pilot's (~/altdata_evals/build_tasks.py); task.toml
gains the repo's metadata (role, workflow, split, companies, fingerprint) under [metadata].
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib import fingerprint  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

DOCKERFILE = """FROM python:3.12-slim
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3 scipy==1.14.1{extra}
WORKDIR /app
COPY data /app/data
RUN mkdir -p /app/output /app/solution
"""

TEST_SH = """#!/bin/bash
# Harbor copies this directory to /tests after the agent finishes; the reward goes to /logs/verifier/reward.txt.
mkdir -p /logs/verifier
cd /tests
python /tests/{verifier} || echo 0 > /logs/verifier/reward.txt
"""

JUDGE_ENV = ('\n[verifier.env]\n# LLM judge for the memo rubric; falls back to keyword grading when no key is set\n'
             'ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY:-}"\nJUDGE = "${JUDGE:-auto}"\n'
             'JUDGE_MODEL = "${JUDGE_MODEL:-claude-opus-5-5}"\n')


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))


def task_toml(task_id: str, fam: dict, meta: dict) -> str:
    lines = ['schema_version = "1.3"', "", "[task]", f'name = "rl_finance/{task_id}"',
             f"description = {_toml_value(fam['description'])}",
             f'keywords = ["alt-data", "data-science", "{fam["task_prefix"]}"]', "", "[metadata]"]
    lines += [f"{k} = {_toml_value(v)}" for k, v in meta.items() if v is not None]
    lines += ["", "[verifier]", f"timeout_sec = {fam['verifier_timeout_sec']}"]
    body = "\n".join(lines) + "\n" + (JUDGE_ENV if fam.get("llm_judge") else "")
    return body + """[agent]
timeout_sec = 3600

[environment]
build_timeout_sec = 900
cpus = 2
memory_mb = 4096
storage_mb = 4096
workdir = "/app"
"""


def write_task(dest: pathlib.Path, fam_dir: pathlib.Path, fam: dict, instruction: str, data: dict[str, str],
               truth: dict, meta: dict, solution_params: dict | None = None) -> dict:
    """Write the task; return manifest info (sha256 of what the agent sees and of the ground truth)."""
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "environment" / "data").mkdir(parents=True)
    (dest / "tests").mkdir()
    (dest / "solution").mkdir()
    for name, text in data.items():
        (dest / "environment" / "data" / name).write_text(text)
    (dest / "instruction.md").write_text(instruction)
    verifier = pathlib.Path(fam["verifier"]).name
    extra = " anthropic" if fam.get("llm_judge") else ""   # LLM judge; agents may ignore it
    (dest / "environment" / "Dockerfile").write_text(DOCKERFILE.format(extra=extra))
    (dest / "tests" / "test.sh").write_text(TEST_SH.format(verifier=verifier))
    (dest / "tests" / "test.sh").chmod(0o755)
    shutil.copy(fam_dir / fam["verifier"], dest / "tests" / verifier)
    shutil.copy(HERE / "verify_common.py", dest / "tests" / "common.py")
    gt = json.dumps(truth, indent=1, default=str)
    (dest / "tests" / "ground_truth.json").write_text(gt)
    for f in (fam_dir / "solutions" / "reference").iterdir():
        if f.is_file():
            shutil.copy(f, dest / "solution")
    if solution_params is not None:
        (dest / "solution" / "params.json").write_text(json.dumps(solution_params))
    fp = fingerprint(instruction, *[data[k] for k in sorted(data)])
    meta = dict(meta, fingerprint=fp)
    (dest / "task.toml").write_text(task_toml(dest.name, fam, meta))
    return {"fingerprint": fp, "ground_truth_sha256": fingerprint(gt)}
