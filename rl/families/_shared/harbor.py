"""Write one task directory in Harbor layout. Every family's builder writes through here.

    <task_id>/
      instruction.md                     what a Harbor agent is given
      task.toml                          Harbor config; [metadata] holds the repo's task metadata
      environment/Dockerfile, environment/data/...   what the agent sees, under /app
      prompt/                            exact messages for the repo's API runners (model-visible;
                                         only families with an API runner have it)
      tests/test.sh, tests/<verifier>, tests/common.py, gold   copied in only after the agent finishes
      solution/solve.sh (+ files)        reference solution for Harbor's oracle agent, where one exists

Dockerfile, test.sh and the toml body are the ~/altdata_evals pilot's; families add pip packages and
gzip-compressed data files (unpacked in the image) where they need them.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

import toml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib import fingerprint  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

DOCKERFILE = """FROM python:3.12-slim
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3 scipy==1.14.1{extra}
WORKDIR /app
COPY data /app/data
{gunzip}RUN mkdir -p /app/output /app/solution
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

COMMON = HERE / "verify_common.py"


def task_toml(task_id: str, description: str, keywords: list[str], metadata: dict, verifier_timeout: int,
              verifier_env: str = "") -> str:
    head = toml.dumps({"task": {"name": f"rl_finance/{task_id}", "description": description, "keywords": keywords}})
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


def write(dest: pathlib.Path, *, instruction: str, metadata: dict, description: str, keywords: list[str],
          verifier: str, tests: dict, verifier_timeout: int = 600, verifier_env: str = "",
          data: dict | None = None, prompt: dict | None = None, solution: dict | None = None,
          pip: str = "") -> None:
    """Write the task. `tests`, `data`, `prompt` and `solution` map file names to text, bytes, or a
    path to copy; `verifier` names the file in `tests` that test.sh runs. Data files ending in .gz
    are unpacked when the image is built, so the agent sees them uncompressed."""
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "environment" / "data").mkdir(parents=True)
    for name, c in (data or {}).items():
        _put(dest / "environment" / "data" / name, c)
    gunzip = "RUN gunzip /app/data/*.gz\n" if any(n.endswith(".gz") for n in data or {}) else ""
    (dest / "environment" / "Dockerfile").write_text(DOCKERFILE.format(extra=pip, gunzip=gunzip))
    (dest / "instruction.md").write_text(instruction)
    for name, c in (prompt or {}).items():
        _put(dest / "prompt" / name, c)
    (dest / "tests").mkdir()
    (dest / "tests" / "test.sh").write_text(TEST_SH.format(verifier=verifier))
    (dest / "tests" / "test.sh").chmod(0o755)
    _put(dest / "tests" / "common.py", COMMON)
    for name, c in tests.items():
        _put(dest / "tests" / name, c)
    (dest / "solution").mkdir()
    for name, c in (solution or {}).items():
        _put(dest / "solution" / name, c)
    (dest / "task.toml").write_text(task_toml(dest.name, description, keywords, metadata, verifier_timeout,
                                              verifier_env))


def write_panel_task(dest: pathlib.Path, fam_dir: pathlib.Path, fam: dict, instruction: str, data: dict[str, str],
                     truth: dict, meta: dict, solution_params: dict | None = None) -> dict:
    """A generated txn_panel task; returns manifest info (fingerprint of what the agent sees, ground-truth hash)."""
    gt = json.dumps(truth, indent=1, default=str)
    verifier = pathlib.Path(fam["verifier"]).name
    solution = {f.name: f for f in (fam_dir / "solutions" / "reference").iterdir() if f.is_file()}
    if solution_params is not None:
        solution["params.json"] = json.dumps(solution_params)
    fp = fingerprint(instruction, *[data[k] for k in sorted(data)])
    write(dest, instruction=instruction, metadata=dict(meta, fingerprint=fp), description=fam["description"],
          keywords=["alt-data", "data-science", fam["task_prefix"]], verifier=verifier,
          tests={verifier: fam_dir / fam["verifier"], "ground_truth.json": gt},
          verifier_timeout=fam["verifier_timeout_sec"], verifier_env=JUDGE_ENV if fam.get("llm_judge") else "",
          data=data, solution=solution, pip=" anthropic" if fam.get("llm_judge") else "")   # LLM judge; agents may ignore it
    return {"fingerprint": fp, "gold_fingerprint": fingerprint(gt)}
