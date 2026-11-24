"""Lab-ready audit: settle the mechanical items of references/checklist.md for one family and print
the whole checklist as a scorecard. Items this script can't settle are listed as MANUAL (read and
experiment), BLOCKED (needs Docker, API spend or a person: the command is given) or left for the
human decision they end in.

Nothing here spends money, calls a model, or writes to the repo: solvers and attacks are graded
offline in scratch folders (JUDGE=keyword, no API key), the way rl/harness/ does.

    python .claude/skills/lab-ready/scripts/audit.py --family data_audit                 # train, 2 tasks + 1 control
    python .claude/skills/lab-ready/scripts/audit.py --family kpi_nowcast --split bench --sample 4
    python .claude/skills/lab-ready/scripts/audit.py --family data_audit --static        # no built tasks needed
    python .claude/skills/lab-ready/scripts/audit.py --family data_audit --out report.md --json report.json

Exit code 1 when any item FAILs. Run with the repo's Python (requirements.txt installed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tomllib

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[4]
RL = ROOT / "rl"
CHECKLIST = HERE.parents[1] / "references" / "checklist.md"
for p in (RL, RL / "harness"):
    sys.path.insert(0, str(p))

PASS, FAIL, WARN, BLOCKED, MANUAL, NA = "PASS", "FAIL", "WARN", "BLOCKED", "MANUAL", "N/A"
GAP = 0.3                    # reference minus naive on planted tasks (tests/test_verifiers.py MARGIN)
BAND = (1 / 8, 3 / 8)        # the pass-rate band on-policy RL learns from
JUDGMENT_WORDS = ("appropriate", "appropriately", "adequate", "adequately", "reasonable", "reasonably", "sufficient",
                  "sufficiently", "thorough", "thoroughly", "clear", "clearly", "well", "proper", "properly",
                  "suitable", "sensible", "high-quality", "meaningful")
REQUIRED_KEYS = ("id", "version", "source", "builder", "verifier", "verifier_timeout_sec", "gold_file", "reward",
                 "gold_inputs", "instrument", "calibration", "leak_check")
STRAY = (".git", "__pycache__", ".ipynb_checkpoints", ".bash_history", ".python_history", ".cache", ".DS_Store")


class Card:
    """The checklist, with a status and evidence per item."""

    def __init__(self) -> None:
        text = CHECKLIST.read_text()
        self.items = {}
        section = ""
        for line in text.splitlines():
            if m := re.match(r"## ([A-K])\. (.+)", line):
                section = m.group(2)
            elif m := re.match(r"### ([A-K]\d+)\. (.+?)(?: \[(.+)\])?$", line):
                self.items[m.group(1)] = {"section": section, "title": m.group(2), "tag": m.group(3) or "",
                                          "status": None, "evidence": []}

    def set(self, item: str, status: str, evidence: str = "") -> None:
        """Record a result; the worst status given for an item wins, and evidence accumulates."""
        order = [None, NA, PASS, MANUAL, WARN, BLOCKED, FAIL]
        it = self.items[item]
        if order.index(status) > order.index(it["status"]):
            it["status"] = status
        if evidence:
            it["evidence"].append(evidence)

    def close(self) -> None:
        """Items nothing settled: a person's decision is BLOCKED on that person, the rest are MANUAL."""
        for it in self.items.values():
            human = it["tag"] == "human"
            if it["status"] is None and it["tag"] == "optional":
                it["status"], it["evidence"] = NA, ["optional: settle it if the budget allows, or leave it"]
            if it["status"] is None:
                it["status"] = BLOCKED if human else MANUAL
            if human and it["status"] != PASS:
                it["evidence"].append("a person's decision: prepare the evidence, do not record it yourself")

    def markdown(self, title: str) -> str:
        counts = {s: sum(i["status"] == s for i in self.items.values()) for s in (PASS, FAIL, WARN, BLOCKED, MANUAL, NA)}
        out = [f"# Lab-ready audit: {title}", "", " · ".join(f"{s} {n}" for s, n in counts.items() if n), ""]
        section = None
        for k, i in self.items.items():
            if i["section"] != section:
                section = i["section"]
                out += ["", f"## {k[0]}. {section}", "", "| | Item | Status | Evidence |", "|---|---|---|---|"]
            ev = "<br>".join(e.replace("|", "\\|").replace("\n", " ") for e in i["evidence"])
            out.append(f"| {k} | {i['title']} | **{i['status']}** | {ev} |")
        return "\n".join(out) + "\n"


