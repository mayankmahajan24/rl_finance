# Dataset Valuation & Analysis suite (planned)

Not implemented yet. This directory is the extension point for a suite that evaluates whether
a model can assess if a novel (alternative) dataset yields alpha or operational value.

Planned tasks

- `coverage_assessment`: given a dataset dictionary and summary stats, report coverage,
  history length, point-in-time availability and obvious quality issues.
- `incremental_alpha`: given a toy regression of forward returns on an existing factor set
  plus the new dataset's feature, compute incremental R^2 / t-stat; scored against a
  reference implementation.
- `valuation_memo`: recommend buy / trial / pass with a price band; scored by `ExactMatch` on
  the decision, `ValueInRange` on the band, and an `LLMJudge` criterion on the rationale.

To implement: add `suite.py` with a `TaskSuite` subclass (`read_samples`, `domain_criteria`,
`spec`, `mirror`), fixtures under `fixtures/`, and `templates/default.j2`. Replace the
`Planned("dataset_valuation", ...)` line in `finrl_eval/suites/__init__.py` with `Live` of
that class. Answer constraints and FORMAT placement are read from the class.
