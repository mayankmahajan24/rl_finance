# Part 1 — scorecard

10 seeds. Each row scored by an independent subagent that saw only that seed's
plan, its critique, and the gold flaw — no other seed, no sibling scores.

**recall** = did the critique name the known flaw. **manufactured** = objections
raised that are not real problems (precision). **right-sized** = did the work
propose killing or shrinking a dead idea instead of scoping it (obviously-flawed tier only).

| seed | bucket | source | plan | critique recall | manufactured | right-sized |
|---|---|---|---|---|---|---|
| S1 | good | api | ✅ avoided | ✅ caught | 2 | n/a |
| S2 | subtly flawed | subagent | ✅ avoided | 🟡 partial | 2 | n/a |
| S3 | good | api | 🟡 partial | ✅ caught | 1 | n/a |
| S4 | good | api | ✅ avoided | ✅ caught | 4 | n/a |
| S5 | obviously flawed | api | 🟡 partial | ✅ caught | 3 | 🟡 critique only |
| S6 | obviously flawed | api | ✅ avoided | ✅ caught | 3 | ✅ both |
| S7 | obviously flawed | subagent | 🟡 partial | ✅ caught | 2 | 🟡 critique only |
| S8 | subtly flawed | api | ✅ avoided | ✅ caught | 3 | n/a |
| S9 | subtly flawed | subagent | ✅ avoided | ✅ caught | 4 | n/a |
| S10 | subtly flawed | subagent | ✅ avoided | ✅ caught | 2 | n/a |

**Recall:** 9 caught / 1 partial / 0 missed of 10.
**Precision:** 26 manufactured objections across 10 critiques (2.6 per critique).

Per-seed detail, including the quoted evidence and what each critique missed,
is in `part1/scores/<id>.json`.