def sh(*cmd: str, timeout: int = 3600) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"} | {"JUDGE": "keyword"}
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def tail(text: str, n: int = 6) -> str:
    return " / ".join(line.strip() for line in text.splitlines()[-n:] if line.strip())[:700]


def docker() -> bool:
    return bool(shutil.which("docker")) and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


# ---------- static: the family folder ----------

def static(card: Card, fam_id: str) -> dict:
    import instrument
    import lib
    import provenance

    fam, d = lib.family(fam_id), RL / "families" / fam_id
    prefix = fam.get("task_prefix", fam_id)
    missing = [k for k in REQUIRED_KEYS if k not in fam]
    card.set("A1", FAIL if missing else PASS, f"family.yaml lacks {missing}" if missing else "family.yaml complete")

    templates = [p for p in [d / "instruction.md", *sorted((d / "prompts").glob("*.md"))] if p.exists()]
    for t in templates:
        words = len(t.read_text().split())
        card.set("A2", WARN if words > 900 else MANUAL, f"{t.name}: {words} words" + ("; long for an instruction" if words > 900 else "") + "; read it for coaching")
    if not fam.get("rubric_visibility") and "judge" in fam:
        card.set("A3", WARN, "judged family with no rubric_visibility note in family.yaml")

    lc = fam.get("leak_check") or {}
    if not ({"gold_numbers", "gold_text"} & set(lc)):
        card.set("A4", WARN, "leak_check declares no gold_numbers/gold_text: confirm the gold really is structural")

    for solver, item in (("reference", "B1"), ("naive", "B4")):
        if not (d / "solutions" / solver / "solve.sh").exists():
            card.set(item, FAIL, f"no solutions/{solver}/solve.sh")

    import ablation
    import attacks
    card.set("E1", PASS if fam_id in attacks.FORMATS else FAIL,
             "adapter in attacks.FORMATS" if fam_id in attacks.FORMATS else "no adapter in harness/attacks.py: never attacked")
    if fam_id not in ablation.CREDIT:
        card.set("B6", WARN, "no hook in ablation.CREDIT: drop a gold item by hand and confirm the reward falls")

    workflow = (ROOT / ".github/workflows/sandbox.yml").read_text()
    in_probe = re.search(rf"tasks/\w+/{re.escape(prefix)}-", workflow)
    card.set("C2", BLOCKED, ("a task of the family is in sandbox.yml" if in_probe else "NO task of the family in "
             ".github/workflows/sandbox.yml: add one") + "; prove it: python rl/harness/sandbox_probe.py <task> (Docker)")
    if not in_probe:
        card.set("C2", FAIL)
    import oracle_check
    in_oracle = any(t.startswith(prefix + "-") for t in oracle_check.SAMPLE)
    card.set("B2", BLOCKED, ("in oracle_check.SAMPLE" if in_oracle else "not in oracle_check.SAMPLE: pass the tasks "
             "explicitly") + "; JUDGE=keyword python rl/harness/oracle_check.py [tasks] (Docker)")

    judged = "judge" in fam
    rubrics = [p for p in [d / "judge.md", *sorted((d / "graders").glob("*.md"))] if p.exists()]
    if not judged and not rubrics:
        for k in card.items:
            if k.startswith("F"):
                card.set(k, NA, "no model judge")
    else:
        j = fam.get("judge", {})
        pinned = all(k in j for k in ("model", "effort", "votes", "max_tokens"))
        card.set("F7", MANUAL if pinned else FAIL, f"judge: {j or 'not pinned in family.yaml'}; confirm it is not the model under test")
        if j.get("votes", 1) < 3:
            card.set("F9", WARN, f"votes = {j.get('votes', 1)}: a single vote hides unstable lines")
        card.set("F9", BLOCKED, "python rl/harness/judge_stability.py --k 3 <task>=<output_dir> (API key, saved answers)")
        card.set("F3", BLOCKED, "grade a never-read-the-record answer with the real judge (API key; cents per answer)")
        for r in rubrics:
            lines = [ln for ln in r.read_text().splitlines() if re.match(r"\s*(-|\d+\.|\|)\s*\*{0,2}[A-Z]{1,2}\d+", ln)]
            vague = [(ln.split(":")[0].strip("-| *"), sorted({w for w in JUDGMENT_WORDS if re.search(rf"\b{w}\b", ln.lower())}))
                     for ln in lines]
            vague = [(i, w) for i, w in vague if w]
            bundled = [ln.split(":")[0].strip("-| *") for ln in lines if len(re.findall(r"\band\b|;", ln)) >= 3]
            note = f"{r.name}: {len(lines)} lines"
            if vague:
                card.set("F1", WARN, f"{note}; judgment words in {len(vague)}: " + ", ".join(f"{i} ({'/'.join(w)})" for i, w in vague[:12]))
            if bundled:
                card.set("F1", WARN, f"{r.name}: possibly bundled (3+ 'and'/';'): {', '.join(bundled[:12])}")
            if not lines:
                card.set("F1", MANUAL, f"{r.name}: no itemised rubric lines found (not a line-per-check rubric): read it")
            elif not vague and not bundled:
                card.set("F1", MANUAL, f"{note}, lint clean; still read them")
            conditional = [ln.split(":")[0].strip("-| *") for ln in lines if re.search(r"\b(if applicable|where applicable|n/a if|na if)\b", ln.lower())]
            if conditional:
                card.set("F2", WARN, f"{r.name}: the judge decides applicability in {', '.join(conditional[:12])}")
        code = " ".join(p.read_text() for p in [*d.rglob("*.py"), RL / "families/_shared/writeup.py"] if p.is_file())
        binary = "'pass', 'fail'" in code or '"pass", "fail"' in code
        unknown = re.search(r"'(na|unknown)'|\"(na|unknown)\"", code)
        card.set("F6", PASS if binary and unknown else MANUAL,
                 "pass/fail verdicts with an na/unknown option" if binary and unknown else "could not find a pass/fail/unknown schema: read the grader")

    tests = " ".join(p.read_text() for p in (RL / "tests").glob("test_*.py"))
    pinned = [t for t in json.loads((RL / "tests/expected_rewards.json").read_text()) if t.startswith(prefix + "-")]
    card.set("G2", PASS if pinned else FAIL, f"{len(pinned)} tasks pinned in tests/expected_rewards.json")
    card.set("G1", MANUAL if fam_id in tests or prefix + "-" in tests else FAIL,
             "the family appears in rl/tests: read for pass / fail / paraphrase / negation cases"
             if fam_id in tests or prefix + "-" in tests else "the family is not mentioned in rl/tests")

    cal = fam.get("calibration") or {}
    raw = (d / "family.yaml").read_text()
    proposed = re.search(r"calibration:.*proposed", raw)
    card.set("H1", BLOCKED, f"calibration.pass = {cal.get('pass')}" + ("; still marked proposed in family.yaml" if proposed else ""))

    states = [(e.get("path", "?"), e.get("state", "?")) for e in provenance.for_family(fam_id)]
    absent = [p for p, s in states if s == "missing"]
    open_ = [f"{p} ({s})" for p, s in states if s not in ("approved", "missing")]
    card.set("J6", FAIL if absent else BLOCKED if open_ else PASS, (f"no provenance entry: {absent}; " if absent else "")
             + (f"{len(open_)} of {len(states)} gold inputs not approved: {', '.join(open_)}" if open_ else "all gold inputs approved"))
    ok, why = instrument.status(fam_id)
    card.set("J7", PASS if ok else BLOCKED, why)
    src = lib.source(fam["source"]).get("licence") or {}
    card.set("J8", BLOCKED, f"{fam['source']} licence.status = {src.get('status')}")
    return fam


