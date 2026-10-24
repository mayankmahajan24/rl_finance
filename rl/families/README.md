# families/

A **family** is one kind of task: a generator or builder that turns a source into task instances,
the instruction the agent gets, the grader, and baseline solutions. Families are organized by what
the agent does; the tasks they build carry the fund role and workflow in their metadata.

Every family builds tasks in the same Harbor layout through `_shared/harbor.py` (`../FORMAT.md`),
into `rl/tasks/<split>/`, and records them in `splits/manifests/<family>.json`. Build with
`python rl/build.py <family>`.

| Family | Source | Agent's job | Reward | Runner |
|---|---|---|---|---|
| [`research_design`](research_design/) | research_design_case | Review, compare (as PM) or write a research plan for a named fund | Issue recall − penalties; pairwise pick; produce has no grader yet | `run.py` (API, skills on/off); `replay.py` |
| [`kpi_nowcast`](kpi_nowcast/) | txn_panel | Nowcast a company's quarterly KPI from the sensor panel and filed actuals; forecast JSON + write-up | Named metrics: forecast accuracy (code) and C1–C12 write-up rubric (LLM judge) | `run.py` (API, code execution, harness-gated) |
| [`data_audit`](data_audit/) | txn_panel | Find planted data-quality problems in a disguised panel | F1 against planted + natural problems | Harbor |
| [`anomaly_scoring`](anomaly_scoring/) | txn_panel | Write an online anomaly scorer with no foresight | F1 × coverage, zeroed by a foresight check | Harbor |
| [`growth_thesis`](growth_thesis/) | txn_panel | Which airline grew fastest? Answer + memo, on semi-synthetic data with traps | 0.35 answer + 0.25 growth + 0.15 unreliable list + 0.25 memo rubric | Harbor |

Every task also runs under Harbor (`harbor run -p rl/tasks/<split>`). Families with an API runner
keep the exact API messages in each task's `prompt/`; the Harbor instruction is the same text plus
where to find files and write the answer.

The three Harbor families came from `~/altdata_evals` (2026-10-21). Built on every company with
its seeds, they reproduced its 18 pilot tasks byte for byte, and the reference and naive solutions
scored exactly as they did there (verified at commit `0411bc4`). That pilot used held-out
companies, so it was then removed; its seeds are retired (`splits/seeds.yaml`).

## Layout of a family

```
<family>/
  family.yaml          id, task_prefix, role, workflow, mode, world, source, verifier, reward
  build.py             builds every task of the family (research_design, kpi_nowcast), or
  generate.py          (seed, control, split's panel) -> (data, ground truth), for generated families
  instruction.md / prompts/   templates; placeholders filled at build time
  verifier/            runs in Harbor's tests/ (copied in only after the agent finishes)
  graders/, grader.py  graders shared by the verifier and the API runner
  run.py               API runner, where the family has one
  solutions/reference  strong solution; also the task's solution/ for Harbor's oracle agent (generated families)
  solutions/naive      deliberately naive; proves the verifier separates quality
_shared/               harbor.py (the one task writer), build_panel.py (builds the generated families
                       per split), panel disguise and injection, verifier helpers, panel schema text
```

## Rules every family follows

- **Build only from the split's companies.** Ask `splits.companies(source, split)` and pass the
  generator a panel restricted to those companies. Record them in the task's `companies` metadata;
  `splits/check.py` fails the build otherwise.
- **Seeds from `splits.seeds()`**, never hard-coded. Held-out seeds are secret, so held-out task
  ids and metadata never contain them.
- **Facts about the data come from the source's `annotations/`**, not constants in the family.
- **Nothing grader-side in `environment/` or `prompt/`.** Gold lives in `tests/`; every builder
  runs a leak check.
- **Write through `_shared/harbor.py` and record a manifest** (`splits.write_manifest`).
- **A naive solution that scores near zero and a reference that scores well.** If both score the
  same, the task measures nothing.

## Adding a family

1. Copy the closest family folder; fill in `family.yaml`.
2. Write `generate.py` against the source loader, taking the split-restricted data as input.
3. Write the instruction, verifier, and both solutions.
4. Register it: a generated panel family in `FAMILIES` in `_shared/build_panel.py`; anything else
   gets its own `build.py` with a `main()` and an entry in `BUILDERS` in `rl/build.py`.
5. `python rl/build.py <family>` (it ends with the split check), then
   `python rl/harness/run_solutions.py --split <split>` if it has baseline solutions. Commit the
   manifest.
