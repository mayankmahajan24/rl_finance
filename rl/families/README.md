# families/

A **family** is one kind of task: a builder that turns a source into task instances,
the instruction the agent gets, the grader, and baseline solutions. Families are organized by what
the agent does; the tasks they build carry the fund role and workflow in their metadata.

Every family builds tasks in the same Harbor layout through `_shared/harbor.py` (`../FORMAT.md`),
into `rl/tasks/<split>/`, and records them in `splits/manifests/<family>.json`. Build with
`python rl/build.py <family>`. Every reward is in [0, 1]: a verifier writes it to reward.txt, or as
`reward` in reward.json beside named diagnostics. A verifier that can't grade (its judge is
unavailable) writes an empty reward.json and says why; one that crashes writes nothing, which Harbor
records as an error, never a zero.

| Family | Source | Agent's job | Reward | Runner |
|---|---|---|---|---|
| [`research_design`](research_design/) | research_design_case | Review or compare (as PM) research plans for a named fund | Issue recall − penalties; pairwise pick, correct in both orders | `harness/run_api.py` (API, skills on/off); `replay.py` |
| [`kpi_nowcast`](kpi_nowcast/) | txn_panel | Nowcast a company's quarterly KPI from the sensor panel and filed actuals; forecast JSON + write-up | Skill vs the naive forecast, clamped to [0, 1]; accuracy and the C1–C12 write-up rubric (LLM judge) as diagnostics | `harness/run_api.py` (API, code execution) |
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
  family.yaml          id, task_prefix, version, authors (names), role/workflow/mode/world (lists), source,
                       builder (module), verifier, gold_file, reward, judge, gold_inputs, instrument, ...
  build.py             builds every task of the family (research_design, kpi_nowcast), or
  generate.py          make_variant(seed, control, ctx) for families built by _shared/build_panel.py
  instruction.md / prompts/   templates; placeholders filled at build time
  verifier/            runs in Harbor's tests/ (copied in only after the agent finishes)
  graders/, grader.py  graders shared by the verifier and the API runner
  solutions/reference  strong solution, or the oracle (gold) answer; the task's solution/ for Harbor's oracle agent
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
- **Nothing grader-side in `environment/` or `prompt/`.** Gold lives in `tests/`. Declare which
  `tests/` fields are gold, and whether tasks are anonymised, under `leak_check` in `family.yaml`;
  the shared check (`../leakcheck.py`) does the rest.
- **Write through `_shared/harbor.py` and record the manifest entries it returns**
  (`splits.write_manifest`). Every task's metadata has its `fingerprint` (what the agent sees) and
  its `case` (the unit that must never straddle splits); gold goes to `tests/<gold_file>`.
- **List the files your gold comes from** under `gold_inputs` in `family.yaml`, each with a
  provenance entry (`../FORMAT.md`, Gold provenance). Nothing ships until they are approved.
- **Declare the instrument** under `instrument` in `family.yaml`: every file that decides what the
  model sees or how it is scored. Live runs and releases need its hash approved
  (`../harness/approve.py`); changing any of them reopens the approval.
- **A naive solution that scores near zero and a reference that scores well.** If both score the
  same, the task measures nothing.

## Versions

`version` in `family.yaml` goes into every task's `[task] version`. Bump it in the same change that
alters the family's tasks, so a score is only ever compared with scores of the same version:

| Bump | When | Examples |
|---|---|---|
| major | the reward means something different | gold or ground truth changed, the verifier or grader logic changed, the reward formula or its weights changed |
| minor | the instrument changed, the reward did not | a prompt fingerprint changed (instruction, prompt or visible data), the sandbox changed (image, network, clock) |
| patch | nothing a model or grader sees | task metadata or documentation only |

A release (`../release/release.yaml`) bumps by the largest family bump it contains.

## Adding a family

1. Copy the closest family folder; fill in `family.yaml`. `rl/build.py` finds it there.
2. A generated panel family sets `builder: families._shared.build_panel` and writes `generate.py`
   (`make_variant(seed, control, ctx)`, ctx holding only the split's panel); anything else writes a
   `build.py` with `build(family_id, splits, n, controls)` and names it as its `builder`.
3. Write the instruction, verifier, and both solutions.
4. `python rl/build.py <family>` (it ends with the split check), then
   `python rl/harness/run_solutions.py --split <split>` if it has baseline solutions. Commit the
   manifest.
