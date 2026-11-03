"""The research_design case-study baselines still reproduce: fingerprints and GRADED.md numbers."""

import subprocess
import sys

from conftest import RL


def test_replay():
    r = subprocess.run([sys.executable, str(RL / "families" / "research_design" / "replay.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "All fingerprints and GRADED.md numbers reproduced." in r.stdout
