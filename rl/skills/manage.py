"""Fetch, validate and upload the financial-services Agent Skills.

    python rl/skills/manage.py fetch     # check out the pinned commit into rl/vendor/
    python rl/skills/manage.py check     # validate every profile against API limits
    python rl/skills/manage.py sync      # upload new/changed skills, pin versions in lock.json
    python rl/skills/manage.py status    # show what is pinned and whether it is stale

`sync` writes to the Anthropic workspace of the active API key: it creates one
custom skill per profile entry, or a new version when the local content changed.
Unchanged skills are skipped, so re-running it is safe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
RL = HERE.parent
CONFIG = HERE / "config.yaml"
LOCK = HERE / "lock.json"
VENDOR = RL / "vendor" / "financial-services"

MAX_SKILLS_PER_REQUEST = 20
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def lock() -> dict:
    return json.loads(LOCK.read_text()) if LOCK.exists() else {"skills": {}}


def skill_dir(ref: str) -> pathlib.Path:
    """`equity-research/earnings-analysis` -> the vertical-plugin source folder."""
    vertical, name = ref.split("/")
    return VENDOR / "plugins" / "vertical-plugins" / vertical / "skills" / name


def frontmatter(d: pathlib.Path) -> dict:
    m = re.match(r"^---\n(.*?)\n---", (d / "SKILL.md").read_text(), re.S)
    return yaml.safe_load(m.group(1)) if m else {}


def content_hash(d: pathlib.Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        h.update(str(f.relative_to(d)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def vendored_commit() -> str | None:
    if not (VENDOR / ".git").exists():
        return None
    return subprocess.run(["git", "-C", str(VENDOR), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


# ---- commands ---------------------------------------------------------------

def fetch(cfg: dict) -> None:
    src = cfg["source"]
    if not VENDOR.exists():
        subprocess.run(["git", "clone", "-q", src["repo"], str(VENDOR)], check=True)
    subprocess.run(["git", "-C", str(VENDOR), "fetch", "-q", "origin"], check=True)
    subprocess.run(["git", "-C", str(VENDOR), "checkout", "-q", src["commit"]], check=True)
    print(f"{VENDOR.relative_to(RL.parent)} at {src['commit'][:12]}")


def check(cfg: dict) -> list[str]:
    problems = []
    if vendored_commit() != cfg["source"]["commit"]:
        problems.append(f"vendor checkout is {vendored_commit()}, config pins "
                        f"{cfg['source']['commit']} — run `fetch`")
        return problems

    all_names = {p.parent.name for p in (VENDOR / "plugins").glob("*/*/skills/*/SKILL.md")}
    accounted = {r.split("/")[1] for refs in cfg["profiles"].values() for r in refs}
    accounted |= {n for names in cfg["excluded"].values() for n in names}
    if all_names - accounted:
        problems.append(f"skills in the repo that no profile or exclusion mentions: "
                        f"{sorted(all_names - accounted)}")

    for profile, refs in cfg["profiles"].items():
        if len(refs) > MAX_SKILLS_PER_REQUEST:
            problems.append(f"profile {profile}: {len(refs)} skills > {MAX_SKILLS_PER_REQUEST} per request")
        for ref in refs:
            d = skill_dir(ref)
            if not (d / "SKILL.md").exists():
                problems.append(f"{ref}: no SKILL.md at {d}")
                continue
            fm = frontmatter(d)
            name, desc = fm.get("name", ""), fm.get("description", "")
            if not NAME_RE.match(name) or any(w in name for w in ("anthropic", "claude")):
                problems.append(f"{ref}: invalid skill name {name!r}")
            if name != d.name:
                problems.append(f"{ref}: frontmatter name {name!r} != folder {d.name!r}")
            if not desc or len(desc) > 1024 or "<" in desc:
                problems.append(f"{ref}: description must be 1-1024 chars with no XML tags")
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            if size > MAX_UPLOAD_BYTES:
                problems.append(f"{ref}: {size} bytes > 30 MB upload limit")
    return problems


def _skills_api(client):
    # SDK >= 1.x exposes client.skills; older releases only client.beta.skills.
    return getattr(client, "skills", None) or client.beta.skills


def _version_ref(obj) -> str:
    """The version string a Messages request accepts, across SDK response shapes."""
    for attr in ("latest_version_id", "id", "latest_version", "version"):
        v = getattr(obj, attr, None)
        if isinstance(v, str) and v.startswith(("skver_", "skill_version_")):
            return v
    return getattr(obj, "latest_version", None) or getattr(obj, "version")


def sync(cfg: dict) -> None:
    problems = check(cfg)
    if problems:
        raise SystemExit("check failed:\n  " + "\n  ".join(problems))
    import anthropic
    from anthropic.lib import files_from_dir

    api = _skills_api(anthropic.Anthropic())
    state = lock()
    state["source"] = cfg["source"]
    refs = sorted({r for refs in cfg["profiles"].values() for r in refs})
    for ref in refs:
        d = skill_dir(ref)
        h = content_hash(d)
        entry = state["skills"].get(ref)
        if entry and entry["content_hash"] == h:
            print(f"  unchanged  {ref}")
            continue
        if entry:
            v = api.versions.create(skill_id=entry["skill_id"], files=files_from_dir(str(d)))
            entry.update(version=_version_ref(v), content_hash=h)
            print(f"  new version {ref} -> {entry['version']}")
        else:
            s = api.create(files=files_from_dir(str(d)))
            state["skills"][ref] = {"name": d.name, "skill_id": s.id,
                                    "version": _version_ref(s), "content_hash": h}
            print(f"  created    {ref} -> {s.id}")
        LOCK.write_text(json.dumps(state, indent=2) + "\n")   # after each, so a crash loses nothing
    LOCK.write_text(json.dumps(state, indent=2) + "\n")
    print(f"lock: {LOCK.relative_to(RL.parent)}")


def status(cfg: dict) -> None:
    state = lock()
    print(f"config pins {cfg['source']['commit'][:12]}; vendor at {(vendored_commit() or 'missing')[:12]}; "
          f"lock built from {state.get('source', {}).get('commit', 'nothing')[:12]}")
    print(f"default for Anthropic models: {cfg['default_for_anthropic']}")
    for profile, refs in cfg["profiles"].items():
        print(f"\n{profile} ({len(refs)} skills)")
        for ref in refs:
            e = state["skills"].get(ref)
            stale = e and VENDOR.exists() and e["content_hash"] != content_hash(skill_dir(ref))
            print(f"  {ref:<40} {('NOT UPLOADED' if not e else e['version'] + (' STALE' if stale else ''))}")


def resolve(profile: str) -> list[dict]:
    """Container skill entries for a profile, pinned to the locked versions. Used by rl/harness/run_api.py."""
    cfg, state = config(), lock()
    refs = cfg["profiles"][profile]
    missing = [r for r in refs if r not in state["skills"]]
    if missing:
        raise SystemExit(f"skills not uploaded: {missing} — run `python rl/skills/manage.py sync`")
    return [{"type": "custom", "skill_id": state["skills"][r]["skill_id"],
             "version": state["skills"][r]["version"]} for r in refs]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["fetch", "check", "sync", "status"])
    args = ap.parse_args()
    cfg = config()
    if args.command == "fetch":
        fetch(cfg)
    elif args.command == "check":
        problems = check(cfg)
        print("\n".join(problems) if problems else "ok: every profile is within API limits")
        sys.exit(1 if problems else 0)
    elif args.command == "sync":
        sync(cfg)
    else:
        status(cfg)


if __name__ == "__main__":
    main()
