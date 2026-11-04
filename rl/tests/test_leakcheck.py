"""The shared leak check (rl/leakcheck.py): every kind of leak planted in a copy of a real built task is
caught, and the clean task passes. Plus the contamination and memorisation probes' scoring."""

from __future__ import annotations

import json
import shutil

import pytest

import canary_probe
import leakcheck
import lib
import memorisation
from conftest import built


@pytest.fixture
def task(tmp_path):
    def copy(split: str, tid: str):
        d = tmp_path / tid
        shutil.copytree(built(split, tid), d)
        return d, lib.task_meta(d)
    return copy


def plant(d, rel: str, text: str) -> None:
    f = d / rel
    f.write_text(f.read_text() + "\n" + text + "\n")


def test_clean_tasks_pass(task):
    for split, tid in (("eval", "rd-review-S1-A"), ("bench", "kn-produce-AIR02-2017Q4-anon"), ("bench", "audit-bench-001")):
        d, m = task(split, tid)
        assert leakcheck.task_problems(d, m) == [], tid


def test_gold_text_and_numbers(task):
    d, m = task("eval", "rd-review-S1-A")
    issue = json.loads((d / "tests" / "gold.json").read_text())["issues"][0]["text"]
    plant(d, "instruction.md", issue)
    assert any("gold text visible in instruction.md" in p for p in leakcheck.task_problems(d, m))

    d, m = task("bench", "kn-produce-AIR02-2017Q4-anon")
    actual = json.loads((d / "tests" / "gold.json").read_text())["actual"]
    plant(d, "prompt/user.md", f"Hint: about {actual:,.0f}.")
    assert any(p.startswith(f"{d.name}: gold value {actual:,.0f} visible in prompt/user.md")
               for p in leakcheck.task_problems(d, m))


def test_identity_and_allowlist(task):
    d, m = task("bench", "audit-bench-001")
    plant(d, "instruction.md", "Source: https://www.sec.gov/ for the rl_finance benchmark task.")
    p = leakcheck.task_problems(d, m)
    assert any("'https://'" in x for x in p) and any("'rl_finance'" in x for x in p)
    assert any("'benchmark task'" in x for x in p)
    d, m = task("bench", "kn-produce-AIR02-2017Q4-anon")
    brief = (d / "environment" / "data" / "data_brief.md").read_text()
    assert "Transaction sensor panel" in brief and "replaced with codes" in brief and "underscore" not in brief
    assert leakcheck.task_problems(d, m) == []


def test_disguise(task):
    d, m = task("bench", "kn-produce-AIR02-2017Q4-anon")
    real = leakcheck.real_names(m["source"], m["companies"])[0]
    plant(d, "prompt/user.md", f"(This is {real}.)")
    assert any(f"real name {real!r}" in x for x in leakcheck.task_problems(d, m))


def test_disguise_of_an_unknown_company_raises():
    with pytest.raises(SystemExit, match=r"txn_panel: unknown companies \['XYZ'\], not in its entities file"):
        leakcheck.real_names("txn_panel", ["DAL", "XYZ"])


def test_canary(task):
    d, m = task("bench", "audit-bench-001")
    assert leakcheck.CANARY in (d / "tests" / "CANARY").read_text()
    plant(d, "instruction.md", leakcheck.CANARY)
    (d / "tests" / "CANARY").unlink()
    p = leakcheck.task_problems(d, m)
    assert f"{d.name}: canary visible in instruction.md" in p
    assert f"{d.name}: tests/CANARY missing or not the current canary (rebuild)" in p


def test_canary_probe_scoring():
    prefix, guid = canary_probe.parts()
    assert leakcheck.CANARY == prefix + guid and canary_probe.knows(f"... {guid} ...", guid)
    assert not canary_probe.knows("canary GUID 00000000-0000", guid)


def test_memorisation_gap():
    rec = lambda task, err, attempt=0: {"status": "ok", "model": "m", "task_id": task, "attempt": attempt,  # noqa: E731
                                        "rewards": {"abs_pct_error": err, "covered": 1.0}}
    case_of = {"kn-UAL": ("UAL-2018Q4", "named"), "kn-AIR03-anon": ("UAL-2018Q4", "anon")}
    paired = memorisation.pairs([rec("kn-UAL", 0.5, 1), rec("kn-AIR03-anon", 0.05), rec("kn-UAL", 0.01)], case_of)
    assert paired["m"] == [({"abs_pct_error": 0.01, "covered": 1.0}, {"abs_pct_error": 0.05, "covered": 1.0})]
    g = memorisation.gaps(paired["m"])
    assert g["abs_pct_error"]["advantage"] == pytest.approx(0.04) and g["covered"]["advantage"] == 0
