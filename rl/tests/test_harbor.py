"""The shared Harbor writer: layout, checksums, content hash, pinned environment."""

from __future__ import annotations

import gzip
import re

import pytest

import lib
from families._shared import harbor
from splits import check

FAMILY = {"authors": [{"name": "Test", "email": "t@example.com"}], "version": "1.0.0"}


def write(dest, **over):
    kw = dict(family=FAMILY, builder="rl/tests", instruction="Do the work.\n",
              metadata={"id": dest.name, "family": "test", "source": "txn_panel", "split": "bench"},
              description="test task", keywords=["test"], verifier="verify.py",
              tests={"verify.py": "print('ok')\n", "gold.json": "{}"},
              data={"a.csv": "x\n1\n"}, solution={"solve.sh": "true\n"})
    kw.update(over)
    return harbor.write(dest, **kw)


def test_layout(tmp_path):
    d = tmp_path / "t1"
    write(d)
    for f in ("instruction.md", "task.toml", "environment/Dockerfile", "environment/data/a.csv", "tests/test.sh",
              "tests/common.py", "tests/verify.py", "tests/gold.json", "solution/solve.sh", "checksums.sha256"):
        assert (d / f).is_file(), f
    assert (d / "tests" / "test.sh").stat().st_mode & 0o111
    assert "python /tests/verify.py" in (d / "tests" / "test.sh").read_text()
    assert not (d / "prompt").exists()


def test_checksums_cover_every_file(tmp_path):
    d = tmp_path / "t1"
    write(d, prompt={"system.md": "sys"})
    assert check.checksum_problems(d) == []
    (d / "environment" / "data" / "a.csv").write_text("x\n2\n")
    assert check.checksum_problems(d) == ["t1: environment/data/a.csv does not match its checksum"]


def test_build_record(tmp_path):
    d = tmp_path / "t1"
    write(d)
    b = lib.task_meta(d)["build"]
    assert b["builder"] == "rl/tests" and b["source"] == "txn_panel" and b["base_image"] == harbor.BASE_IMAGE
    assert re.fullmatch(r"[0-9a-f]{40}", b["repo_commit"])
    assert set(b["packages"]) == set(harbor.BUILD_PACKAGES)


def test_content_hash_ignores_only_the_build_record(tmp_path):
    a = write(tmp_path / "t1")
    assert write(tmp_path / "t1") == a                              # rebuilt later: new built_at, same hash
    assert write(tmp_path / "t1", data={"a.csv": "x\n2\n"}) != a      # data changed
    assert write(tmp_path / "t1", instruction="Other.\n") != a
    assert write(tmp_path / "t1", tests={"verify.py": "print(1)\n", "gold.json": "{}"}) != a
    assert write(tmp_path / "t1", metadata={"id": "t1", "family": "test", "source": "txn_panel",
                                            "split": "train"}) != a


def test_rewrite_removes_stale_files(tmp_path):
    d = tmp_path / "t1"
    write(d, data={"a.csv": "1", "b.csv": "2"})
    write(d)
    assert not (d / "environment" / "data" / "b.csv").exists()
    assert check.checksum_problems(d) == []


@pytest.mark.parametrize("gz", [False, True])
def test_gz_data_is_unpacked_in_the_image(tmp_path, gz):
    d = tmp_path / "t1"
    write(d, data={"a.csv.gz": gzip.compress(b"x\n1\n")} if gz else {"a.csv": "x\n1\n"})
    assert ("RUN gunzip /app/data/*.gz" in (d / "environment" / "Dockerfile").read_text()) == gz


def test_verifier_packages_stay_out_of_the_agent_image(tmp_path):
    d = tmp_path / "t1"
    write(d, test_pip=harbor.JUDGE_PIP)
    assert harbor.JUDGE_PIP in (d / "tests" / "test.sh").read_text()
    assert "anthropic" not in (d / "environment" / "Dockerfile").read_text()


def test_environment_is_pinned():
    assert re.fullmatch(r"python:[\w.-]+@sha256:[0-9a-f]{64}", harbor.BASE_IMAGE)
    pkgs = re.search(r"pip install --no-cache-dir (.*?)\{extra\}", harbor.DOCKERFILE).group(1).split()
    assert pkgs and all(re.fullmatch(r"[\w-]+==[\w.]+", p) for p in pkgs), pkgs
    assert re.fullmatch(r"[\w-]+==[\w.]+", harbor.JUDGE_PIP)


@pytest.mark.parametrize("judged", [False, True])
def test_every_phase_has_an_explicit_network_policy(tmp_path, judged):
    import tomllib
    d = tmp_path / "t1"
    write(d, test_pip=harbor.JUDGE_PIP if judged else "")
    cfg = tomllib.loads((d / "task.toml").read_text())
    assert cfg["agent"]["network_mode"] == cfg["environment"]["network_mode"] == "no-network"
    hosts = harbor.VERIFIER_HOSTS if judged else []
    assert cfg["verifier"]["network_mode"] == ("allowlist" if judged else "no-network")
    assert cfg["verifier"].get("allowed_hosts", []) == hosts
    assert cfg["metadata"]["environment"] == {"internet": False, "verifier_hosts": hosts}
    assert check.sandbox_problems(d, cfg["metadata"]) == []


def test_as_of_pins_the_clock_for_the_agent_only(tmp_path):
    d = tmp_path / "t1"
    write(d, metadata={"id": "t1", "family": "test", "source": "txn_panel", "split": "bench", "as_of": "2018-06-30"})
    docker = (d / "environment" / "Dockerfile").read_text()
    assert 'FAKETIME="@2018-06-30 12:00:00"' in docker and "TASK_AS_OF=2018-06-30 " in docker
    assert re.search(r"libfaketime=[\w.+~-]+ ", docker)                 # pinned apt package
    assert "FAKETIME_ONLY_CMDS=python,python3,python3.12,date " in docker  # the agent's own process keeps real time
    assert "unset LD_PRELOAD FAKETIME" in (d / "tests" / "test.sh").read_text()
    write(d)
    assert "FAKETIME" not in (d / "environment" / "Dockerfile").read_text()
