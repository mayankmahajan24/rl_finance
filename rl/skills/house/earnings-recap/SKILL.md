---
name: earnings-recap
user_invocable: true
description: >
  Use this skill when the user wants a finished investor-grade recap of a
  completed earnings call. Work from a supplied transcript or retrieve the
  latest available call, then produce a decision-led post covering the surprise,
  changed underwriting, contrary evidence, and portfolio implications. Do not
  use it for a quick earnings lookup, a historical guidance reconstruction, or
  ghostwriting in the user's personal voice.
---

# Earnings Recap

Write the post an elite public-markets analyst would publish after the call. The
reader should immediately know the surprise versus expectations, why the stock
reacted when knowable, what changes in estimates or thesis, the strongest evidence
against that conclusion, and the read-through for other positions.

Read and follow [the Slack format](references/slack-format.md). Return only the
finished post. Do not show research notes, methodology, citations, links, or a
source footer.

Read [the editorial opening patterns](references/editorial-patterns.md) to calibrate
which contested decision deserves the lead. Treat them only as selection precedent;
never transfer their facts, tickers, conclusions, or house views to the current call.

## Establish the evidence

Use a supplied transcript when available. Otherwise retrieve the latest completed
earnings call and its supporting company materials. Read the complete call before
ranking conclusions. Use targeted searches only to revisit important changes, Q&A
challenges, timing, and named counterparties in context.

Before ranking, read and apply [the coverage worksheet](references/coverage-worksheet.md).
Use it to separate reported facts, external expectations, management framing,
inference, and house context before choosing themes.

When research tools are available, make one dated context pass before drafting. For a
historical call, use only information knowable at the requested point in time. Seek
actuals and guidance versus Street or a separately sourced buyside expectation, the
prior implied guide, beat-to-guide pass-through, stock reaction, valuation, and the
prevailing debate. The transcript already supplies reported facts: retrieve only
missing comparators or context. Record the source date, period, and provenance. Mark
unavailable items `not found`; do not manufacture them.

Reconcile conflicts before using a fact. Prefer the company release or presentation
for reported metrics, the complete call transcript for exact management language,
and a dated external source for Street expectations or market reaction. When two
credible sources still disagree, omit the disputed figure or attribute the difference
without presenting either value as settled.

Preserve metric, entity, period, unit, denominator, and status. Distinguish actual,
guidance, target, pipeline, design win, and aspiration. A number introduced by an
analyst remains an analyst premise unless management validates it. Preserve every
material condition, and label calculations or bridges as inference. When management
conditionally validates an analyst premise, preserve both the endorsement and every
condition rather than reducing it to either an unsupported premise or a company target.

When filesystem tools are available, materialize the worksheet and candidate cards in
a workspace-local temporary file. Rank the complete slate there, record why the
strongest omitted card loses to the weakest selected card, and draft the post in a
second temporary file. Audit and revise that draft once, then delete both temporary
files before returning. This private work prevents an easy-to-write scorecard fact
from displacing a harder investment decision.

## Choose the investment decisions

Read and apply [the decision-selection guide](references/decision-selection.md) before
turning the completed coverage ledger into one final slate. Use its single ranking and
omission test. Never return the working slate.

Choose purposeful exact management quotes only after ranking. Normally retain two or
three that prove different decision-relevant points, including the strongest adverse
qualification when present. Preserve wording, speaker, context, and every material
qualifier; never silently splice or polish a quote.

## Draft and audit

Draft in the exact structure and publication budget defined by
[the Slack format](references/slack-format.md). Compress only after reconciling the
draft against the completed ledger. Aim for 375–450 words and never return more than
475.

Before returning, read and complete [the final audit](references/final-audit.md),
including its coverage, fidelity, and editing gates. Where a presentation rule is
needed, the Slack format is canonical. Return only the audited post.
