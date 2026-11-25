# anomaly_hindsight feedback log

Copied from anomaly_hard on 2026-11-25 (anomaly_hard feedback #61). Earlier history: rl/runs/anomaly_hard/reviews/feedback_log.md.

| # | Date | Item | Feedback (verbatim) | Kind | Done |
|---|---|---|---|---|---|
| 1 | 2026-11-25 | Setup | make sure there are no links between anomaly_hard and anomaly_hindsight, so we can change the instructions/graders/references/solutions for each separately | structure | anomaly_hindsight is a full copy: its own grade.py, build.py, background.py, perturb.py, writeup.py, judge.md, instruction.md, solutions and README; built tasks in rl/tasks/proto/anomaly_hindsight{,_train}; grader work folder /var/lib/anomaly_hindsight_grade; its own feedback log. Neither imports or reads the other (checked by search). Both still use the repo's shared panel code (rl/families/_shared) and source data, as every family does |
| 2 | 2026-11-25 | Runs | dont run the tasks yet. | hold | No model runs and no grading on anomaly_hindsight until asked. Tasks built (data only) |
