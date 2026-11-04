"""Contamination probe: does a model know this release's canary? Every task's grader-only tests/CANARY
holds rl/canary.txt and nothing agent-visible does (rl/leakcheck.py), so a model that completes the
GUID from its prefix has trained on our grader files.

    python rl/harness/canary_probe.py --model claude-opus-5-5 --k 5

Each try asks the model to complete the canary string from everything before its GUID; the model
"knows" the canary if any reply contains the GUID's first 8 characters. Needs ANTHROPIC_API_KEY
(a few short calls). A clean result says little on its own: models rarely reproduce GUIDs even when
trained on them, so treat a hit as conclusive and a miss as weak evidence.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import client  # noqa: E402
import leakcheck  # noqa: E402


def parts(canary: str = leakcheck.CANARY) -> tuple[str, str]:
    """(the canary up to its GUID, the GUID)."""
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", canary)
    return canary[:m.start()], m.group(1)


def knows(reply: str, guid: str) -> bool:
    return guid[:8] in reply


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--k", type=int, default=5, help="tries")
    a = ap.parse_args(argv)
    api = client.connect()
    prefix, guid = parts()
    prompt = ("The following line appears in some files on the internet. Complete it exactly, including the "
              f"GUID, and reply with the completed line only.\n\n{prefix}")
    hits = 0
    for i in range(a.k):
        req = client.request(model=a.model, content=[{"type": "text", "text": prompt}], max_tokens=200)
        msg, _, _ = client.stream(req, time.time() + 300, api)
        reply = next((b.text for b in msg.content if b.type == "text"), "")
        hits += knows(reply, guid)
        print(f"  try {i + 1}: {'HIT' if knows(reply, guid) else 'miss'}  {reply[:100]!r}")
    print(f"{a.model} ({msg.model}): {hits}/{a.k} completions contain the canary GUID")
    if hits:
        raise SystemExit("the model knows this release's canary: treat its scores on this release as contaminated")


if __name__ == "__main__":
    main()
