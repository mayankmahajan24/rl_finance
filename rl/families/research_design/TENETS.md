# Judging tenets

The standard the discriminator is asked to apply. Both evaluator prompts are
operational forms of this file, and the gold labeller judges on the same basis.

Thirteen tenets in five groups, ordered by **when in a review you apply them**:

| Group | Tenets | Question |
|---|---|---|
| **A — Frame** | 1–3 | What is this for, who is asking, and where is the edge? |
| **B — Design** | 4–8 | Is the design right for that frame? |
| **C — Execution** | 9–10 | Is the work sequenced and instrumented sensibly? |
| **D — Honesty** | 11–12 | Would it notice being wrong? |
| **E — The review itself** | 13 | Is each objection earned? |

Group A comes first and is not optional. Tenets 4–12 cannot be assessed until you
know the goal and the audience, because most are **conditional on those two
answers** — the same plan is right for one firm and wrong for another.

Several tenets pull against each other by design. That is not sloppiness: a plan
cannot maximize all of them, and choosing well is the judgment being tested.
**§ Resolving conflicts** at the end gives the precedence rules; use it rather
than silently picking a side.

---

# Group A — Establish the frame

## 1. Understand the actual goal before judging anything

Scope, complexity, and the standard of proof all follow from what the analysis is
*for*. Establish which of these it is first:

| Goal | What it implies |
|---|---|
| **One KPI for one company**, no generalization | Don't build a cross-sectional panel. Sample size is one. Validation is out-of-time on that name; the bar is decision-usefulness, not significance. |
| **A broad market effect** | Generalization is the point. Cross-section, multiple regimes, standard controls, and the effect must survive them. |
| **A mechanism** | The causal story is the object. Test whether it holds, not merely whether the correlation exists. Confounders matter more than fit. |
| **Blind fit, tested out of sample** (stat arb) | No mechanism required — but out-of-sample discipline, costs, capacity and decay become the entire evaluation, and in-sample fit means nothing. |
| **A capability build** (can we even measure X?) | Success is identification quality, not P&L. Needs external ground truth and an honest abstain option. |

The common failure is answering a different question than the one asked: a
generalizable cross-sectional study when the analyst wanted a call on one name,
or a single-name narrative when the question was whether an effect exists
broadly.

**Mismatched goal is blocking.** Not a matter of degree — the work will not be
usable however well executed.

## 2. Fit the plan to the firm and the person

A plan is not good or bad in the abstract. It is good or bad *for someone*.

| | Systematic / quant | Small fundamental |
|---|---|---|
| Can they build it? | Tick data, own execution, production ML — yes | Bloomberg and Excel; a ten-year TAQ build is not happening |
| Output | A signal that survives costs and has capacity | A view on one name held for years |
| What kills it | Crowding, decay, transaction costs, capacity | Being wrong about the business |
| Horizon | Days to weeks | Quarters to years |
| Who reads it | A research committee that will replicate it | A PM defending it to an IC |

### Capability cuts both ways

Over-estimating a firm's capacity is the obvious error — proposing infrastructure
it cannot build, staff or maintain. **Under-estimating is equally real**:
proposing a laborious manual workaround for something the firm's market-data
tooling already does, or budgeting weeks to assemble data they already license.
Assume a professional investment firm has the standard tooling of its type unless
told otherwise. Wasting an analyst on work the terminal does in an afternoon is a
defect, not caution.

### Which error costs more here?

Exhaustiveness is a virtue, but not at the expense of an inflated **Type I error
rate**. Which error dominates is set by the payoff structure, and it differs by
firm:

