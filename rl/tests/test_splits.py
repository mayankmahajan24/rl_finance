"""Split rules: seed ranges, held-out seed secrecy and the redraw guard, manifest writing, task ids."""

from __future__ import annotations

import shutil

import pytest
import yaml

import splits
from families._shared import build_panel
from sources.txn_panel import panel

CFG = yaml.safe_load((splits.HERE / "seeds.yaml").read_text())


def test_every_company_in_exactly_one_split():
    a = splits.assignment("txn_panel")["companies"]
    names = [n for split in splits.SPLITS for n in a[split]]
    assert len(names) == len(set(names))
    assert set(names) == set(panel.companies())
    for split in splits.SPLITS:
        for n in a[split]:
            assert splits.split_of("txn_panel", n) == split


def test_bench_seeds_come_from_config():
    got = splits.seeds("data_audit", "bench")
    c = CFG["bench"]
    assert [s for s, ctl in got if not ctl] == list(range(c["seed_start"], c["seed_start"] + c["seeds_per_family"]))
    assert [s for s, ctl in got if ctl] == list(range(c["control_start"],
                                                       c["control_start"] + c["controls_per_family"]))


def test_train_needs_a_count():
    with pytest.raises(ValueError):
        splits.seeds("data_audit", "train")
    got = splits.seeds("data_audit", "train", n=3, controls=2)
    assert [ctl for _, ctl in got] == [False] * 3 + [True] * 2
    assert all(CFG["retired_below"] <= s < CFG["bench"]["seed_start"] for s, _ in got)


def test_fixed_sets_refuse_a_count():
    for split in ("bench", "heldout"):
        with pytest.raises(ValueError, match=f"{split} is a fixed set: n and controls apply to train only"):
            splits.seeds("data_audit", split, n=3)


def test_task_ids_never_contain_the_seed():
    for split, seed, ctl, i in (("heldout", 123456789, False, 1), ("heldout", 987654321, True, 2),
                                ("bench", 200000, False, 1)):
        tid = build_panel.task_id("audit", split, seed, ctl, i)
        assert str(seed) not in tid
    assert build_panel.task_id("audit", "heldout", 123456789, False, 7) == "audit-heldout-007"
    assert build_panel.task_id("audit", "bench", 1, True, 2) == "audit-bench-control-02"


def test_write_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(splits, "MANIFESTS", tmp_path)
    e = lambda split, seed: {"split": split, "seed": seed, "fingerprint": "f", "gold_fingerprint": "g"}  # noqa: E731
    splits.write_manifest("fam", {"a-train-1": e("train", 1), "a-bench-1": e("bench", 2)})
    splits.write_manifest("fam", {"a-heldout-001": e("heldout", 123456789)}, splits_rebuilt={"heldout"})
    m = splits.manifest("fam")
    assert set(m) == {"a-train-1", "a-bench-1", "a-heldout-001"}        # other splits kept
    assert "seed" not in m["a-heldout-001"]                               # held-out seeds never committed
    splits.write_manifest("fam", {"a-bench-2": e("bench", 3)}, splits_rebuilt={"bench"})
    assert set(splits.manifest("fam")) == {"a-train-1", "a-bench-2", "a-heldout-001"}   # rebuilt split replaced


@pytest.fixture
def fake_here(tmp_path, monkeypatch):
    """splits.HERE pointed at a copy of the real config, so a held-out draw can't touch the real secrets."""
    shutil.copy(splits.HERE / "seeds.yaml", tmp_path / "seeds.yaml")
    monkeypatch.setattr(splits, "HERE", tmp_path)
    return tmp_path


def test_heldout_draw(fake_here, monkeypatch):
    monkeypatch.setattr(splits, "manifest", lambda family: {})
    h = splits.seeds("data_audit", "heldout")
    cfg = CFG["heldout"]
    assert sum(not c for _, c in h) == cfg["seeds_per_family"] and sum(c for _, c in h) == cfg["controls_per_family"]
    assert all(10**8 <= s < 10**9 for s, _ in h)                         # above every train/bench seed
    assert (fake_here / cfg["file"]).exists()
    assert splits.seeds("data_audit", "heldout") == h                    # drawn once, then reused
    other = {s for s, _ in splits.seeds("growth_thesis", "heldout")}
    assert not other & {s for s, _ in h}


def test_heldout_seeds_are_never_redrawn(fake_here, monkeypatch):
    monkeypatch.setattr(splits, "manifest", lambda family: {"audit-heldout-001": {"split": "heldout"}})
    with pytest.raises(SystemExit, match="Restore that file"):
        splits.seeds("data_audit", "heldout")
    assert not (fake_here / CFG["heldout"]["file"]).exists()


def test_committed_manifests_carry_no_heldout_seeds():
    for p in splits.MANIFESTS.glob("*.json"):
        for tid, v in splits.manifest(p.stem).items():
            assert not (v["split"] == "heldout" and "seed" in v), f"{p.name}: {tid}"
