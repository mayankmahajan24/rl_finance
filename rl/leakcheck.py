"""One leak check for every built task: nothing the agent sees may give away gold, the benchmark's
identity, or a disguised company. Builders run it before recording a manifest, and splits/check.py
runs it over every built task.

What the agent sees: instruction.md, prompt/ and environment/ (text files; .gz data is unpacked).

  gold       each family declares its gold fields under `leak_check` in family.yaml:
               gold_text     {tests file: [field, list[].field, ...]}: text of 40+ characters must not
                             appear (whitespace-normalized, first 80 characters)
               gold_numbers  {tests file: [field, ...]}: numbers must not appear in their common
                             formats (1234, 1,234, 1234.0, 1234.000), except in `number_exempt` files,
                             where a bare long number is coincidence
             a family whose ground truth is structural (tickers and dates that are in the data by
             construction) declares none and says why
  identity   no repo, source or upstream identifiers, URLs, SEC accession numbers, task ids, or
             benchmark framing ("you are being evaluated"). A source can allow a phrase in
             `identity_allowlist` in its source.yaml, with the reason
  disguise   for anonymised tasks (`leak_check.anonymised`: `all`, or tags such as `coded` and `anon`), none of
             the real names, tickers or series ids of the task's companies (word-bounded), except in
             the `exempt` files
  canary     the release canary (canary.txt) sits in every task's tests/ and nowhere the agent sees
"""

from __future__ import annotations

import gzip
import json
import pathlib
import re

import lib

RL = pathlib.Path(__file__).resolve().parent
CANARY = (RL / "canary.txt").read_text().strip()
IDENTITY = [
    r"rl[_ -]finance", r"txn_panel", r"research_design_case", r"Finance Domain Research Lead", r"take-?home",
    r"https?://", r"(?<!\d)\d{10}-\d{2}-\d{6}(?!\d)",
    rf"(?:{'|'.join(lib.family(f)['task_prefix'] for f in lib.families())})-(?:produce|review|funding|bench|heldout|train)-",
    r"you are being (?:evaluated|tested|graded|benchmarked)\b",
    r"(?:this|the) (?:task|question|prompt) is (?:a|an|part of an?) (?:benchmark|eval|evaluation|test)\b",
    r"(?:benchmark|eval) (?:task|item|suite)\b", r"Anomaly Detection Exercise",
]
# matched one by one against lowercased text: re.I, and one big alternation, are both slow on MBs of CSV
IDENTITY_RES = [re.compile(p.lower()) for p in IDENTITY]


def visible(d: pathlib.Path) -> dict[str, str]:
    """{relative path: text} of every file the agent sees."""
    out = {}
    for p in [d / "instruction.md", *sorted((d / "prompt").rglob("*")), *sorted((d / "environment").rglob("*"))]:
        if not p.is_file() or p.name == "Dockerfile":
            continue
        raw = gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
        out[str(p.relative_to(d)).removesuffix(".gz")] = raw.decode("utf-8", errors="replace")
    return out


def fields(obj, path: str) -> list:
    """Values at `path` ("a", "a[].b") in a JSON-like object; missing paths give nothing."""
    head, _, rest = path.partition(".")
    many = head.endswith("[]")
    v = obj.get(head.removesuffix("[]")) if isinstance(obj, dict) else None
    vals = (v or []) if many else ([] if v is None else [v])
    return [x for item in vals for x in (fields(item, rest) if rest else [item])]


def gold(d: pathlib.Path, cfg: dict) -> tuple[list[str], list[str]]:
    texts, numbers = [], []
    for kind, out in (("gold_text", texts), ("gold_numbers", numbers)):
        for name, paths in (cfg.get(kind) or {}).items():
            f = d / "tests" / name
            if f.exists():
                g = json.loads(f.read_text())
                out += [x for p in paths for x in fields(g, p) if x not in (None, "")]
    frags = {re.sub(r"\s+", " ", str(t)).strip()[:80] for t in texts}
    nums = {s for n in numbers if isinstance(n, (int, float)) and not isinstance(n, bool)
            for s in (f"{n:.0f}", f"{n:,.0f}", f"{n:.1f}", f"{n:.3f}") if len(s) >= 4}
    return sorted(f for f in frags if len(f) >= 40), sorted(nums)


def real_names(source: str, companies: list[str]) -> list[str]:
    """Every real name, ticker and series id of the companies; raises on a company the source doesn't know."""
    c = lib.entities(source)
    unknown = sorted(set(companies) - set(c))
    if unknown:
        raise SystemExit(f"{source}: unknown companies {unknown}, not in its entities file")
    names = [x for n in companies for x in (n, c[n]["name"], *c[n]["sensors"], *c[n]["series"])]
    return sorted({x for x in names if len(x) >= 2})


def task_problems(d: pathlib.Path, meta: dict) -> list[str]:
    """Everything wrong with what this task's agent sees."""
    cfg, tid, out = lib.family(meta["family"]).get("leak_check") or {}, d.name, []
    vis = visible(d)
    flat = {k: re.sub(r"\s+", " ", v) for k, v in vis.items()}
    texts, nums = gold(d, cfg)
    for frag in texts:
        out += [f"{tid}: gold text visible in {k}: {frag!r}" for k, v in flat.items() if frag in v]
    exempt = set(cfg.get("number_exempt", []))
    for n in nums:
        out += [f"{tid}: gold value {n} visible in {k}" for k, v in vis.items()
                if pathlib.Path(k).name not in exempt and re.search(rf"(?<![\d.,]){re.escape(n)}(?![\d,]|\.\d)", v)]
    allowed = [a["phrase"].lower() for a in lib.source(meta["source"]).get("identity_allowlist", [])]
    for k, v in flat.items():
        low = v.lower()
        hits = {m.group(0) for r in IDENTITY_RES for m in r.finditer(low)}
        out += [f"{tid}: identifying text {h!r} in {k}" for h in sorted(hits)
                if not any(h.lower() in a for a in allowed)]
    anon = cfg.get("anonymised")
    if anon and (anon == "all" or set(anon["tags"]) & set(meta.get("tags", []))):
        skip = set(anon.get("exempt", [])) if isinstance(anon, dict) else set()
        names = real_names(meta["source"], meta.get("companies", []))
        names_re = re.compile(r"\b(?:" + "|".join(map(re.escape, names)) + r")\b") if names else None
        for k, v in flat.items():
            if names_re and pathlib.Path(k).name not in skip:
                out += [f"{tid}: real name {n!r} in anonymised task's {k}" for n in sorted(set(names_re.findall(v)))]
    out += [f"{tid}: canary visible in {k}" for k, v in vis.items() if CANARY in v]
    if (d / "tests").is_dir() and CANARY not in ((d / "tests" / "CANARY").read_text() if (d / "tests" / "CANARY").exists() else ""):
        out.append(f"{tid}: tests/CANARY missing or not the current canary (rebuild)")
    return out