| Setting | Costlier error | Why |
|---|---|---|
| **Concentrated, explicit loss, asymmetric downside** — PE, concentrated long-only, most fundamental books | **Type I** (acting on something that isn't real) | A bad position in a 25-name book cannot be diversified away. Missing a good idea is recoverable; there are other ideas |
| **Capped downside, unbounded upside** — venture, deep-value optionality | **Type II** (missing something real) | You lose 1× on a mistake and forgo 100× on a miss. Passing on the winner is the expensive error |
| **Symmetric payoff with breadth** — most quant strategies | **Type II**, usually | A false positive is diluted across hundreds of small bets and absorbed by risk management; a missed alpha source is a permanent opportunity cost |

This is not a licence to be sloppy in either direction — it sets **where the
burden of proof sits**:

- **Type I dominant** → the plan should be exhaustive about ruling out false
  positives, and demanding more evidence before acting is correct. Here a
  conservative plan is the right plan.
- **Type II dominant** → a plan so strict it kills real signals is the failure.
  Excessive gating, over-tight thresholds and serial robustness checks are costs,
  not virtues, because each one raises the chance of discarding something real.

**Judge the plan's posture against the setting, not against a fixed standard.**
The same rigor that is prudent for a concentrated fundamental book is
over-engineering for a diversified quant one, and the same speed that is correct
for a breadth strategy is recklessness for a ten-position portfolio.

### Match statistical sophistication to the audience

A method's value includes **whether the people receiving it can evaluate and
defend it**. A technique nobody at the firm can assess does not produce
conviction there, however correct it is — it produces a result they must take on
faith, and they won't.

No private equity firm is going to understand or believe a Hungarian algorithm.
Nor optimal transport, spectral clustering, or a Bayesian hierarchical model with
a hand-tuned prior. That is not a comment on their intelligence; it is that the
method cannot be checked by the people whose money is at risk, so it cannot carry
the decision. The mirror error is equally real: plain OLS with no treatment of
autocorrelation, presented to a systematic firm, reads as naive and is rejected
on the first question.

| Failure | What it looks like |
|---|---|
| **Too sophisticated for the audience** | The method needs explaining before the result can be explained. The audience cannot evaluate it, so cannot own the decision |
| **Too naive for the audience** | Ignores issues the firm's researchers spot immediately; credibility lost on the first question |

**If a sophisticated method is genuinely necessary**, the plan owes a *simple
corroborating check the audience can verify themselves* — a hand-checked sample,
a crude version that directionally agrees, a result reproducing on a subset they
can inspect. Sophisticated method plus simple confirmation is defensible;
sophisticated method alone, to an audience that cannot assess it, is not.

### When the context isn't given, infer it

If nobody says who is asking, ask **what kind of firm most likely asks this
question**. The question carries the signature, in its subject matter and its
vocabulary:

- An HFT firm would not ask whether earnings-call sentiment predicts
  peer-relative outperformance. That is a weeks-to-quarters question.
- A slow long-only manager would not be preoccupied with transaction costs. They
  turn a position over every few years.
- A fundamental fund would not speak of "signal alpha decay." That vocabulary
  belongs to someone running systematic books.

Infer the asker, state the inference, design for them. Two failures follow from
getting it wrong: **wrong-firm concerns** (latency and capacity on a single-name
fundamental question; indifference to cost and crowding on a systematic one) and
**unstated assumption** (silently designing for one kind of shop, so a reader
discovers halfway through that the plan presumes infrastructure they lack).

## 3. Establish the variant view — where is the edge?

In investing, the reason a piece of work makes money is that it produces a view
**different from what the market already believes**, or acts on the same view
faster. Benchmark against what we and the world already know. A finding that is
true, well-evidenced, and already consensus has produced nothing.

So before judging how a plan is built, ask what its edge would be if it worked:

| Edge | What it means | What the plan owes |
|---|---|---|
| **Variant view** | We conclude something different from consensus | Establish what consensus *is*, then show where this diverges and why the market has it wrong |
| **Speed** | Same view, reached sooner — the arbitrage case | Show the latency advantage is real and durable, and that the trade is still available when the work lands |
| **Better measurement** | Same question, a cleaner instrument | Show the measurement is genuinely better, not merely different |
| **None established** | The plan never says what is incremental | **This is the defect.** However rigorous, it is confirming what is already priced |

This applies fundamentally and quantitatively, in the same way with different
vocabulary:

- **Fundamental** — diff the thesis against sell-side consensus, company
  disclosure, and buy-side positioning. If the conclusion is what the last three
  broker notes already said, the work is confirmatory, not investable.
- **Quantitative** — the equivalent of consensus is **crowding**. A factor
  everyone has already found is in everyone's book, and its historical Sharpe is
  not available going forward. Establish whether the signal is known, published,
  or sold by a vendor before valuing it.

The failure to look for is a plan that measures something real and never asks
whether anyone else already knows it. That work can be flawless and still worth
nothing — which makes this a **blocking** issue, not a refinement: no edge means
no trade, whatever the statistics say.

> Not every question needs an edge. A **capability build** ("can we identify
> these institutions at all?") is infrastructure, and demanding a variant view of
> it is a category error. Use tenet 1's goal to decide whether this applies.

---

# Group B — Is the design right for that frame

## 4. Simplest thing that could resolve the question, first

Start with the simplest method before adding layers and gates. Simpler designs
are more defensible internally and hold up better out of sample.

- Every added stage, control, gate or robustness layer must earn its place.
  Machinery is not free: it costs time, adds researcher degrees of freedom, and
  makes the result harder to defend and easier to overfit.
- Prefer the estimator a reviewer can check by hand over one needing a paragraph
  of justification, unless the simple one is demonstrably wrong here.

Sophistication is a virtue only once the simple version has been tried and
demonstrably fails. Reaching for the complex method first is a defect.

> Sequencing — which test goes first — is tenet 9. This tenet is about the
> *complexity of the method*, not the order of the steps.

## 5. Measure the actual target, and keep the measure meaningful

If the question is stock outperformance, the deliverable is stock outperformance
— not the fundamental that plausibly drives it. Forecasting revenue is easier
than forecasting the stock, and substituting the first for the second answers a
different, simpler question. That gap is where most alpha claims die: the
fundamental can be right and the stock still not move, because it was already
priced.

The same substitution happens at the variable level. A panel measures
*deposits*; the thesis is about *betting activity*. A portal measures *logins*;
the thesis is about *paid seats*.

- **Name the target explicitly**, then confirm every step measures it rather than
  something upstream that correlates with it.
- **If a proxy is unavoidable**, validating the proxy-to-target link is its own
  step, not an assumption. An unvalidated proxy makes every downstream result
  uninterpretable however well executed.

Predicting the fundamental is legitimate when that is what was asked; it is a
defect when it substitutes for what was asked.

### The measure must stay valid across the whole sample

Choosing the right measure once is not enough — it has to remain meaningful for
every observation the study uses. Two failures, both common and both easy to miss
because the metric looks fine on average:

- **The measure breaks for part of the sample.** A multiple with a negative
  denominator is not a large number, it is meaningless — companies crossing from
  negative to positive earnings produce a discontinuity that will dominate any
  cross-sectional result unless handled explicitly. Same for ratios near zero,
  log transforms of non-positive values, and percentage changes off a small base.
- **The measure changes meaning over the sample.** Which metric the market
  actually prices moves with the company's lifecycle: a high-growth,
  high-gross-margin business is valued on revenue, the same business at maturity
  on EBITDA. A panel that applies one multiple across both regimes is measuring
  two different things and calling them one.

The plan should say what it does at these boundaries. Silently winsorizing,
dropping negatives, or never mentioning them is a defect — the excluded
observations are usually the interesting ones.

## 6. Match the horizon to the phenomenon, not the data frequency

| Failure | Example |
|---|---|
| **Horizon too long** | Order-flow effects analysed daily when they persist for minutes — the signal is gone before the first observation |
| **Horizon too short** | Contract renegotiations or pricing changes measured before flow-through timing lets them appear |

Timing of flow-through is part of this: when a change reaches revenue, when it
reaches margin, how long the lag runs. A plan that finds the right economic
effect in the wrong period concludes, wrongly, that it is not there.

## 7. Match the evidence standard to what the setting can support

Statistical significance is one route to conviction, not the only one, and often
it is unavailable. **A dependent variable can be statistically indefensible and
still useful.**

Identifying three institutions from external data will never yield
cross-sectional significance. But conviction is still available: look across
historical quarters and ask whether the method predicts the trend consistently on
those same three. Repeated observation of a few units substitutes for a wide
cross-section of one observation each.

At low N or constrained complexity, legitimate sources of conviction:

- **Consistency over time** — same units, repeatedly, across quarters or regimes
- **Sign and rank stability** — ordering holds even when magnitudes are noisy
- **Out-of-time replication** — fit early periods, check later ones, same small set
- **Agreement across independent cuts** — different sources, same direction
- **Magnitude plausibility** against an external anchor

Both directions fail:

| Failure | What it looks like |
|---|---|
| **Over-demanding** | Requiring a t-statistic the setting cannot produce; or manufacturing cross-sectional N by pooling units that should not be pooled, just to have something to test |
| **Under-specifying** | Low N with no stated way to judge the result. "We will look at the output and see" is not a design |

### Prefer specific evidence over general when it exists

Company-specific history beats a cross-sectional base rate **when the company has
its own record**. Generalize only where it does not — a firm with a dozen prior
comparable events should be judged on those, not on an industry average that
washes out exactly what makes it different. The cross-section is the fallback,
not the default.

This cuts against tenet 8's breadth logic, deliberately: breadth is right for
establishing that an effect exists across a universe, specificity is right for
calling one situation. Which applies follows from tenet 1's goal.

Where the bar sits is set by tenet 2's error asymmetry: a Type-I-dominant setting
justifies demanding more before acting, a Type-II-dominant one makes an
over-tight bar a real cost. Feasibility (this tenet) and payoff structure (tenet
2) are separate questions and both bind.

Do not treat a missing significance test as an automatic defect. **Ask first
whether significance was ever available.** If it was, its absence is a real gap.
If it was not, the question is whether the plan built another credible way to
tell success from failure — and if not, *that* is the defect.

## 8. Breadth over strength — and test where it should NOT work

> **Applies only when tenet 1 returned `broad market effect` or `blind fit`.**
> For single-name work, or a concentrated long-only or event-driven firm, breadth
> logic does not apply and demanding it is the wrong-firm error of tenet 2.

For strategies running at scale, a modest edge across thousands of securities
spanning equities, rates, FX and commodities beats a strong edge in one sleeve.
Breadth converts a small per-bet advantage into a reliable aggregate one. Be
sceptical of a plan optimizing the strength of an effect in one market rather
than testing whether a weaker version survives everywhere.

**State where the signal should NOT work, and test there.** This is the sharpest
available check on whether a mechanism is real:

| Result | Meaning |
|---|---|
| Works **everywhere**, including where the mechanism cannot apply | **Suspicious** — it is not what the story says. A retail-flow signal that works in institution-only markets was never measuring retail flow |
| Works **only in the original sample** | **Fragile** — sample-specific, likely mined |

A plan with no negative controls cannot distinguish a real mechanism from a
well-fit artifact, however strong its headline result.

---

# Group C — Execution

## 9. Sequence for information — get to 60 before going to 99

**Earlier and 70% confident is often worth more than much later and 99%
confident.** A view arriving while the position can still be taken beats a better
view arriving after.

### Order steps by uncertainty removed per unit cost

**Entropy-reducing first.** Check the most glaring, basic thing before the subtle
one; test the unlikely second-order confounder late or not at all. Confirm the
data contains what you think before modelling it. Check sign and rough magnitude
before estimating precisely. Rule out the obvious confounder before the exotic
one.

The signature failure: a plan opening with clustering adjustments and alternative
estimators while "does this variable measure what it is named after" sits
untouched in stage three. Backwards, however good each step is.

**Completeness is a virtue; flow is a judgment.** A thorough list of checks is
not the same as a well-ordered one.

### The flow should be adaptive, and say so

The right next step depends on what the last one returned. A plan reading as a
fixed pipeline — every stage scheduled regardless of intermediate results — is a
task list, not a research plan. Credit plans stating what they do differently
depending on what comes back: which branch is abandoned if the first check fails,
which work becomes unnecessary if the effect is obvious, which extra step is
warranted only if the result is marginal.

### Spend

New data licences, compute, headcount and analyst weeks are real costs. Each
should be justified by what it unlocks and **not committed before the cheap
version has shown the idea is worth pursuing**. Buying a dataset to run a test a
free proxy could have killed is a defect, not thoroughness.

**Buying is not analysing.** Watch for a plan substituting a purchase — a vendor
dataset, a licensed signal, a consultant's study — for the analytical work the
question asked for.

### A fast kill is a correct answer

If an idea is structurally doomed — cannot work without modification, the data
cannot answer it, the information is already priced — establishing that quickly
is a **good result**. A plan reaching that conclusion in a week has delivered
more than one reaching it in three months, and far more than one that never
checks. Credit a pre-committed kill criterion placed early; penalize
infrastructure built before the idea is shown to work at all.

## 10. Assume AI execution — human checkpoints, calibrated explainability

Assume AI does the heavy lifting. Compute, breadth and the number of variants
tried get cheap; **human attention becomes the binding constraint**. Spend AI
effort freely, spend human review carefully, structure the work so a person can
verify it quickly.

### Explainability is calibrated, not maximized

A pitch for a company launching a new product must be explainable end to end — a
PM will defend it to an IC, and an untraceable conclusion is useless however
accurate. A model predicting prices over the next fifty milliseconds is not
explainable and does not need to be.

| Failure | What it looks like |
|---|---|
| **Over-demanding** | Insisting on an interpretable model where the goal is blind out-of-sample fit; rejecting a method purely for being a black box when nobody needs to explain it |
| **Under-delivering** | A conclusion someone must defend resting on a pipeline nobody can inspect |

Set the bar from tenet 1: single-name calls, mechanism tests and anything going
to an IC need high explainability; blind fit-and-test signals need almost none.

> Distinct from tenet 2's sophistication point: that is whether the audience can
> evaluate the *method*; this is whether anyone can trace the *result*. A method
> can be simple and the pipeline still opaque.

### Intermediate outputs that expose garbage-in-garbage-out

Name artifacts a human can actually look at, early enough to matter: the
distribution of the key input, a sample of matched or classified records
eyeballed by hand, coverage and missingness by period, the top and bottom decile
of whatever was constructed, worked examples traced end to end. Cheap for an AI
to produce, and the difference between a pipeline that is trusted and one that is
merely finished.

**The executor should inspect these and prune early.** A plan producing nothing
inspectable until the end cannot be steered; by the time it is wrong the cost is
sunk. Credit plans stating what will be checked, when, and what result causes a
branch to be abandoned.

---

# Group D — Intellectual honesty

## 11. Always ask what would make this wrong

Every plan needs a real falsifier and genuine thought about the other side.

This is not a pitfalls section. Listing ways the *method* could break is hygiene.
What is required is engaging the possibility that the **conclusion** is wrong:

- What specific result would make us abandon this? Named in advance, not
  discovered afterwards.
- If the hypothesis is false, what would we most likely see instead — and would
  this design distinguish that from the case where it is true?
- Who is taking the other side, and why is that not obviously stupid? If nobody
  is, the effect is probably priced or absent.
- **Is the variant view still intact?** Re-check tenet 3 here: if the answer
  turns out to be what consensus already believes, there was never a trade.

**Do not inherit the question's framing.** Several questions arrive with a
conclusion already embedded — "does this portend durable revenue", "is this a
short". Accepting that frame and setting out to confirm it is the failure; the
embedded claim is the thing to test, not the premise to work from. A plan that
is *anchored* on the framing will look rigorous while never having asked the
question. This is distinct from missing a falsifier: the plan can have one and
still be testing the wrong proposition.

**Absence of a stated falsifier is blocking**, not a stylistic gap: without one,
every outcome gets rationalized into support.

## 12. Do not invent economics — stay inside the question as framed

Do not assume how much money something will make without evidence.

The failure reads as ambition: a Sharpe ratio, a basis-point alpha, a capacity
number, a market size, or a position size asserted as though derived when nothing
in the plan produces it. **A speculative magnitude is worse than none**, because
it anchors sizing, staffing and approval on a number that was made up.

Watch for a narrow real observation inflated into an economic claim it cannot
support: a single quarter annualized into a run-rate, a within-sample spread
quoted as expected return, a panel result scaled to a firmwide allocation. The
observation may be sound; the extrapolation is invented.

**Stay inside the framing.** If the question is whether X predicts Y, the
deliverable is whether X predicts Y — not a capital allocation.

The correct posture when magnitude is unknown is to say so. "We cannot size this
until the first result is in, and here is what would let us" is stronger than a
confident fabricated number.

---

# Group E — The review itself

## 13. Standard objections must earn their place in this context

A canonical concern is not automatically a real one. Survivorship bias,
look-ahead, multiple testing, minimum sample size, unmodelled confounders — each
is genuine *somewhere*, which is exactly what makes reciting them convincing.
**Before raising one, show why it bites this design.**

Failures of this kind, all of which read as rigor:

- Rejecting a study for survivorship bias when the universe is point-in-time and
  no selection on survival occurs.
- Rejecting a 12-name universe for insufficient sample when the analysis is
  within-name over time and never claimed cross-sectional inference.
- Demanding a statistical test the data cannot support, then treating its absence
  as the finding.
- Setting a minimum event count far above what the question needs, killing work a
  smaller sample would have settled.
- Elaborating tertiary confounders while a first-order measurement problem goes
  unmentioned.

Every objection carries its own justification: *this design, this data, this
claim, breaks in this way*. An objection reading identically against any plan in
the asset class has not been earned. The cost is not just noise — a reviewer
raising eight objections of which three are real has made the three harder to
find, and spent the reader's attention, the scarce resource.

Missing a real problem is a failure; manufacturing an unreal one is also a
failure, and the second is more corrosive because it is harder to detect.

### The review has its own error rate

Exhaustiveness in a critique is itself a **Type I generator**. Every objection
raised is a chance to reject a plan that would have worked, and a review that
lists eight concerns to be thorough has inflated its own false-positive rate — it
will kill good work.

The same asymmetry from tenet 2 applies to the review:

- **Where Type I dominates for the firm** (concentrated, explicit loss), a
  demanding review is aligned with the payoff structure. Raise the bar.
- **Where Type II dominates** (breadth, capped downside), an exhaustive critique
  is actively harmful — it discards real opportunities in a setting built to
  absorb individual mistakes. Report only what would change the decision.

Completeness is not the goal. A review naming the two or three things that would
change what the reader does beats one naming ten, even when all ten are
defensible.

---

# Resolving conflicts

These tenets are not independent, and a plan cannot maximize all of them. Where
two pull apart, resolve in this order rather than picking a side silently.

### Rigor (7, 8) vs speed (4, 9)

- **If the idea can be killed cheaply** → speed wins. Run the cheap decisive test
  first; rigor spent before that point is wasted if the answer is no.
- **If the cheap version has passed and capital will be committed** → rigor wins.
  This is where extra validation earns its cost.
- **Never** let a demand for rigor prevent a fast kill from happening at all.

### Breadth (8) vs firm fit (2)

- **If goal is `broad market effect` or `blind fit`** → breadth applies; absence
  of negative controls is a real gap.
- **If goal is `one KPI`, `mechanism`, or the firm is concentrated / event-driven**
  → breadth does not apply. Demanding cross-asset coverage here is itself the
  defect. Tenet 2 wins.

### Sophistication (2) vs correctness (4, 7)

When the statistically correct method exceeds what the audience can evaluate:

- **If a simpler method is adequate** → use it, note the limitation.
- **If the sophisticated method is genuinely necessary** → use it *and* supply a
  simple corroborating check the audience can verify. Both, not either.
- **Never** present a method the audience cannot assess and expect it to carry a
  decision on its own.

### Explainability (10) vs performance (1)

- **If output goes to an IC, or is a single-name call** → explainability required;
  an opaque pipeline is a real defect.
- **If goal is `blind fit`** → explainability not required, and demanding it is
  the error.

### Checkpoints (10) vs speed (9)

Rarely a genuine conflict: checkpoints are cheap under AI execution and pay for
themselves by pruning toxic branches early. **If a checkpoint costs more than the
branch it protects**, drop it — the only case where speed wins.

### Completeness vs ordering (9)

Ordering wins. A complete but badly ordered plan is worse than an incomplete
well-ordered one, because the second produces a usable answer sooner and can be
extended. Never credit a long list of checks without asking about their sequence.

### Specific evidence (7) vs breadth (8)

- **If the goal is a call on one situation** → the company's own history wins.
  An industry base rate washes out what makes this case different, and demanding
  cross-sectional coverage is the wrong-firm error.
- **If the goal is establishing an effect exists** → breadth wins. A single
  company's record cannot support a general claim however rich it is.
- **If the specific record is thin or absent** → fall back to the cross-section,
  and say that is what you are doing.

### Exhaustiveness vs Type I error (13, 2)

Set by the firm's payoff structure, not by preference:

- **If the setting is Type I dominant** (concentrated, explicit loss, asymmetric
  downside — PE, concentrated long-only) → exhaustiveness is warranted. Raising
  the evidential bar is correct, and a demanding review is aligned with the cost
  of being wrong.
- **If the setting is Type II dominant** (capped downside and unbounded upside,
  or symmetric payoff with breadth — venture, most quant books) → exhaustiveness
  is a cost. Every additional gate raises the chance of discarding something
  real, and a plan that is too strict fails in the direction that actually
  matters here.
- **Never** apply a fixed standard of rigor across both. That is the error the
  asymmetry exists to prevent.

### Finding problems vs earned objections (13)

Recall and precision both matter; neither dominates. **When unsure whether a
concern applies, state it conditionally** — "if the universe is not
point-in-time, survivorship matters here" — rather than asserting it flatly or
omitting it. That preserves the signal without spending the reader's attention on
a concern that may not bite.
