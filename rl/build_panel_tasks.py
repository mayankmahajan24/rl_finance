"""Build the generated txn_panel families (data_audit, anomaly_scoring, growth_thesis) as Harbor tasks.

Each split's tasks are generated only from that split's companies (splits/txn_panel.yaml), from
that split's seeds (splits/seeds.yaml; held-out seeds are secret). Output goes to
rl/tasks/<split>/<task_id>/ (gitignored: tasks are rebuilt, not committed) and a record of what was
built, with hashes, to splits/manifests/<family>.json.

Usage:
    python rl/build_panel_tasks.py --split bench                       # all three families
    python rl/build_panel_tasks.py --split train --family data_audit --n 200 --controls 20
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import shutil
import sys

import yaml

RL = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RL))
import splits  # noqa: E402
from families._shared import harbor  # noqa: E402
from sources.txn_panel import panel  # noqa: E402

FAMILIES = ["data_audit", "anomaly_scoring", "growth_thesis"]
SCHEMA = (RL / "families" / "_shared" / "panel_schema.md").read_text().rstrip("\n")
TASKS = RL / "tasks"


def render(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{{" + k + "}}", str(v))
    assert "{{" not in template, template[template.index("{{"):][:40]
    return template


def task_id(prefix: str, split: str, seed: int, control: bool, index: int) -> str:
    # never the seed itself: held-out seeds are secret, and ids are not
    return f"{prefix}-{split}-" + (f"control-{index:02d}" if control else f"{index:03d}")


def build_family(fam_id: str, split: str, n: int | None, controls: int | None, full) -> dict:
    fam_dir = RL / "families" / fam_id
    fam = yaml.safe_load((fam_dir / "family.yaml").read_text())
    gen = importlib.import_module(f"families.{fam_id}.generate")
    instruction_t = (fam_dir / "instruction.md").read_text()
    artifacts = panel.data_artifacts()

    comps = splits.companies(fam["source"], split)
    sensors = panel.sensors_of(comps)
    raw = full[full.ticker.isin(sensors)].reset_index(drop=True)

    built, i_task, i_ctrl = {}, 0, 0
    for seed, control in splits.seeds(fam_id, split, n, controls):
        if fam_id == "growth_thesis":
            template = [t for t in gen.TEMPLATE_TICKERS if t in sensors]
            if not template:
                raise SystemExit(f"{split}: no clean airline in this split for the seasonality template")
            df, truth = gen.make_variant(seed, control, full, template_tickers=template)
            used = sorted({panel.company_of_sensor(t) for t in template})
        elif fam_id == "anomaly_scoring":
            df, truth = gen.make_variant(seed, control, raw, artifacts, panel_end=panel.PANEL_END)
            used = comps
        else:
            df, truth = gen.make_variant(seed, control, raw, artifacts)
            used = comps
        if control:
            i_ctrl += 1
        else:
            i_task += 1
        tid = task_id(fam["task_prefix"], split, seed, control, i_ctrl if control else i_task)
        instruction = render(instruction_t, schema=SCHEMA,
                             **({"y1": truth["year_start"], "y2": truth["year_end"]} if fam_id == "growth_thesis" else {}))
        data = {"transactions.csv": df.to_csv(index=False, date_format="%Y-%m-%d")}
        meta = {"id": tid, "family": fam_id, "role": fam["role"], "workflow": fam["workflow"], "mode": fam["mode"],
                "world": fam["world"], "source": fam["source"], "split": split,
                "seed": None if split == "heldout" else seed, "control": control, "companies": used,
                "generator": f"rl/families/{fam_id}/{fam['generator']}"}
        params = ({"year_start": truth["year_start"], "year_end": truth["year_end"]}
                  if fam_id == "growth_thesis" else None)
        info = harbor.write_panel_task(TASKS / split / tid, fam_dir, fam, instruction, data, truth, meta, params)
        built[tid] = {"split": split, "role": fam["role"], "workflow": fam["workflow"], "mode": fam["mode"],
                      "world": fam["world"], "status": "graded", "seed": seed, "control": control,
                      "companies": used, **info}
        print(f"  {tid}")
    return built


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=splits.SPLITS)
    ap.add_argument("--family", choices=FAMILIES, action="append", help="default: all three")
    ap.add_argument("--n", type=int, help="seeds per family (train needs it; bench/heldout use seeds.yaml)")
    ap.add_argument("--controls", type=int)
    args = ap.parse_args()

    full = panel.load_df()
    for fam_id in args.family or FAMILIES:
        print(f"{fam_id} ({args.split})")
        prefix = yaml.safe_load((RL / "families" / fam_id / "family.yaml").read_text())["task_prefix"]
        for stale in (TASKS / args.split).glob(f"{prefix}-*"):   # a rebuilt split replaces its tasks
            shutil.rmtree(stale)
        built = build_family(fam_id, args.split, args.n, args.controls, full)
        mpath = splits.write_manifest(fam_id, built, splits_rebuilt={args.split})
        print(f"{len(built)} tasks; {mpath.relative_to(RL.parent)}")


if __name__ == "__main__":
    main()
