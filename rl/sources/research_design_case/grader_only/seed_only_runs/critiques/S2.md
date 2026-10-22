# S2 — critique (claude-code subagent)

> Do monthly active users on a company's client-facing portal predict ARR for SaaS companies on seat-based pricing?

## Verdict

This is a well-built plan by a careful analyst. The craft is top-decile: unique visitors not visits, mean not sum, weekday adjustment, fiscal-calendar matching, point-in-time consensus dated ten days pre-print, the `www.` placebo, leave-one-firm-out, pre-registration, and an ending that refuses to promise a factor. I am not going to manufacture objections about any of that.

I am going to reject the project as scoped anyway, for five reasons, in order of how badly they hurt. Two of them (universe arithmetic, survivorship) mean the study cannot be run at the stated size. One (dependent variable) means the headline test is aimed at the wrong quantity. One (the control cohort) means the result the plan calls "the headline" identifies something other than pricing model. One (the success criteria) means the plan commits to a verdict on data it has already admitted is contaminated.

Fund the cheap version at the bottom instead. It is two weeks and roughly $10k of data, and it answers the go/no-go question the four-week version defers to week three.

---

## 1. The universe screens do not intersect to 35–50 names. Closer to 12.

The plan estimates 35–50 seat names and treats that as the working sample. Walk the funnel it actually specifies, in its own order:

- ~120 app software names above $1bn.
- ≥60% of revenue from seat-priced SKUs: call it 55.
- Browser-primary (screen two, which the plan itself says "kills the study if applied honestly"): call it 40.
- **Tenant-per-subdomain architecture.** This is the one the plan misses, and it is the killer. The plan lists `*.atlassian.net` casually alongside `app.asana.com` as if both are one series. They are not. Atlassian, Zendesk, Freshworks, ServiceNow, Salesforce (`*.lightning.force.com`, `*.my.salesforce.com`), Monday (`*.monday.com`) and most of the enterprise cohort give every customer its own hostname. No web panel will aggregate an unbounded wildcard into a single subdomain series, and each individual tenant sits three orders of magnitude below any reporting floor. You either cannot measure these names, or you fall back to the root domain — which reintroduces the `www.` marketing traffic the plan correctly says destroys the study. Cut to ~25.
- Panel floor of 50k monthly uniques with 24 unbroken months: portal subdomains are far smaller than marketing sites. Cut to ~18.
- Then the freemium confound (section 6 below) pushes you toward sales-led enterprise — which is precisely the tenant-subdomain population you just lost.

The compounding trap is the point: the freemium problem pushes you to enterprise names, and the domain architecture makes enterprise names unmeasurable. What survives is a small set of mid-cap, single-portal, browser-primary apps — Asana, Smartsheet, HubSpot, DocuSign, Bill, Box, a handful more. Twelve to fifteen names, not fifty.

**Fix:** move domain resolvability into screen one, not into "Data." Before anything else, ask the vendor for the actual subdomain series list and the coverage history for your candidate portals. This is a one-week, pre-contract question and it sets the entire scope of the project. If the answer is twelve names, that is a different project and you should know that in week one, not week two.

## 2. Survivorship, and it destroys the exact result the plan expects to find.

"Start from US- and Israel-listed application software companies with a market cap above $1bn" — as of when? If as of today, the universe silently excludes every name taken private or acquired over the sample: Anaplan, Coupa, Zendesk, Avalara, Medallia, Sumo Logic, Momentive, New Relic, Alteryx, Everbridge, Smartsheet itself. That is a large share of mid-cap seat-based SaaS, and it is disproportionately the *weak* names — companies bought cheap after growth rolled over. The rejection log will not catch them because they never enter the screen.

Now overlay the plan's own stated prior: the effect is asymmetric, usage collapse predicts churn sharply, the deliverable is a downside screen. The downside cases are the ones the survivorship filter removed. The plan's most likely product rests on the most biased part of its sample.

**Fix:** build the universe from point-in-time constituency each quarter (index membership or Compustat active-at-date), carry names to delisting, and treat the delisting quarter as a terminal observation rather than a gap. Non-negotiable given what this signal is for.

## 3. The dependent variable is mostly not ARR, and the horizon logic is backwards because of it.

"ARR and ARR-proxy from company IR disclosures where given, otherwise quarterly subscription revenue" gets one clause and deserves a section. Two problems.

