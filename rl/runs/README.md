# runs/

Records of model and solver runs: what was run, what it scored, and what a human concluded from it.
Nothing here is an input to a build or a grader.

```
runs/api/<split>/<run_id>/            rl/harness/run_api.py: records.jsonl, args.json; traces/ (not in git)
runs/calibration/<split>/<run_id>/    rl/harness/calibrate.py: records.jsonl, args.json, report.md, stats.json; jobs/ (not in git)
runs/solutions/<split>.records.jsonl  reference vs naive solvers on built tasks (rl/harness/run_solutions.py)
runs/attacks/<split>.csv              the reward-hacking suite (rl/harness/attacks.py)
runs/<family>/baseline/               earlier runs, kept as records only
runs/<family>/reviews/                human reviews of runs and the grader feedback log, with dispositions
runs/kpi_nowcast/trajectory/          score per variant over time; _state.json: report settings
```

**Run records.** Every runner writes one schema (`../harness/run_record.schema.json`, one row per task
and attempt). A record names the instrument it was measured with (the content_sha256 of the task
folder that was run, the fingerprint of what the model saw, the family's instrument hash), the
runner, model, skills, effort, max tokens and judge, its named rewards, a status (`ok`; `refusal`,
`truncated`, `timeout`, `parse_error`, which score 0; `error` and `not_graded`, which are never
scored), and tokens, cost and latency.

Only records are committed. They carry rewards, never the model's answer, gold, grading breakdowns
or task metadata (an anonymised task's real company stays out of git). Transcripts, Harbor jobs and
other raw outputs stay local and are gitignored.

```sh
python rl/harness/records.py import-harbor jobs/ --out rl/runs/harbor/<run_id>/records.jsonl
python rl/harness/report.py --split bench               # leaderboard per family, mode and condition
python rl/harness/report.py --split train --mix         # tasks measured on several instruments, side by side
```

`report.py` refuses to average a task measured with two instruments unless `--mix` asks for them side
by side. The baseline records predate task bundles, so they carry no content_sha256 and never merge
with new runs. Costs come from the one price table, `../harness/prices.yaml`; `--budget <usd>` on
run_api.py and calibrate.py stops starting work once spend reaches it.
