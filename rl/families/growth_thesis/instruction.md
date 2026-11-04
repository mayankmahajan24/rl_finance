# Thesis: which airline is growing fastest?

You are a data scientist at an investment firm. A portfolio manager asks: **which airline grew its underlying
transaction activity the fastest between calendar year {y1} and calendar year {y2}?** They want the growth of the
company's real activity, not of any one data vendor's panel.

{schema}

## What to deliver

1. `/app/output/answer.json`:

```json
{"fastest": "<ticker>",
  "growth": {"<ticker>": 0.12, "...": -0.03},
  "unreliable": ["<ticker>"]}
```

   * `growth`: your best estimate of each airline's {y1}->{y2} growth in total transactions (0.12 = +12%).
   * `unreliable`: airlines whose data cannot support this comparison even after cleaning (empty list if none).

2. `/app/output/memo.md`: a short memo (under 400 words) for the portfolio manager giving your conclusion and
   every data issue that affected it, with what you did about each.

You are scored on the correct answer, the accuracy of the growth estimates, the `unreliable` list, and whether the
memo correctly identifies the data issues that matter.