First, most of the sample will be on subscription revenue, which is ratable — a smoothed, twelve-month-trailing shadow of ARR. Revenue at *t+1* is largely already contracted and already being recognized from bookings made one to four quarters ago. A signal about *seat-expansion decisions* has almost no room to move it. So the specification is biased toward null at t+1 and t+2 by construction.

Second, and worse, the plan's horizon interpretation inverts under this DV: "a signal that only works at t+1 is probably just picking up the quarter's already-booked seats; a signal that persists to t+3 and t+4 is a genuine leading indicator." With ratable revenue as the DV, *t+1 is the most mechanically pre-booked horizon, not the least*. You would read a correct result as a spurious one.

Third, disclosure of true ARR is endogenous: companies start disclosing it when it flatters them and quietly stop when growth turns. Your true-ARR subsample is selected on outcome.

**Fix:** pick one. Either (a) restrict to firms with a consistently disclosed ARR/cARR series and accept a smaller cross-section, or (b) make the DV *current* RPO growth or calculated billings, which sit far closer to the booking event the signal is supposed to lead. Option (b) is better and the plan already has cRPO in the dataset — it is currently sitting on the right-hand side as a control when it should probably be on the left.

## 4. The seat-vs-consumption interaction — the stated headline — does not identify pricing model.

The control cohort is Snowflake, Datadog, Confluent, MongoDB, Twilio, Cloudflare, Fastly. These differ from the treatment cohort on pricing model, yes — and also on being developer/infrastructure rather than business-application, on being machine-consumed rather than human-consumed, on cohort age and IPO vintage, and most importantly on *whether the browser is where the product is used at all*. Snowflake revenue comes from warehouse compute; Snowsight sessions by a dozen data engineers are irrelevant to it.

