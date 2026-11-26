The problems in `issues.json` should be fixed or excluded before these series are used. Each one distorts growth or levels for the period it covers.

How I searched: I ran independent checks over the full history. They cover exact duplicate rows, ticket size (amt / ct), runs of missing or near-zero days, weekly-cycle alignment against other sensors of the same ticker, and step changes in level, both ticker-wide and against peer sensors. Real business events move every sensor of a company together, so the peer comparisons separate them from sensor faults. Series with a median below 10 transactions a day were not checked.

What to do: remove duplicates, undo swapped columns and unit changes, re-align shifted dates, and exclude outage windows. Treat level shifts and re-mappings as breaks in the series, since growth across them is not real.

Limits: this list comes from automated rules with fixed thresholds, so a slow drift or a small step would not show up. Dates for step changes are approximate.
