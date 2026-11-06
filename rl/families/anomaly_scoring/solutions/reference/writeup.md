`score.py` gives every row a probability of being bad data. A score above 0.5 is a flag.

Method: each sensor is compared with the other sensors of the same company, so holidays, seasonality and company-wide moves cancel out. A robust z-score on that offset catches one-day anomalies. A 7-day median of the offset catches level shifts and sensor dropouts. A shift lasting 90 days is accepted as the new normal and the baseline is re-based. Large company-wide moves widen the noise band. I chose peer comparison over a per-sensor seasonal model because the panel's sensors share a company's real activity but not each other's faults.

No foresight: every statistic uses trailing windows of rows dated on or before the score date. A sensor needs 56 days of history before it is considered warmed up.

Checks and limits: there are no labels here, and the thresholds are fixed parameters in `anomaly_model.py`, not fitted to this panel, so I report no accuracy figure. A company with a single sensor has no peers to compare against, and a fault hitting all of a company's sensors at once looks like a real move.
