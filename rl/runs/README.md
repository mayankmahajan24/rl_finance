# runs/

Records of model and solver runs: what was run, what it scored, and what a human concluded from it.
Nothing here is an input to a build or a grader.

```
runs/<family>/
  <variant>/       one run condition (e.g. baseline): results.jsonl, errors.jsonl, traces/, or the
                   runner's own per-model files
  reviews/         human reviews of runs and the grader feedback log, with dispositions
  trajectory/      score per variant over time
  report.html      generated report over the variants
  _state.json      runner state (kpi_nowcast: the approved harness hash)
runs/solutions/<split>.csv   reference vs naive solver scores on built Harbor tasks
```

**Run records.** Every runner also writes its results in one schema
(`../harness/run_record.schema.json`, one row per task and attempt), beside its own files:
`records.jsonl` or `<name>.records.jsonl`. A record names the instrument it was measured with (the
task's `content_sha256` and prompt fingerprint), the runner, model, skills, effort, max tokens and
judge, its named rewards, a status (`ok`, `error`, `refusal`, `timeout`, `truncated`,
`parse_error`, `not_graded`), and tokens, cost and latency.

```sh
python rl/harness/records.py import                     # convert the run files above (done once; committed)
python rl/harness/records.py import-harbor jobs/ --out rl/runs/harbor/<tag>/records.jsonl
python rl/harness/report.py --split bench               # leaderboard per family, mode and condition
python rl/harness/report.py --split train --mix         # tasks measured on several instruments, side by side
```

`report.py` refuses to average a task measured with two instruments (a changed prompt, task, or
an unrecorded instrument next to a recorded one) unless `--mix` asks for them side by side. The
imported kpi_nowcast pilot predates fingerprints, so its records carry none and never merge with
new runs. Costs come from the pinned price table `../harness/prices.yaml`; `--budget <usd>` on
both API runners stops starting tasks once spend reaches it.

Not kept: console logs (the results files carry everything they print) and patches (once applied,
the change is in git). Both are gitignored here.
