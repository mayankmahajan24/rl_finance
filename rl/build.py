"""Build tasks: the one entry point for every family. Ends with the split check.

Every family names its builder module in family.yaml (`builder`); the module's
`build(family_id, splits, n, controls)` writes Harbor tasks to rl/tasks/<split>/<task_id>/
(gitignored) and records them in splits/manifests/<family>.json (committed). `splits`, `n` and
`controls` choose what a generated family builds (default: bench and heldout); a family built from
fixed cases builds every case, each in its own split, and refuses `n` and `controls`. Commit the
manifests after a build that changes them; splits/check.py fails when built tasks and manifests
disagree.

    python rl/build.py                                    # every family
    python rl/build.py research_design kpi_nowcast
    python rl/build.py panel --split bench                # every family built by families/_shared/build_panel.py
    python rl/build.py data_audit --split train --n 200 --controls 20
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import sys

RL = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RL))
import lib  # noqa: E402
import splits  # noqa: E402

PANEL = "families._shared.build_panel"   # `panel` on the command line: every family this module builds


def main() -> None:
    families = lib.families()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("families", nargs="*", choices=[*families, "panel"], metavar="family",
                    help=f"any of {', '.join(families)}, or panel for the generated ones (default: all)")
    ap.add_argument("--split", action="append", choices=splits.SPLITS,
                    help="generated families only (default: bench and heldout; train needs --n)")
    ap.add_argument("--n", type=int, help="seeds per generated family (train only; bench/heldout use seeds.yaml)")
    ap.add_argument("--controls", type=int)
    args = ap.parse_args()

    chosen = args.families or families
    if "panel" in chosen:
        chosen = [f for f in families if f in chosen or lib.family(f)["builder"] == PANEL]
    for fam_id in chosen:
        builder = importlib.import_module(lib.family(fam_id)["builder"])
        builder.build(fam_id, args.split, args.n, args.controls)

    from splits import check
    check.main([])


if __name__ == "__main__":
    main()
