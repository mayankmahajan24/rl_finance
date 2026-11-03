"""Split assignments: which companies and which seeds belong to train, bench and heldout.

A split is decided per source by company (splits/<source>.yaml) and, for generated families, by
seed (splits/seeds.yaml; held-out seeds in splits/secrets/). Builders ask this module rather than
reading the files, so the rules live in one place. splits/check.py verifies built tasks obey them.
"""

from __future__ import annotations

import pathlib
import random

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SPLITS = ("train", "bench", "heldout")
SECRETS = HERE / "secrets"


def assignment(source: str) -> dict:
    return yaml.safe_load((HERE / f"{source}.yaml").read_text())


def companies(source: str, split: str) -> list[str]:
    if split == "pilot":
        raise ValueError("the pilot split uses every company; ask the source for its company list")
    return list(assignment(source)["companies"][split])


def split_of(source: str, company: str) -> str:
    for split, names in assignment(source)["companies"].items():
        if company in names:
            return split
    raise KeyError(f"{company} has no split in splits/{source}.yaml")


def _seed_config() -> dict:
    return yaml.safe_load((HERE / "seeds.yaml").read_text())


def heldout_seeds() -> dict[str, dict[str, list[int]]]:
    """{family: {"seeds": [...], "controls": [...]}}, created at random on first use."""
    path = HERE / _seed_config()["heldout"]["file"]
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def _draw_heldout(family: str) -> dict[str, list[int]]:
    cfg = _seed_config()["heldout"]
    path = HERE / cfg["file"]
    allv = heldout_seeds()
    if family not in allv:
        rng = random.SystemRandom()
        used = {s for f in allv.values() for v in f.values() for s in v}
        draw = set()
        while len(draw) < cfg["seeds_per_family"] + cfg["controls_per_family"]:
            s = rng.randrange(10**8, 10**9)
            if s not in used:
                draw.add(s)
        draw = sorted(draw)
        allv[family] = {"seeds": draw[:cfg["seeds_per_family"]], "controls": draw[cfg["seeds_per_family"]:]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Secret held-out seeds. Gitignored; back up outside the repo.\n"
                        + yaml.safe_dump(allv, sort_keys=True))
    return allv[family]


def seeds(family: str, split: str, n: int | None = None, controls: int | None = None) -> list[tuple[int, bool]]:
    """[(seed, is_control)] for one family in one split. `n`/`controls` override the configured
    counts (train has none configured; it takes whatever the caller asks for)."""
    cfg = _seed_config()
    if split == "pilot":
        return [(s, False) for s in cfg["pilot"]["seeds"]] + [(s, True) for s in cfg["pilot"]["controls"]]
    if split == "heldout":
        h = _draw_heldout(family)
        ss, cc = h["seeds"], h["controls"]
        return [(s, False) for s in ss[:n]] + [(s, True) for s in cc[:controls]]
    c = cfg[split]
    n = c.get("seeds_per_family") if n is None else n
    controls = c.get("controls_per_family", 0) if controls is None else controls
    if n is None:
        raise ValueError(f"{split}: pass n (how many seeds to build)")
    return ([(c["seed_start"] + i, False) for i in range(n)]
            + [(c["control_start"] + i, True) for i in range(controls)])
