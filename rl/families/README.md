# families/

A **family** is one kind of task: a generator or builder that turns a source into task instances,
the instruction the agent gets, the grader, and baseline solutions. Families are organized by what
the agent does; the tasks they build carry the fund role and workflow in their metadata.

| Family | Source | Agent's job | Reward | Format | Build |
|---|---|---|---|---|---|
| [`kpi_nowcast`](kpi_nowcast/) | txn_panel | Nowcast a company's quarterly KPI from the sensor panel and filed actuals; forecast JSON + write-up | Forecast accuracy (code) + C1–C12 write-up rubric (LLM judge) | repo format (Harbor in step 4) | `python rl/families/kpi_nowcast/build.py` |
| [`data_audit`](data_audit/) | txn_panel | Find planted data-quality problems in a disguised panel | F1 against planted + natural problems | Harbor | `python rl/build_panel_tasks.py --split <s> --family data_audit` |
| [`anomaly_scoring`](anomaly_scoring/) | txn_panel | Write an online anomaly scorer with no foresight | F1 × coverage, zeroed by a foresight check | Harbor | same, `--family anomaly_scoring` |
| [`growth_thesis`](growth_thesis/) | txn_panel | Which airline grew fastest? Answer + memo, on semi-synthetic data with traps | 0.35 answer + 0.25 growth + 0.15 unreliable list + 0.25 memo rubric | Harbor | same, `--family growth_thesis` |
| research_design / research_funding | research_design_case | Review, compare or write research plans | Issue recall − penalties; pairwise pick | repo format (Harbor in step 4) | `python rl/build_research_design.py` |

The three Harbor families came from `~/altdata_evals` (2026-10-21). Built on every company with
its seeds, they reproduced its 18 pilot tasks byte for byte, and the reference and naive solutions
scored exactly as they did there (verified at commit `0411bc4`). That pilot used held-out
companies, so it was then removed; its seeds are retired (`splits/seeds.yaml`).

## Layout of a family

```
<family>/
  family.yaml          id, task_prefix, role, workflow, mode, world, source, format, verifier, reward
  generate.py          (seed, control, panel restricted to one split) -> (agent-visible data, ground truth)
  instruction.md       template; {{placeholders}} filled at build time
  verifier/            grader that runs in Harbor's tests/ (copied in only after the agent finishes)
  solutions/reference  strong solution; also the task's solution/ for Harbor's oracle agent
  solutions/naive      deliberately naive; proves the verifier separates quality
_shared/               code used by several families: panel disguise and injection, the Harbor writer,
                       the verifier helpers, the panel schema text
```

## Rules every family follows

- **Build only from the split's companies.** Ask `splits.companies(source, split)` and pass the
  generator a panel restricted to those companies. Record them in the task's `companies` metadata;
  `splits/check.py` fails the build otherwise.
- **Seeds from `splits.seeds()`**, never hard-coded. Held-out seeds are secret, so held-out task
  ids and metadata never contain them.
- **Facts about the data come from the source's `annotations/`**, not constants in the family.
- **Nothing grader-side in `environment/`.** Ground truth lives in `tests/`.
- **A naive solution that scores near zero and a reference that scores well.** If both score the
  same, the task measures nothing.

## Adding a family

1. Copy the closest family folder; fill in `family.yaml`.
2. Write `generate.py` against the source loader, taking the split-restricted data as input.
3. Write the instruction, verifier, and both solutions.
4. Add it to `FAMILIES` in `rl/build_panel_tasks.py` (or give it its own build script if it isn't a
   generated panel family), build a small `train` split, and run
   `python rl/harness/run_solutions.py`.
5. `python rl/splits/check.py` must pass.
