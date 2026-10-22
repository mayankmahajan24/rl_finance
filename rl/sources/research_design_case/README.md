# research_design_case: source data

Raw inputs for the `research_design` and `research_funding` tasks. `rl/build_research_design.py`
renders them into `rl/worlds/` and `rl/roles/*/research_*/rd-*`; `rl/replay_research_design.py`
re-grades the baseline runs against the built tree.

All of it comes from the Finance Domain Research Lead take-home (August 2026). The full
take-home (report, Parts 0–3, generation and scoring scripts, every raw model call) is in
git history at commit `a75441c`, under `case_study/`:

```sh
git show a75441c:case_study/REPORT.md
git archive a75441c case_study | tar -x -C /tmp    # the whole thing
```

## Layout

| Path | What it is | Was, in the case study |
|---|---|---|
| `seeds.json` | 10 seed ideas. `text` and `style` feed prompts; `discriminator` is grader-only (the produce tasks' must-hit item) | `seeds.json` |
| `contexts.json` | 6 firm briefs (the worlds), the seed→firm assignment, and the 4 context flips | `part2/contexts.json` |
| `items/<id>.json` | 14 items: context, seed, `plan_A`, `plan_B`. Everything here is model-visible | `part2/items/` |
| `plan_manifest.json` | Opaque generation token → (seed, slot, methodology) | `part2/plans/_manifest.json` |
| `ISOLATION.md` | What the generator, evaluator and scorer were each allowed to see when the items were built | `part2/ISOLATION.md` |
| `grader_only/gold/` | Human labels per item (`S*.json`), the prose split into issues (`_issues.json`), and the labelling instructions | `part2/gold/` |
| `grader_only/seed_catalog.md` | Per seed, what a good plan must do and how a capable analyst gets it wrong. Raw material for the produce rubrics | `ideas.md` |
| `grader_only/seed_only_runs/` | Claude's plan and critique per seed with no firm context, and the human verdict on each (`findings-table.md`). Reference outputs for the produce tasks | `part1/plans/`, `part1/critiques/`, `part1/findings-table.md`, `part1/PROVENANCE.md` |
| `baseline_runs/` | Four models' saved responses on every review and compare item, the scorer's cached decisions, and the headline numbers the replay must reproduce (`GRADED.md`) | `part2/runs/`, `part2/GRADED.md` |

`grader_only/` follows the same rule as a task's `grader/` folder: nothing in it may reach a
model under test. The build's leak check enforces that for the rendered prompts.

## Left out, on purpose

| Case-study path | Why |
|---|---|
| `part2/gold/design-intent.json` | The author's construction intent, not a gold label (`ISOLATION.md`) |
| `part2/forks.json` | Generator-tier methodology briefs; must never reach the evaluator tier |
| `part1/scores/` | Scored by a model; gold must be human |
| `part2/plans/raw/`, `part2/plans/short/` | The plans as generated and as edited. The edited text is already in `items/` |
| `part2/evaluator/*.md`, `scripts/` | Prompts and schemas are now canonical in `rl/prompts/research_design/`, `rl/schemas/` and `rl/graders/review_scorer*`; their fingerprints are checked by the replay |
| `REPORT.md`, `part0/`, `part3/`, and the per-part write-ups | Narrative, not task data |
