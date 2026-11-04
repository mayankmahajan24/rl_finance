"""Per-trap credit (rl/harness/ablation.py): on a planted bench task of each generated family, dropping
any one planted item from a gold-derived answer lowers the reward, so the verifier credits every one."""

from __future__ import annotations

import json

import pytest

import ablation
from conftest import built


@pytest.mark.slow
@pytest.mark.parametrize("family, task", [("data_audit", "audit-bench-001"), ("anomaly_scoring", "anomaly-bench-001"),
                                          ("growth_thesis", "thesis-bench-001")])
def test_every_planted_item_counts(family, task):
    d = built("bench", task)
    truth = json.loads((d / "tests" / "gold.json").read_text())
    assert ablation.CREDIT[family](d, truth) == []
