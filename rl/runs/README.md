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

Not kept: console logs (the results files carry everything they print) and patches (once applied,
the change is in git). Both are gitignored here.