# ---------- built tasks ----------

def pick(tasks: list, n: int) -> list:
    """Up to n planted tasks and one control, in id order."""
    planted = [t for t in tasks if not t[1].get("control")]
    return planted[:n] + [t for t in tasks if t[1].get("control")][:1]


def built(card: Card, fam_id: str, fam: dict, split: str, sample: int, full: bool) -> None:
    import local
    import run_solutions

    tasks = local.tasks(split, [fam_id])
    if not tasks:
        raise SystemExit(f"no {fam_id} tasks built under rl/tasks/{split}/: python rl/build.py {fam_id} --split {split} "
                         f"(train takes --n/--controls), or pass --static")
    chosen = tasks if full else pick(tasks, sample)
    names = ", ".join(d.name for d, _ in chosen)
    threshold = (fam.get("calibration") or {}).get("pass", 0.8)
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["JUDGE"] = "keyword"

    # J1 and the items check.py owns
    code, out = sh("rl/splits/check.py")
    prefix = fam.get("task_prefix", fam_id)
    mine = [ln for ln in out.splitlines() if fam_id in ln or f"{prefix}-" in ln]
    bad = code != 0 and (mine or "passed" not in out)
    for item in ("J1", "A4", "B3", "C1", "C6"):
        card.set(item, FAIL if bad else PASS, tail("\n".join(mine) or out, 4) if bad else "splits/check.py")
    card.set("A1", FAIL if bad else PASS, "splits/check.py check 9" if not bad else "")
    card.set("K1", BLOCKED, "python rl/splits/check.py --release (fails until J6 and J7 are signed)")

    # what the tasks themselves say
    modes, stray, unpinned, copies, canary = set(), [], [], [], []
    for d, m in tasks:
        cfg = tomllib.loads((d / "task.toml").read_text())
        modes.add(cfg["verifier"].get("environment_mode") or ("separate" if cfg["verifier"].get("environment") else "shared"))
        stray += [str(p.relative_to(d)) for p in (d / "environment").rglob("*") if p.name in STRAY]
        df = (d / "environment/Dockerfile").read_text()
        if "@sha256:" not in df.splitlines()[0] or re.search(r"pip install(?!.*==)", df) or re.search(r"curl|wget|git clone", df):
            unpinned.append(d.name)
        copies += [ln for ln in df.splitlines() if ln.startswith(("COPY", "ADD")) and not ln.startswith("COPY data ")]
        if not (d / "tests/CANARY").exists():
            canary.append(d.name)
    card.set("C3", FAIL if unpinned else PASS, f"unpinned or fetching Dockerfile: {unpinned[:5]}" if unpinned
             else f"{len(tasks)} Dockerfiles: digest-pinned base, pinned packages, no fetches")
    card.set("C6", FAIL if copies else PASS, f"Dockerfile copies more than data/: {sorted(set(copies))}" if copies else "Dockerfiles copy data/ only")
    card.set("C7", FAIL if stray else MANUAL, f"stray files in the image context: {stray[:8]}" if stray
             else "no stray state under environment/; confirm task.toml has no mounts")
    card.set("C8", WARN if modes != {"separate"} else PASS,
             f"verifier environment_mode: {sorted(modes)}" + ("" if modes == {"separate"} else
             ": the verifier runs in the container the agent had root in; record the residual risk or propose separate mode"))
    card.set("J5", FAIL if canary else PASS, f"no tests/CANARY in {canary[:5]}" if canary else "canary in every task; leakcheck keeps it out of view")
    card.set("J5", BLOCKED, "python rl/harness/canary_probe.py --model <m> --k 5 (API key)")
    if fam.get("dated"):
        card.set("C5", BLOCKED, "check 6 passed; clock readings need the sandbox probe (Docker)")
    else:
        card.set("C5", NA, "not a dated family")

    controls = [d.name for d, m in tasks if m.get("control")]
    if controls:
        card.set("I3", PASS, f"{len(controls)} of {len(tasks)} {split} tasks are no-action controls")
    else:
        card.set("I3", WARN, f"no task in {split} has control = true: name the family's no-action twins, or add them")
    seen = [hashlib.sha256(b"".join(p.read_bytes() for p in [d / "instruction.md", *sorted((d / "environment").rglob("*"))]
                                    if p.is_file())).hexdigest() for d, _ in tasks]
    if len(set(seen)) < len(seen):
        card.set("I5", FAIL, f"{len(seen) - len(set(seen))} tasks in {split} show the agent exactly what another task does")

    # B1, B4, D5: reference and naive, offline
    rows = []
    for d, m in chosen:
        r = {s: run_solutions.run_one(str(d), s) for s in ("reference", "naive")}
        again = run_solutions.run_one(str(d), "reference")
        rows.append((d.name, m.get("control", False), r["reference"], r["naive"], again))
    show = "; ".join(f"{n}: ref {r['reward']} naive {v['reward']}" for n, _, r, v, _ in rows)
    broken = [f"{n} ({r.get('note') or r['reward']})" for n, _, r, _, _ in rows
              if r["status"] != "ok" or r["reward"] is None or r["reward"] < threshold]
    card.set("B1", FAIL if broken else PASS, (f"reference below pass ({threshold}) or errored on: {', '.join(broken)}; " if broken else "")
             + f"{show} (pass at {threshold})")
    weak = [n for n, control, r, v, _ in rows if not control and r["reward"] is not None
            and ((v["reward"] or 0) >= threshold or r["reward"] - (v["reward"] or 0) < GAP)]
    card.set("B4", FAIL if weak else PASS, f"naive passes or is within {GAP} of the reference on: {weak}" if weak
             else f"naive below pass and at least {GAP} under the reference on planted tasks")
    drift = [n for n, _, r, _, again in rows if r["rewards"] != again["rewards"]]
    card.set("D5", FAIL if drift else PASS, f"reference graded twice gave different rewards on {drift}" if drift
             else f"reference graded twice, identical rewards ({len(rows)} tasks)")

    # E2, B5, D4: the attack suite
    import attacks
    if fam_id in attacks.FORMATS:
        targets = [(d, m) for d, m in chosen if attacks.attacked(m)]
        if not targets:
            card.set("E2", WARN, "none of the sampled tasks is attackable offline (attacks.attacked)")
        else:
            arows, problems = attacks.run(targets)
            by = {}
            for r in arows:
                by.setdefault(r["attack"], []).append(r["score"])
            means = ", ".join(f"{a} {sum(v) / len(v):.2f}" for a, v in by.items())
            card.set("E2", FAIL if problems else PASS, ("; ".join(problems)[:600] + "; " if problems else "") + means)
            crashes = [f"{r['task']}/{r['attack']}" for r in arows if r["crashed"] and r["attack"] != "GOOD"]
            card.set("D4", FAIL if crashes else PASS, f"verifier crashed on {crashes[:6]}" if crashes
                     else "no attack crashed the verifier (malformed, long, tamper included)")
            empties = {r["task"]: r["score"] for r in arows if r["attack"] == "empty"}
            paid = {t: s for t, s in empties.items() if s > 0}
            card.set("B5", FAIL if paid else PASS, f"no output earns reward: {paid}" if paid
                     else f"no output scores 0 on {len(empties)} tasks" + (" (a control among them)" if any(m.get("control") for _, m in targets) else "; no control sampled"))
    import ablation
    if fam_id in ablation.CREDIT:
        code, out = sh("rl/harness/ablation.py", "--split", split, "--family", fam_id, *([] if full else ["--sample", str(sample)]))
        card.set("B6", PASS if code == 0 else FAIL, tail(out, 3))

    # J2: the manifest matches what is built (check.py compares content hashes; a rebuild is the full proof)
    card.set("J2", MANUAL, f"check.py matched {len(tasks)} built tasks to the manifest; full proof: rebuild, then git diff --exit-code -- rl/splits/manifests")
    card.items["B1"]["evidence"].append(f"sampled: {names}" if not full else f"all {len(tasks)} tasks")


