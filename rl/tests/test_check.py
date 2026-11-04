"""splits/check.py: a clean built task passes, and every failure mode is caught. Each test copies a
real built task into a scratch tasks/ tree, breaks one thing, and runs the check over that tree."""

from __future__ import annotations

import hashlib
import pathlib
import shutil

import lib
from splits import check

TASK = "audit-bench-001"


def edit(d: pathlib.Path, rel: str, old: str, new: str, rehash: bool = True) -> None:
    """Change one file; with rehash, update checksums.sha256 too, so only the targeted check fails."""
    f = d / rel
    text = f.read_text()
    assert old in text, (rel, old)
    f.write_text(text.replace(old, new, 1))
    if rehash:
        sums = d / "checksums.sha256"
        lines = [ln for ln in sums.read_text().splitlines() if not ln.endswith(f"  {rel}")]
        sums.write_text("\n".join([*lines, f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {rel}"]) + "\n")


def problems(release: bool = False) -> list[str]:
    return check.check() + (check.release_problems(list(lib.iter_tasks())) if release else [])


def test_clean_task_passes(tree):
    tree()
    assert problems() == []


def test_tampered_file(tree):
    d = tree()
    (d / "environment" / "data" / "transactions.csv").write_text("date,ticker\n")
    assert f"{TASK}: environment/data/transactions.csv does not match its checksum" in problems()


def test_unlisted_and_missing_files(tree):
    d = tree()
    (d / "environment" / "data" / "extra.csv").write_text("x")
    (d / "solution" / "solve.sh").unlink()
    p = problems()
    assert f"{TASK}: environment/data/extra.csv not in checksums.sha256" in p
    assert f"{TASK}: solution/solve.sh listed but missing" in p


def test_grader_file_where_the_agent_can_see_it(tree):
    d = tree()
    shutil.copy(d / "tests" / "gold.json", d / "environment" / "data" / "gold.json")
    assert f"{TASK}: grader-only file under environment/" in problems()


def test_wrong_split_folder(tree):
    tree("train")
    assert f"{TASK}: metadata split bench but built under tasks/train" in problems()


def test_not_a_split_folder(tree):
    tree("pilot")
    assert f"{TASK}: built under tasks/pilot, which is not a split" in problems()


def test_same_task_in_two_splits(tree):
    tree()
    tree("train")
    assert any(p.startswith(f"{TASK}: built in both") for p in problems())


def test_heldout_task_with_a_seed(tree):
    d = tree("heldout")
    edit(d, "task.toml", 'split = "bench"', 'split = "heldout"')
    assert f"{TASK}: held-out task records its seed" in problems()


def test_seed_outside_its_range(tree):
    d = tree()
    edit(d, "task.toml", "seed = 200000", "seed = 100000")
    assert f"{TASK}: seed 100000 outside the bench range [200000, 100000000)" in problems()


def test_company_from_another_split(tree):
    d = tree()
    other = check.splits.companies("txn_panel", "heldout")[0]
    edit(d, "task.toml", 'companies = [ "', f'companies = [ "{other}", "')
    assert f"{TASK}: uses ['{other}'], not in bench" in problems()


def test_missing_build_record(tree):
    d = tree()
    toml = (d / "task.toml").read_text()
    start = toml.index("[metadata.build]")
    end = toml.index("[verifier]")
    edit(d, "task.toml", toml[start:end], "")
    assert f"{TASK}: no [metadata.build] record" in problems()


def test_content_differs_from_manifest(tree):
    d = tree()
    edit(d, "instruction.md", "issues.json", "answers.json")
    assert any(p.startswith(f"{TASK}: differs from splits/manifests/data_audit.json") for p in problems())


def test_task_not_in_manifest(tree):
    d = tree(name="audit-bench-999")
    edit(d, "task.toml", f'id = "{TASK}"', 'id = "audit-bench-999"')
    assert "audit-bench-999: not in splits/manifests/data_audit.json" in problems()


def test_release_rejects_dirty_builds(tree):
    d = tree()
    edit(d, "task.toml", "repo_dirty = false", "repo_dirty = true")
    assert problems() == []
    assert f"{TASK}: built with uncommitted changes to tracked files" in problems(release=True)


def test_release_rejects_mixed_commits(tree):
    tree()
    d = tree(task="audit-bench-002")
    commit = lib.task_meta(d)["build"]["repo_commit"]
    edit(d, "task.toml", commit, "0" * 40)
    assert problems() == []
    assert "tasks were built from 2 different commits; rebuild everything from one" in problems(release=True)


def test_agent_phase_with_network(tree):
    d = tree()
    edit(d, "task.toml", '[agent]\ntimeout_sec = 3600\nnetwork_mode = "no-network"',
         '[agent]\ntimeout_sec = 3600\nnetwork_mode = "public"')
    assert f"{TASK}: [agent] network_mode is 'public', not 'no-network'" in problems()


def test_policy_missing_between_phases(tree):
    d = tree()
    edit(d, "task.toml", '[environment]\nnetwork_mode = "no-network"', "[environment]")
    assert f"{TASK}: [environment] network_mode is None, not 'no-network'" in problems()


def test_verifier_policy_disagrees_with_metadata(tree):
    d = tree()
    edit(d, "task.toml", '[verifier]\ntimeout_sec = 600\nnetwork_mode = "no-network"',
         '[verifier]\ntimeout_sec = 600\nnetwork_mode = "public"')
    assert any(p.startswith(f"{TASK}: [verifier] network policy 'public'") for p in problems())


DATED = "kn-produce-AIR02-2017Q4-anon"


def test_dated_task_without_as_of(tree):
    d = tree(task=DATED)
    edit(d, "task.toml", 'as_of = "2017-12-31"\n', "")
    assert f"{DATED}: kpi_nowcast is dated but the task records no as_of" in problems()


def test_dated_task_with_the_real_clock(tree):
    d = tree(task=DATED)
    edit(d, "environment/Dockerfile", "TASK_AS_OF=2017-12-31 ", "TASK_AS_OF=2018-12-31 ")
    assert f"{DATED}: as_of 2017-12-31 but its image does not pin the clock to it" in problems()


def test_instruction_names_a_missing_file(tree):
    d = tree()
    edit(d, "instruction.md", "issues.json", "issues.json` from `/app/data/lookup.csv")
    assert f"{TASK}: instruction names /app/data/lookup.csv, which the image doesn't have" in problems()


def test_instruction_output_the_verifier_never_reads(tree):
    d = tree()
    edit(d, "instruction.md", "/app/output/issues.json", "/app/output/findings.json")
    assert f"{TASK}: instruction names /app/output/findings.json, which the verifier never reads" in problems()


def test_reference_reads_grader_files(tree):
    d = tree()
    edit(d, "solution/audit.py", "import json", "import json  # cheat: json.load(open('/tests/gold.json'))")
    assert f"{TASK}: solution/audit.py refers to grader-side files ('/tests')" in problems()


def test_reference_imports_what_the_image_lacks(tree):
    d = tree()
    edit(d, "solution/audit.py", "import json", "import json\nimport sklearn")
    assert f"{TASK}: solution/audit.py imports sklearn, which the agent's image doesn't install" in problems()
