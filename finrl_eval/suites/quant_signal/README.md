# Quantitative Signal Research suite (planned)

Not implemented yet. This directory is the extension point for a suite that evaluates
signal-discovery workflows: given a small panel of synthetic price/fundamental data, can the
model specify a signal, compute it correctly, and reason about its information coefficient,
turnover and look-ahead bias?

Planned tasks

- `signal_computation`: compute a named factor (e.g. 12-1 momentum, book-to-price) from a
  fixture panel; scored with `NumericTolerance` against a reference implementation in
  `reference.py` (same pattern as `fixed_income/reference.py`).
- `ic_analysis`: rank IC and t-stat of a given signal vs forward returns.
- `bias_detection`: identify look-ahead / survivorship issues in a described backtest;
  scored with `ExactMatch` on a categorical label plus an `LLMJudge` criterion.

To implement: add `suite.py` with a `QuantSignalSuite(TaskSuite)`, `fixtures/panel.json`,
`templates/default.j2`, and register it in `finrl_eval/suites/__init__.py`.
