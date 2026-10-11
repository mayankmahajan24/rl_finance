# Filling in gold

> **Status:** the ten base items (`S1`–`S10`) are filled and scored. The four
> context-flip items (`S2F`, `S5F`, `S8F`, `S9F`) are still empty — `score.py`
> excludes them by name rather than shrinking the denominator silently. Filling
> them is the one thing that would unblock the context-sensitivity axis.
>
> Gold prose is classified into blocking / secondary / anti-objection / praise by
> `scripts/split_gold.py`; the **anti-objection** label (explicitly ruling an
> objection *out*) turned out to be the highest-value thing in gold, so write those
> down when you have them.

One file per item: `part2/gold/S1.json` … `S10.json`, plus the four flips
(`S2F`, `S5F`, `S8F`, `S9F`). Nine fields each.

**Judge blind** — don't open `design-intent.json` in this directory until you're
done. It holds my private read of which plan is stronger, and the value of your
label is that it's independent of mine.

Read the pair in `part2/items/<id>.json`: `context` (who's asking), `seed`,
`plan_A`, `plan_B`. Judging basis is `../evaluator/TENETS.md` — same standard the
model is held to.

| Field | What to write |
|---|---|
| `goal_type` | What this analysis is *for*: `single_name_kpi`, `broad_market_effect`, `mechanism_test`, `blind_fit_oos`, `capability_build` |
| `error_asymmetry` | `type_i_dominant`, `type_ii_dominant`, or `symmetric` — which error the payoff structure punishes |
| `preference` | `A` or `B` — which you'd put an analyst on |
| `preference_strength` | `strong` or `weak` |
| `decisive_tenets` | Which tenets actually drove it, most important first. Usually one or two |
| `preference_rationale` | Why, in a few sentences |
| `critique_A` / `critique_B` | Desk review of each plan, as prose |
| `why_loser_was_defensible` | 1–2 sentences: why a capable analyst would have gone the other way |

## Fill the frame first

`goal_type` and `error_asymmetry` come before everything else, because most
judgments are conditional on them. Breadth only matters if the goal is a broad
effect. A demanding plan is right where Type I dominates and over-engineered
where Type II does. Get these two down and the rest follows.

## Both plans are real approaches

Each pair is two genuinely different strategies, each built as the strongest
version of its own approach. Neither was constructed to be wrong, and neither
carries a deliberate defect. So `preference` is a real judgment call, not the
recovery of a hidden answer.

**You must pick A or B — `preference_strength` is how you say it was close.**
Mark `weak` when you could be argued out of it. Weak items are scored separately,
so disagreement there counts far less against a model. Don't inflate a weak call
to make the label look decisive.

## Write the critiques as prose

However the issues occur to you. Don't tier them —
`scripts/categorize_gold.py` splits your prose into discrete issues and marks
each **blocking** (conclusion untrustworthy until resolved) or **secondary**
(worth fixing, answer still usable). You review that split before it's used.

Four things worth stating explicitly when they apply, because each is an axis
where models fail in a specific direction:

**Say when an objection doesn't apply.** Your Part 1 verdicts caught this four
times — universe size and survivorship bias on S2, tertiary confounders on S1, an
impossible statistical test on S3, an inflated event-count requirement on S9.
Each concern is real *somewhere*, which is exactly why misapplication needs
catching here.

**Say where the edge is** — or isn't. Work makes money by concluding something
different from consensus, or reaching the same view faster. A plan measuring
something true that everyone already knows is worth nothing. Note that speed is a
legitimate edge, and that a capability build (S3) is exempt.

**Say when a plan is over-scoped, or when a fast kill is the right answer.**
Part 1 found this is where the plan step is weakest — Claude names an idea as
weak and budgets weeks to confirm it anyway.

**Say when the measure stops working.** A multiple with a negative denominator is
meaningless rather than large, and the metric the market prices shifts as a
company matures — revenue for high-growth, EBITDA for mature. Your S6 verdict
caught both. A plan that silently winsorizes or drops those cases has excluded
the interesting observations.

**Say when a plan generalizes where it shouldn't.** Your S7 verdict —
*"generalizing if and only if company has no prior valid events."* The company's
own record beats an industry base rate whenever that record exists; the
cross-section is the fallback, not the default. Note that this pulls against
breadth, and the goal decides which wins.

**Say when a plan is anchored on the question's framing.** Your S4 verdict. Some
seeds arrive with a conclusion embedded — "does this portend durable revenue" —
and a plan that sets out to confirm it has never asked the question. Distinct
from missing a falsifier: a plan can have one and still be testing the wrong
proposition.

**Say when a plan is fine.** Sound plans are what make precision measurable.
Without them a model that manufactures five objections per plan scores perfectly
on recall and its noise is invisible.

## Where the tenets conflict

Several pull against each other by design — rigor against speed, breadth against
firm fit, thoroughness against Type I error. `TENETS.md` § Resolving conflicts
gives the precedence rules, but where you feel the tension, **say how you
resolved it** in `preference_rationale`. That reasoning is the most valuable
thing your gold carries: it's the judgment no model can infer from the tenets
alone.

## If you disagree with my construction

Say so. If your preference contradicts my design intent, that's a signal the
pair's contrast is weaker than I thought — information about item quality, not
something to reconcile away.
