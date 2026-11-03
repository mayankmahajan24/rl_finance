"""Build the generated txn_panel families (data_audit, anomaly_scoring, growth_thesis) as Harbor tasks.

Each split's tasks are generated only from that split's companies (splits/txn_panel.yaml), from
that split's seeds (splits/seeds.yaml; held-out seeds are secret). Output goes to
rl/tasks/<split>/<task_id>/ (gitignored: tasks are rebuilt, not committed) and a manifest of what
was built, with hashes, to splits/manifests/ (held-out: splits/secrets/manifests/).

The `pilot` split rebuilds the 18 tasks of ~/altdata_evals on every company, to prove the port
reproduces them. It belongs to no split and is never used for training or eval.

Usage:
    python rl/build_panel_tasks.py --split pilot
    python rl/build_panel_tasks.py --split bench                       # all three families
    python rl/build_panel_tasks.py --split train --family data_audit --n 200 --controls 20
"""

from __future__ import annotations

import argparse
import importlib
import json
import pathlib
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
    if split == "pilot":
        return f"{prefix}-s{seed}" + ("-control" if control else "")
    # never the seed itself: held-out seeds are secret, and ids are not
    return f"{prefix}-{split}-" + (f"control-{index:02d}" if control else f"{index:03d}")


def manifest_path(split: str) -> pathlib.Path:
    base = splits.SECRETS / "manifests" if split == "heldout" else splits.HERE / "manifests"
    return base / f"txn_panel_{split}.json"


def build_family(fam_id: str, split: str, n: int | None, controls: int | None, full) -> dict:
    fam_dir = RL / "families" / fam_id
    fam = yaml.safe_load((fam_dir / "family.yaml").read_text())
    gen = importlib.import_module(f"families.{fam_id}.generate")
    instruction_t = (fam_dir / "instruction.md").read_text()
    artifacts = panel.data_artifacts()

    if split == "pilot":
        comps = sorted(panel.companies())
    else:
        comps = splits.companies(fam["source"], split)
    sensors = panel.sensors_of(comps)
    raw = full[full.ticker.isin(sensors)].reset_index(drop=True) if split != "pilot" else full

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
        meta = {"family": fam_id, "role": fam["role"], "workflow": fam["workflow"], "mode": fam["mode"],
                "world": fam["world"], "source": fam["source"], "split": split,
                "seed": None if split == "heldout" else seed, "control": control, "companies": used,
                "generator": f"rl/families/{fam_id}/{fam['generator']}"}
        params = ({"year_start": truth["year_start"], "year_end": truth["year_end"]}
                  if fam_id == "growth_thesis" else None)
        info = harbor.write_task(TASKS / split / tid, fam_dir, fam, instruction, data, truth, meta, params)
        built[tid] = {"family": fam_id, "seed": seed, "control": control, "companies": used, **info}
        print(f"  {tid}")
    return built


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["pilot", *splits.SPLITS])
    ap.add_argument("--family", choices=FAMILIES, action="append", help="default: all three")
    ap.add_argument("--n", type=int, help="seeds per family (train needs it; bench/heldout use seeds.yaml)")
    ap.add_argument("--controls", type=int)
    args = ap.parse_args()

    full = panel.load_df()
    mpath = manifest_path(args.split)
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    for fam_id in args.family or FAMILIES:
        print(f"{fam_id} ({args.split})")
        manifest = {k: v for k, v in manifest.items() if v["family"] != fam_id}   # rebuilt family replaces its entries
        for stale in (TASKS / args.split).glob(f"{yaml.safe_load((RL / 'families' / fam_id / 'family.yaml').read_text())['task_prefix']}-*"):
            import shutil
            shutil.rmtree(stale)
        manifest.update(build_family(fam_id, args.split, args.n, args.controls, full))
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + "\n")
    print(f"{len(manifest)} tasks in {mpath.relative_to(RL.parent)}")


if __name__ == "__main__":
    main()
