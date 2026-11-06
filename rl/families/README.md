# families/

A **family** is one kind of task: a builder that turns a source into task instances,
the instruction the agent gets, the grader, and baseline solutions. Families are organized by what
the agent does; the tasks they build carry the fund role and workflow in their metadata.

Every family builds tasks in the same Harbor layout through `_shared/harbor.py` (`../FORMAT.md`),
into `rl/tasks/<split>/`, and records them in `splits/manifests/<family>.json`. Every reward is in
[0, 1]: a verifier writes it to reward.txt, or as `reward` in reward.json beside named diagnostics.
A verifier that can't grade (its judge is unavailable) writes an empty reward.json and says why; one
that crashes writes nothing, which Harbor records as an error, never a zero. Every task runs under
Harbor and through `harness/run_api.py`, graded by the same verifier (commands: `../README.md`).

| Family | Source | Agent's job | Reward |
|---|---|---|---|
| [`research_design`](research_design/) | research_design_case | Review a research plan for a named fund, or compare two (as PM) in both orders | Issue recall − penalties; 1 only for the gold plan in both orders |
| [`kpi_nowcast`](kpi_nowcast/) | txn_panel | Nowcast a company's quarterly KPI from the sensor panel and filed actuals; forecast JSON + write-up | Skill vs the naive forecast, clamped to [0, 1]; accuracy and the C1–C12 write-up rubric (LLM judge) as diagnostics |
| [`data_audit`](data_audit/) | txn_panel | Find planted data-quality problems in a disguised panel | F1 against planted + natural problems; write-up rubric as a separate metric |
| [`anomaly_scoring`](anomaly_scoring/) | txn_panel | Write an online anomaly scorer with no foresight | F1 × coverage, zeroed by a foresight check; write-up rubric as a separate metric |
| [`growth_thesis`](growth_thesis/) | txn_panel | Which airline grew fastest? Answer + memo, on semi-synthetic data with traps | 0.35 answer + 0.25 growth + 0.15 unreliable list + 0.25 memo rubric |

The three Harbor families came from `~/altdata_evals` (2026-10-21). Built on every company with
its seeds, they reproduced its 18 pilot tasks byte for byte, and the reference and naive solutions
scored exactly as they did there (verified at commit `0411bc4`). That pilot used held-out
companies, so it was then removed; its seeds are retired (`splits/seeds.yaml`).

## Layout of a family

```
<family>/
  family.yaml          id, task_prefix, version, authors (names), role/workflow/mode/world (lists), source,
                       format, tools, builder (module), verifier, verifier_timeout_sec, gold_file (gold.json),
                       reward, judge, gold_inputs, instrument, calibration, leak_check
  build.py             build(family_id, splits, n, controls) (research_design, kpi_nowcast), or
  generate.py          make_variant(seed, control, ctx) for families built by _shared/build_panel.py
  instruction.md / prompts/   templates; placeholders filled at build time
  verifier/            runs in Harbor's tests/ (copied in only after the agent finishes)
  graders/, grader.py  scoring code the verifier imports
  solutions/reference  strong solution, or the oracle (gold) answer; the task's solution/ for Harbor's oracle agent
  solutions/naive      deliberately naive; proves the verifier separates quality
  provenance.yaml      who produced each gold input the family owns, and its review (../provenance.py)
  approval.yaml        the approved instrument hash (../instrument.py; written by harness/approve.py)
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

A new family is a folder here; no shared code changes.

1. **`family.yaml`.** Copy the closest family's and fill it in: `builder` (the module `rl/build.py`
   imports), `verifier`, `verifier_timeout_sec`, `gold_file: gold.json`, `source`, `reward`,
   `tools: [code_execution]` if the agent needs to run code, `judge` if the verifier calls a model,
   `gold_inputs`, `instrument`, `calibration` and `leak_check`. `rl/build.py` finds it through
   `lib.families()`.
2. **Builder.** A generated panel family sets `builder: families._shared.build_panel` and writes
   `generate.py` (`make_variant(seed, control, ctx)`, ctx holding only the split's panel). Any other
   family writes a `build.py` exposing `build(family_id, splits, n, controls)` that writes each task
   through `_shared/harbor.py` with `fingerprint` and `case` in its metadata, and records the
   manifest (`splits.write_manifest`).
3. **Instruction and verifier.** The verifier writes `reward.txt`, or `reward.json` with `reward` in
   [0, 1]; a judged one calls `_shared/judge.py`.
4. **Solutions.** `solutions/reference/solve.sh` and `solutions/naive/solve.sh`.
5. **Provenance and approval.** A `provenance.yaml` entry for every gold input (`../FORMAT.md`, Gold
   provenance) and an `approval.yaml` with `approved: null` and `history: []` until
   `harness/approve.py` approves the instrument.
6. **Build and check.** `python rl/build.py <family>` (it ends with the split check), then
   `python rl/harness/run_solutions.py --split <split> --family <family>`: the reference must beat
   naive. Commit the manifest.

Optional per-family hooks in the harness, for families that want them: an output-format adapter in
`harness/attacks.py` (`FORMATS`; families without one are not attacked), a per-trap credit check in
`harness/ablation.py` (`CREDIT`), and pinned solver rewards in `tests/test_verifiers.py` (`SAMPLE`,
recorded in `tests/expected_rewards.json`).