So the interaction will very likely come out significant with the expected sign — for a mechanical reason (their product isn't consumed in a browser) that has nothing to do with per-seat pricing. The plan would then bank it as evidence of a seat-expansion mechanism. This is the centerpiece of the study and it is confounded.

**Fix, and this is the best available:** the plan already has the right control group and has demoted it. Klaviyo (per contact), Samsara (per device), Procore (construction volume) are browser-primary business applications, human-operated, sold to similar buyers, where the *unit of pricing is not a person*. That is a clean contrast on pricing unit holding usage-modality fixed. Promote the entity-priced cohort to primary control; demote consumption to a secondary sanity check. Better still, add within-firm identification where available — firms that migrated pricing model, or firms with both (HubSpot's seats vs. contacts).

## 5. Pre-registered success criteria that cannot be evaluated on the data you have.

The plan states honestly that Similarweb restates history on re-weighting, that point-in-time vintages are unavailable pre-2024, and that the historical backtest is therefore "contaminated by an unknown amount of restatement bias." Correct, and rare to see admitted.

It then defines four hard pass/fail criteria — DK *t* > 3, +3pp out-of-sample R², Diebold-Mariano at 5%, interaction at 5% — all computed on that contaminated history, and schedules the verdict for week four. You cannot pre-commit to a decision rule and then apply it to data you have already declared unreliable. One of the two has to give.

Related inference problem: the signal is cross-sectionally demeaned within calendar quarter *and* the specification carries calendar-quarter fixed effects. The common time component is removed twice; identification is purely within-quarter cross-sectional. With ~15 firms per quarter after screens 1–2, "t > 3" is being read off far fewer effective independent observations than 900 firm-quarters suggests, and Driscoll-Kraay is now correcting for a dependence you already double-removed. The randomization placebo (1,000 reassignments) is the right way to get the real null — make it the primary inference, not the third placebo.

**Fix:** split the deliverable. Week four produces a *feasibility verdict with an effect-size range*, explicitly labelled as not-investable. Freeze a live monthly snapshot from day one and pre-register the actual pass/fail for a forward walk-forward with a stated minimum of eight quarters. Say out loud that sizing is 18–24 months away.

---

## Second-order, still worth fixing

- **The IV will not work, and the plan pre-rationalizes its failure.** Multiple-indicator IV needs two noisy proxies of the *same* latent variable with *independent* errors. Similarweb web panel and Sensor Tower mobile panel measure different populations (mobile adoption has its own true component correlated with ARR through other channels), and both vendors reweight against overlapping upstream clickstream/SDK sources, so the errors are not independent either. Then: "if the IV estimate is three times the OLS estimate, that is the honest effect size." No — a 3x jump is the textbook signature of a weak or invalid instrument. Report the first-stage F, and make the disclosed-metric reliability ratio (the credible correction) primary, reported as a bounded range. Note also that the calibration subsample — Zoom, Dropbox, Box, Slack, Atlassian — is the freemium/consumer-adjacent tail, i.e. the least representative firms for the enterprise names you would apply the correction to.
- **Free tier mitigations are weaker than stated.** Hour-of-day splits at subdomain granularity are not reliably available in the standard product, and free users are business users on weekday afternoons too. Geographic weighting does not separate free from paid. This is not noise that attenuates β — for a name where 90% of measured MAU never pays, free-growth-with-weak-monetization can flip the sign. Treat freemium as an exclusion, not a robustness split.
- **Consensus absorption will be misread as decay.** The sell side has used web-traffic alt-data since roughly 2018. Post-2019 consensus partially *contains* your signal, which mechanically shrinks β and will show up in the pre/post-2021 split as alpha decay. Those two stories have very different implications and the split as designed cannot separate them.
- **Consensus coverage.** Visible Alpha line-item subscription-revenue consensus is thin for mid-caps and short-history pre-2018. If it is missing or stale for a third of firm-quarters, "incremental to consensus" quietly degrades to "correlated with growth." Report coverage rate per firm-quarter as a first-class diagnostic.
- **Break detection must precede seasonal adjustment**, and the 30% MoM threshold misses the common case — a gradual six-month cutover, which reads as a genuine trend. Pair every flag with a search for a compensating rise on a candidate new hostname, and re-verify the domain map quarterly, not annually.
- **The tertile backtest cannot settle anything.** Thirteen names a side over ~35 quarters, returns dominated by earnings-day dispersion: the standard error on the mean will swallow any plausible effect. It cannot confirm or kill. Replace with a pooled event-study regression of earnings-day return on the demeaned signal — same information, a week cheaper, and honest about what it can support. 30bp round-trip is also light for a five-day hold around earnings in $1–5bn names.
- **Demean against an external universe**, not the estimation sample. Demeaning within the sample makes the seat and control cohorts' signals mechanically sum to zero each quarter, which biases the interaction.
- **Schedule is off by ~3x.** Hand pricing classification across 120 companies via Wayback snapshots at 40 quarter-ends, plus trial-account domain mapping for each, is not "two days" — it is most of the four weeks for one analyst. With a $250–500k annual data stack (Similarweb Investor Intelligence at subdomain grain, Sensor Tower, Visible Alpha, Revelio) for a stated deliverable of "a per-name dashboard," the budget conversation has to happen before week one, not after.

---

## What I would actually fund

The idea is not novel — web-traffic alt-data has been traded for the better part of a decade and Similarweb sells an investor product built on exactly this premise. What is potentially differentiated is narrower than the plan's framing: **portal usage decay as a downside screen on sales-led, seat-priced, single-portal names.** That narrow claim is worth two weeks, not four, and it should be gated on a test the plan currently buries in week two.

Two weeks, ~$10k of one-off historical data extract (vendors sell these; you do not need the six-figure license to answer this):

1. **Days 1–3: domain resolvability.** Ask the vendor which of your candidate portal subdomains actually have a standalone series with 24+ months of coverage. This alone determines whether the project has 12 names or 40. Kill if under 10.
2. **Days 4–8: the measurement-validity gate, which is the real go/no-go.** For every firm that discloses a customer, seat, or user count, regress Δ4 disclosed metric on Δ4 panel MAU *contemporaneously*. If panel MAU does not track the disclosed quantity in the same quarter, there is no leading indicator to find — the measurement has failed before the timing question is even asked. Pre-commit a threshold. My prior is this is where it dies, and it costs three days to learn.
3. **Days 9–14: one chart.** For the ~12 surviving names, scatter demeaned Δ4 MAU against next-quarter subscription-revenue (or cRPO) surprise versus consensus, with the quintile/asymmetry cut overlaid. Roughly 240 observations of the cleanest possible data. If nothing is visible there, the fifty-name version will not find it either — it will only find enough researcher degrees of freedom to manufacture it.

If steps 2 and 3 both clear, then buy the license, fix survivorship and the DV, swap the control cohort to entity-priced, freeze a live snapshot, and run the full study as an 10–12 week project ending in a forward test — not a four-week project ending in a verdict.

