"""Split assignments: which companies and which seeds belong to train, bench and heldout.

A split is decided per source by company (the `company_split` file its source.yaml names) and, for generated families, by
seed (splits/seeds.yaml; held-out seeds in splits/secrets/). Builders ask this module rather than
reading the files, so the rules live in one place, and record what they built in
splits/manifests/<family>.json. splits/check.py verifies built tasks obey the rules.

Besides the three splits, a task folder can be `eval` (a source with no split assignment yet:
research_design_case, whose tasks are all one eval set until whole worlds can be held out) or
`retired` (a case listed under `retired:` in its source's split file).
"""

from __future__ import annotations

import json
import pathlib
import random

import yaml

import lib

HERE = pathlib.Path(__file__).resolve().parent
SPLITS = ("train", "bench", "heldout")
UNSPLIT, RETIRED = "eval", "retired"
NEVER = {"heldout", RETIRED}        # never exported
SECRETS = HERE / "secrets"
MANIFESTS = HERE / "manifests"


def split_sources() -> list[str]:
    """Sources whose companies are assigned to splits (source.yaml `company_split`)."""
    return [s for s in lib.sources() if lib.source(s).get("company_split")]


def assignment(source: str) -> dict:
    f = lib.source(source).get("company_split")
    if not f:
        raise SystemExit(f"source {source} has no company_split in its source.yaml")
    return yaml.safe_load((lib.SOURCES / source / f).read_text())


def companies(source: str, split: str) -> list[str]:
    return list(assignment(source)["companies"][split])


def split_of(source: str, company: str) -> str:
    for split, names in assignment(source)["companies"].items():
        if company in names:
            return split
    raise KeyError(f"{company} has no split in splits/{source}.yaml")


def retired(source: str, family: str) -> dict[str, str]:
    """{case: reason} for cases removed from every split (built with split "retired")."""
    return dict(assignment(source).get("retired", {}).get(family, {}))


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
        if any(v["split"] == "heldout" for v in manifest(family).values()):
            raise SystemExit(f"{family}: the manifest lists held-out tasks but {path.relative_to(HERE.parent)} has no "
                             "seeds for it. Restore that file from your backup; drawing new seeds would replace "
                             "the held-out set.")
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
    """[(seed, is_control)] for one family in one split. Only train takes `n`/`controls` (it has no
    configured size); bench and held-out are fixed sets."""
    if split != "train" and (n, controls) != (None, None):
        raise ValueError(f"{split} is a fixed set: n and controls apply to train only")
    if split == "train" and n is None:
        raise ValueError("train: pass n (how many seeds to build)")
    if split == "heldout":
        h = _draw_heldout(family)
        return [(s, False) for s in h["seeds"]] + [(s, True) for s in h["controls"]]
    c = _seed_config()[split]
    if split == "bench":
        n, controls = c["seeds_per_family"], c["controls_per_family"]
    return ([(c["seed_start"] + i, False) for i in range(n)]
            + [(c["control_start"] + i, True) for i in range(controls or 0)])


def manifest(family: str) -> dict[str, dict]:
    p = MANIFESTS / f"{family}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def write_manifest(family: str, built: dict[str, dict], splits_rebuilt=None) -> pathlib.Path:
    """Record the tasks a build wrote. Entries of the rebuilt splits (default: all) are replaced.
    Held-out entries never carry a seed: the manifest is committed, the seeds are secret."""
    old = manifest(family)
    keep = {k: v for k, v in old.items() if splits_rebuilt is not None and v["split"] not in splits_rebuilt}
    for v in built.values():
        if v["split"] == "heldout":
            v.pop("seed", None)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    p = MANIFESTS / f"{family}.json"
    p.write_text(json.dumps(dict(sorted({**keep, **built}.items())), indent=1) + "\n")
    return p
