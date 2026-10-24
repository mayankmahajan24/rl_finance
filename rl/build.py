"""Build tasks: the one entry point for every family. Ends with the split check.

Each family's builder writes Harbor tasks to rl/tasks/<split>/<task_id>/ (gitignored) and records
them in splits/manifests/<family>.json (committed). Commit the manifests after a build that changes
them; splits/check.py fails when built tasks and manifests disagree.

    python rl/build.py                                    # research_design, kpi_nowcast, panel bench + heldout
    python rl/build.py research_design kpi_nowcast
    python rl/build.py panel --split bench                # data_audit, anomaly_scoring, growth_thesis
    python rl/build.py data_audit --split train --n 200 --controls 20
"""

from __future__ import annotations

import argparse
import pathlib
import sys

RL = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RL))
import splits  # noqa: E402
from families._shared import build_panel  # noqa: E402

BUILDERS = ["research_design", "kpi_nowcast"]          # families with their own build.py
PANEL = build_panel.FAMILIES                           # generated per split by families/_shared/build_panel.py


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("families", nargs="*", choices=[*BUILDERS, *PANEL, "panel"], metavar="family",
                    help=f"any of {', '.join([*BUILDERS, *PANEL])}, or panel for all three generated ones (default: all)")
    ap.add_argument("--split", action="append", choices=splits.SPLITS,
                    help="generated families only (default: bench and heldout; train needs --n)")
    ap.add_argument("--n", type=int, help="seeds per generated family (train only; bench/heldout use seeds.yaml)")
    ap.add_argument("--controls", type=int)
    args = ap.parse_args()

    chosen = args.families or [*BUILDERS, "panel"]
    panel_fams = PANEL if "panel" in chosen else [f for f in PANEL if f in chosen]
    if (args.split or args.n is not None) and not panel_fams:
        ap.error("--split, --n and --controls apply to the generated families only")
    if "research_design" in chosen:
        from families.research_design import build
        build.main()
    if "kpi_nowcast" in chosen:
        from families.kpi_nowcast import build
        build.main([])
    for split in args.split or ["bench", "heldout"]:
        if panel_fams:
            if split == "train" and args.n is None:
                ap.error("train has no fixed size: pass --n (and --controls)")
            build_panel.build(panel_fams, split, args.n, args.controls)

    from splits import check
    check.main()


if __name__ == "__main__":
    main()
