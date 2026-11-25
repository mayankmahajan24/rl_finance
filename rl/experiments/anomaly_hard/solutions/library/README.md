# Library-based variants of the practitioner reference (experiment E30, retired)

Each is `../practitioner/score.py` with one hand-written part swapped for a library. Data reward on the 15 tuning
panels (practitioner 0.871 in the same environment):

| Variant | Library replaces | Reward | False alerts / panel |
|---|---|---|---|
| `mstl` | statsmodels MSTL removes weekly and yearly seasonality from the sister comparison | 0.760 | 9.2 |
| `sf` | statsforecast AutoETS: a week outside the 99% forecast interval raises a level change (for CUSUM) | 0.741 | 16.0 |
| `rup` | ruptures least-squares single break in the last 90 days raises a level change (for CUSUM) | 0.738 | 19.0 |
| `beast` | Rbeast Bayesian change point (screened) raises a level change (for CUSUM) | 0.721 | 18.8 |
| `prophet` | Prophet fits the source's difference from its sisters' median (for the pairwise anchor) | 0.540 | 33.8 |

Why they lose: break finders built for whole-series segmentation miss ramps and slow drifts in real time, which then
leak out as many one-day spikes (false alerts), and stricter thresholds cut recall without cutting them; the sister
comparison already removes seasonality, so MSTL adds noise; Prophet on the sisters' median moves whenever a sister
enters or leaves. Rbeast's first result in a process differs from later ones with the same seed (a warm-up call
fixes it; without it the point-in-time check fails).
