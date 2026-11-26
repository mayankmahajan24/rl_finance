"""The shared Harbor writer: layout, checksums, content hash, pinned environment."""

from __future__ import annotations

import gzip
import re

import pytest

import lib
from families._shared import harbor
from splits import check

FAMILY = {"authors": [{"name": "Test", "email": "t@example.com"}], "version": "1.0.0", "verifier_timeout_sec": 600,
          "gold_file": "gold.json", "judge": {"model": "m", "effort": None, "votes": 1, "max_tokens": 100}}


def meta(name, **over):
    return {"id": name, "family": "test", "source": "txn_panel", "split": "bench", "case": name, "fingerprint": "f",
            **over}


def write(dest, **over):
    kw = dict(family=FAMILY, builder="rl/tests", instruction="Do the work.\n", metadata=meta(dest.name),
              description="test task", keywords=["test"], verifier="verify.py",
              tests={"verify.py": "print('ok')\n"}, gold="{}", data={"a.csv": "x\n1\n"},
              solution={"solve.sh": "true\n"})
    kw.update(over)
    return harbor.write(dest, **kw)["content_sha256"]


def test_layout(tmp_path):
    d = tmp_path / "t1"
    write(d)
    for f in ("instruction.md", "task.toml", "environment/Dockerfile", "environment/data/a.csv", "tests/test.sh",
              "tests/common.py", "tests/verify.py", "tests/gold.json", "solution/solve.sh", "checksums.sha256"):
        assert (d / f).is_file(), f
    assert (d / "tests" / "test.sh").stat().st_mode & 0o111
    assert "python /tests/verify.py\n" in (d / "tests" / "test.sh").read_text()   # a crash is an error, never a 0
    assert not (d / "prompt").exists()


def test_manifest_entry(tmp_path):
    e = harbor.write(tmp_path / "t1", family=FAMILY, builder="rl/tests", instruction="x", description="d",
                     keywords=[], verifier="verify.py", tests={}, gold="{}",
                     metadata=meta("t1", role="r", seed=3, other="not recorded"))
    assert set(e) == {"split", "case", "role", "seed", "fingerprint", "gold_fingerprint", "content_sha256"}
    assert e["fingerprint"] == "f" and e["gold_fingerprint"] == lib.fingerprint("{}")


def test_authors_carry_no_email(tmp_path):
    write(tmp_path / "t1")
    assert "@" not in (tmp_path / "t1" / "task.toml").read_text().split("[metadata]")[0]


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
    assert write(tmp_path / "t1", tests={"verify.py": "print(1)\n"}) != a
    assert write(tmp_path / "t1", gold='{"a": 1}') != a
    assert write(tmp_path / "t1", metadata=meta("t1", split="train")) != a


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


def test_judged_task_ships_the_judge(tmp_path):
    d = tmp_path / "t1"
    write(d, judged=True)
    assert harbor.JUDGE_PIP in (d / "tests" / "test.sh").read_text()
    assert "anthropic" not in (d / "environment" / "Dockerfile").read_text()   # verifier-only package
    assert (d / "tests" / "judge.py").exists() and (d / "tests" / "client.py").exists() and '"model": "m"' in (d / "tests" / "judge.json").read_text()
    assert "ANTHROPIC_API_KEY" in (d / "task.toml").read_text()
    write(d)
    assert not (d / "tests" / "judge.py").exists() and "ANTHROPIC_API_KEY" not in (d / "task.toml").read_text()


def test_environment_is_pinned():
    assert re.fullmatch(r"python:[\w.-]+@sha256:[0-9a-f]{64}", harbor.BASE_IMAGE)
    pkgs = re.search(r"pip install --no-cache-dir (.*?)\{extra\}", harbor.DOCKERFILE).group(1).split()
    assert pkgs and all(re.fullmatch(r"[\w-]+==[\w.]+", p) for p in pkgs), pkgs
    assert re.fullmatch(r"[\w-]+==[\w.]+", harbor.JUDGE_PIP)


@pytest.mark.parametrize("judged", [False, True])
def test_every_phase_has_an_explicit_network_policy(tmp_path, monkeypatch, judged):
    import tomllib
    monkeypatch.setattr(lib, "family", lambda family_id: FAMILY)     # the check reads `dated` from family.yaml
    d = tmp_path / "t1"
    write(d, judged=judged)
    cfg = tomllib.loads((d / "task.toml").read_text())
    assert cfg["agent"]["network_mode"] == cfg["environment"]["network_mode"] == "no-network"
    hosts = harbor.VERIFIER_HOSTS if judged else []
    assert cfg["verifier"]["network_mode"] == ("allowlist" if judged else "no-network")
    assert cfg["verifier"].get("allowed_hosts", []) == hosts
    assert cfg["metadata"]["environment"] == {"internet": False, "verifier_hosts": hosts}
    assert check.sandbox_problems(d, cfg["metadata"]) == []


def test_as_of_pins_the_clock_for_the_agent_only(tmp_path):
    d = tmp_path / "t1"
    write(d, metadata=meta("t1", as_of="2018-06-30"))
    docker = (d / "environment" / "Dockerfile").read_text()
    assert 'FAKETIME="@2018-06-30 12:00:00"' in docker and "TASK_AS_OF=2018-06-30 " in docker
    assert re.search(r"libfaketime=[\w.+~-]+ ", docker)                 # pinned apt package
    assert "FAKETIME_ONLY_CMDS=python,python3,python3.14,date " in docker
    assert "ENV LD_PRELOAD" not in docker and " LD_PRELOAD=/" not in docker  # the agent's own process never loads it
    assert "unset LD_PRELOAD FAKETIME" in (d / "tests" / "test.sh").read_text()
    write(d)
    assert "FAKETIME" not in (d / "environment" / "Dockerfile").read_text()


def test_render():
    assert harbor.render('{"a": 1} {x} {x}', x=2) == '{"a": 1} 2 2'     # JSON needs no escaping
    assert harbor.render("{x}", x="{y}") == "{y}"                         # one pass: values are not re-read
    with pytest.raises(AssertionError):
        harbor.render("{x} {y}", x=1)
