"""Build a generated txn_panel family as Harbor tasks: the builder of every family whose family.yaml
says `builder: families._shared.build_panel`.

Each split's tasks are generated only from that split's companies (splits/txn_panel.yaml), from
that split's seeds (splits/seeds.yaml; held-out seeds are secret). Output goes to
rl/tasks/<split>/<task_id>/ (gitignored: tasks are rebuilt, not committed) and a record of what was
built, with hashes, to splits/manifests/<family>.json.

A family's generator is families/<family>/generate.py, with one function:

    make_variant(seed, control, ctx) -> (df, truth, render_kw, solution_params, companies)

`ctx` (Context) holds the split's slice of the panel and nothing outside it. The generator returns
the panel the agent gets, the gold, values for the instruction's placeholders besides {schema},
params for the reference solution (or None), and the split's companies the task was built from.

Run through rl/build.py:
    python rl/build.py panel --split bench                       # every generated family
    python rl/build.py data_audit --split train --n 200 --controls 20
"""

from __future__ import annotations

import functools
import importlib
import json
import pathlib
import shutil
import sys
from dataclasses import dataclass

import pandas as pd

RL = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RL))
import lib  # noqa: E402
import splits  # noqa: E402
from families._shared import harbor  # noqa: E402
from sources.txn_panel import panel  # noqa: E402

SCHEMA = (RL / "families" / "_shared" / "panel_schema.md").read_text().rstrip("\n")
FIRM = (RL / "families" / "_shared" / "firm.md").read_text().rstrip("\n")
DEFAULT_SPLITS = ["bench", "heldout"]      # train has no fixed size: it needs n


@dataclass(frozen=True)
class Context:
    """One split's slice of the panel: everything a generator may use."""
    companies: list[str]
    sensors: list[str]
    raw: pd.DataFrame          # the split's sensors' rows only
    artifacts: tuple           # (required, optional) natural artifacts, original coordinates
    panel_end: str


@functools.cache
def _panel() -> pd.DataFrame:
    return panel.load_df()


def context(source: str, split: str) -> Context:
    comps = splits.companies(source, split)
    sensors = panel.sensors_of(comps)
    raw = _panel()[_panel().ticker.isin(sensors)].reset_index(drop=True)
    return Context(comps, sensors, raw, panel.data_artifacts(), panel.PANEL_END)


def task_id(prefix: str, split: str, seed: int, control: bool, index: int) -> str:
    # never the seed itself: held-out seeds are secret, and ids are not
    return f"{prefix}-{split}-" + (f"control-{index:02d}" if control else f"{index:03d}")


def write_task(dest: pathlib.Path, fam: dict, instruction: str, data: dict[str, str], truth: dict, meta: dict,
               solution_params: dict | None) -> dict:
    """One generated task; returns its manifest entry."""
    fam_dir = lib.FAMILIES / fam["id"]
    verifier = pathlib.Path(fam["verifier"]).name
    solution = {f.name: f for f in (fam_dir / "solutions" / "reference").iterdir() if f.is_file()}
    if solution_params is not None:
        solution["params.json"] = json.dumps(solution_params)
    fp = lib.fingerprint(instruction, *[data[k] for k in sorted(data)])
    return harbor.write(dest, family=fam, builder="rl/families/_shared/build_panel.py", instruction=instruction,
                        metadata=dict(meta, fingerprint=fp), description=fam["description"],
                        keywords=["alt-data", "data-science", fam["task_prefix"]], verifier=verifier,
                        tests={verifier: fam_dir / fam["verifier"]}, gold=json.dumps(truth, indent=1, default=str),
                        judged="judge" in fam, data=data, solution=solution)


def build_split(fam_id: str, split: str, n: int | None, controls: int | None) -> dict:
    fam = lib.family(fam_id)
    gen = importlib.import_module(f"families.{fam_id}.generate")
    instruction_t = (lib.FAMILIES / fam_id / "instruction.md").read_text()
    ctx = context(fam["source"], split)
    (role,), (workflow,), (mode,), (world,) = fam["role"], fam["workflow"], fam["mode"], fam["world"]
    built, i_task, i_ctrl = {}, 0, 0
    for seed, control in splits.seeds(fam_id, split, n, controls):
        df, truth, render_kw, params, used = gen.make_variant(seed, control, ctx)
        if control:
            i_ctrl += 1
        else:
            i_task += 1
        tid = task_id(fam["task_prefix"], split, seed, control, i_ctrl if control else i_task)
        instruction = harbor.render(instruction_t, schema=SCHEMA, firm=FIRM, **render_kw)
        data = {"transactions.csv": df.to_csv(index=False, date_format="%Y-%m-%d")}
        meta = {"id": tid, "family": fam_id, "case": tid, "role": role, "workflow": workflow, "mode": mode,
                "world": world, "status": "graded", "source": fam["source"], "split": split,
                "seed": None if split == "heldout" else seed, "control": control, "companies": used,
                "generator": f"rl/families/{fam_id}/generate.py"}
        built[tid] = write_task(lib.TASKS / split / tid, fam, instruction, data, truth, meta, params)
        print(f"  {tid}")
    return built


def build(family_id: str, split_names: list[str] | None = None, n: int | None = None,
          controls: int | None = None) -> None:
    """Build one generated family's splits (default bench and heldout, sized by seeds.yaml; train
    needs `n`)."""
    prefix = lib.family(family_id)["task_prefix"]
    for split in split_names or DEFAULT_SPLITS:
        if split == "train" and n is None:
            raise SystemExit("train has no fixed size: pass --n (and --controls)")
        print(f"{family_id} ({split})")
        for stale in (lib.TASKS / split).glob(f"{prefix}-*"):   # a rebuilt split replaces its tasks
            shutil.rmtree(stale)
        built = build_split(family_id, split, n, controls)
        mpath = splits.write_manifest(family_id, built, splits_rebuilt={split})
        print(f"{len(built)} tasks; {mpath.relative_to(RL.parent)}")