def calibration(card: Card, fam_id: str, split: str) -> None:
    runs = sorted((RL / "runs/calibration" / split).glob("*/stats.json"))
    cmd = f"python rl/harness/calibrate.py run --split {split} --model <strong> --model <weaker> --k 2 --budget <usd>"
    if not runs:
        card.set("H2", BLOCKED, f"no calibration run for {split}: {cmd} (approved instrument, API budget), then k 4, 8")
        for item in ("H4", "H5", "H7", "H8", "H9", "H11", "E6"):
            card.set(item, BLOCKED, "needs the calibration run (H2)")
        return
    stats = json.loads(runs[-1].read_text())
    tasks = {k: t for k, t in stats["tasks"].items() if t["family"] == fam_id}
    if not tasks:
        card.set("H4", BLOCKED, f"{runs[-1].parent.name} has no {fam_id} tasks: {cmd}")
        return
    models = sorted({m for t in tasks.values() for m in t["models"]})
    card.set("H2", PASS if len(models) >= 2 else FAIL, f"{runs[-1].parent.name}: models {models}; confirm one is a weaker family")
    for model in models:
        rates = [t["models"][model]["pass_rate"] for t in tasks.values() if model in t["models"] and t["models"][model]["pass_rate"] is not None]
        if not rates:
            continue
        zero, full_ = sum(r == 0 for r in rates), sum(r == 1 for r in rates)
        band = sum(BAND[0] <= r <= BAND[1] for r in rates)
        n = len(rates)
        card.set("H4", PASS if band / n >= 0.5 else WARN,
                 f"{model}: {zero}/{n} at 0, {band}/{n} in 1/8-3/8, {n - zero - full_ - band}/{n} otherwise mixed, {full_}/{n} at k/k")
        if zero:
            card.set("H5", MANUAL, f"{model}: {zero} tasks at 0/k to audit from transcripts")
    errored = max((s["errored"] for t in tasks.values() for s in t["models"].values()), default=0)
    card.set("H7", PASS if errored <= 0.05 else FAIL, f"worst errored share {errored}")
    k = stats["k"]
    solid = [(t["task_id"], m, s[f"pass^{k}"]) for t in tasks.values() for m, s in t["models"].items() if s.get(f"pass^{k}") is not None]
    if solid:
        mean = sum(v for _, _, v in solid) / len(solid)
        card.set("H11", MANUAL, f"mean pass^{k} {mean:.2f} over {len(solid)} task-model pairs (intervals in report.md); "
                 "add cost per correct outcome from the run records")
    fam = stats["families"].get(fam_id, {})
    card.set("H8", MANUAL, f"noise floor {fam.get('noise_floor')}; separation {fam.get('separation')}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", required=True)
    ap.add_argument("--split", default="train", help="train by default: bench and held-out cases you debug against must be retired")
    ap.add_argument("--sample", type=int, default=2, help="planted tasks to run solvers and attacks on (plus one control)")
    ap.add_argument("--full", action="store_true", help="every task of the split instead of a sample")
    ap.add_argument("--static", action="store_true", help="family-folder checks only; needs no built tasks")
    ap.add_argument("--out", type=pathlib.Path, help="write the scorecard (markdown) here as well as stdout")
    ap.add_argument("--json", type=pathlib.Path, help="write the items as JSON")
    a = ap.parse_args(argv)

    card = Card()
    fam = static(card, a.family)
    if not a.static:
        built(card, a.family, fam, a.split, a.sample, a.full)
        calibration(card, a.family, a.split)
    card.set("G4", MANUAL, 'run: pytest -m "not slow" && ruff check')
    if not docker():
        for item in ("B2", "C2"):
            card.set(item, BLOCKED, "no Docker daemon here: use the Oracle / Sandbox probe workflows")
    card.close()
    text = card.markdown(f"{a.family}" + ("" if a.static else f" / {a.split}") + (" (static only)" if a.static else ""))
    print(text)
    if a.out:
        a.out.write_text(text)
    if a.json:
        a.json.write_text(json.dumps(card.items, indent=1) + "\n")
    raise SystemExit(1 if any(i["status"] == FAIL for i in card.items.values()) else 0)


if __name__ == "__main__":
    main()
