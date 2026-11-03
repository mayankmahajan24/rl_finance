"""Review and approve a family's instrument (rl/instrument.py): the files that decide what a model sees
and how it is scored. Live API runs and release checks refuse a family whose instrument changed since
its last approval.

    python rl/harness/approve.py                                  # every family: approved, or what changed
    python rl/harness/approve.py --family kpi_nowcast --show      # the diff since the approved commit
    python rl/harness/approve.py --family kpi_nowcast --approve --by "Mayank Mahajan" --note "judge.md C6 reworded"

Approving writes families/<family>/approval.yaml; commit it.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import instrument  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", choices=instrument.families())
    ap.add_argument("--show", action="store_true", help="print what changed since the approved commit")
    ap.add_argument("--approve", action="store_true", help="approve the current instrument")
    ap.add_argument("--by", help="who approves (required with --approve)")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    if (a.show or a.approve) and not a.family:
        ap.error("--show and --approve need --family")
    if a.approve:
        if not a.by:
            ap.error("--approve needs --by")
        e = instrument.approve(a.family, a.by, a.note)
        print(f"{a.family}: approved {e['sha256'][:12]} ({len(e['files'])} files) at {e['commit'][:12]}; "
              f"commit families/{a.family}/approval.yaml")
    elif a.show:
        print(instrument.status(a.family)[1])
        print(instrument.diff(a.family))
    else:
        for f in [a.family] if a.family else instrument.families():
            ok, why = instrument.status(f)
            print(f"{'ok  ' if ok else 'OPEN'} {why}")


if __name__ == "__main__":
    main()
