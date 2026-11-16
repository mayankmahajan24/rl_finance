# anomaly_scoring grader feedback log

Your feedback on the anomaly_scoring tasks and grading, recorded verbatim with a date. Each entry gets a disposition once it's acted on. Findings refer to [`review_2026-11-16.md`](review_2026-11-16.md). Grader changes made from these entries go through the usual harness diff and re-approval.

Disposition values: `open`, `rubric change`, `new programmatic check`, `case/gold change`, `reference change`, `no change` (with reason).

## Your feedback

| # | Date | Scope (case / rubric item / general) | Feedback (verbatim) | Disposition | Change made |
|---|---|---|---|---|---|
| 1 | 2026-11-16 | General (difficulty) | whats the difference bbetween the data audit stuff and the anomaly task? i am worried that the anomaly task will have similar results to the data audit where the models score very hihg | open | Opus smoke run on bench 001, 002 and control-01; see the review |
| 2 | 2026-11-16 | General (frontier runs) | ok do this using my subscription | done | Run through the subscription CLI, ANTHROPIC_API_KEY unset |
