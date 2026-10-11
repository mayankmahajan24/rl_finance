# Seed idea catalog

Seeds for Part 1. **The graded object is the plan, not the seed.** Seed quality is instrumental — it sets what a good plan on that seed looks like:

| Seed bucket | A good plan… | A plausible-bad plan… |
|---|---|---|
| obviously good | executes cleanly — right identification, right confounders | overcomplicates, or pads with ritual caveats |
| subtly flawed | surfaces the flaw and builds a test that would detect it | competently executes the wrong thing *(the dangerous case)* |
| obviously flawed | kills it fast or reframes it into an answerable question | dutifully scopes a full research program for a dead idea |

That third row is an underrated axis: knowing when to say "this is a two-week feasibility, not a project" is a senior behavior, and a model that always produces a full research program fails it silently.

Per-seed fields below: **good plan must** (the discriminating requirements) and **bad plan** (how a capable analyst still gets it wrong). These are also the raw material for Part 2 — `plan_A` / `plan_B` and the gold critiques come straight out of them.

Style test: does the work output a **view on a specific situation** (fundamental) or a **signal measured across a universe** (quant)? Method isn't the discriminator — S1 is quantitative in method but the deliverable is a view on one name.

---

## Shortlist — the working 10

5 quant / 5 fundamental · 3 good / 3 obviously flawed / 4 subtly flawed.

**S1 and S2 are the Part 0 pair** — the sound idea and the plausible-but-dead one I wrote before touching Claude (`part0/`). They lead the list so the appendix and the seed table line up.

| # | Seed | Style | Bucket | Discriminator |
|---|---|---|---|---|
| S1 | Kalshi → DraftKings substitution | fund | good | Staggered adoption + selection into treatment |
| S2 | Portal MAUs → ARR | quant | subtle | Seats contracted ≠ seats used |
| S3 | EU institution ID from txn data | quant | good | Does validation leak? Non-PnL success metric |
| S4 | Hyperscaler dropped as SPV guarantor | fund | good | Consolidation fact before strategy signal |
| S5 | Call sentiment → peer outperformance | quant | obvious flaw | Crowded; sentiment collinear with the surprise |
| S6 | N2Y CAGR revisions → re-rating | quant | obvious flaw | Near-tautological; simultaneity both directions |
| S7 | Channel checks → guidance raise | fund | obvious flaw | Published = consensus. Is it in the price? |
| S8 | Round lots → retail flow | quant | subtle | Proxy polarity is backwards |
| S9 | Shortage → LTAs → durable revenue | fund | subtle | Narrative anchoring; cycle-peak tell |
| S10 | Defensive tone on vendor renegotiation | fund | subtle | Signal confounded at source |

Failure modes named in the assignment, mapped: leaky validation → S3, S2 · anchors on management narrative → S9, S10 · misses the obvious confounder → S4, S1 · can't tell mechanism from correlation → S8, S6 · overfits the question → S5.

---

# The ten

## S1 — Kalshi adoption cannibalizing DraftKings wallet share
**fundamental · obviously good**

> Do customers who start trading on Kalshi subsequently reduce spend/activity on DraftKings? Tested on our credit-card and bank-deposit panel.

**Good plan must:**
- Treat adoption as **staggered** — cohort or stacked DiD, not a pooled pre/post on adopters. Naive two-way fixed effects with staggered timing and heterogeneous effects is biased.
- Confront **selection into treatment**: Kalshi adopters are already high-propensity speculators and may already be trending in DKNG spend. Requires pre-trend tests and controls matched on pre-period DKNG intensity, not just demographics.
- Know what the panel actually measures: **deposits, not net gaming revenue**. Reload behavior, promo credits, and withdrawals sit between the two. A user who "stops depositing" may have switched to a funding method outside the panel or churned out of the panel entirely — attrition looks identical to substitution.
- Handle **event confounds**: NFL season and March Madness drive DKNG; Kalshi adoption spikes around elections. An election-window effect is not a steady-state effect.
- State the extrapolation step: panel share of DKNG's base, and whether panel demographics resemble it.

**Bad plan:** pooled pre/post regression on adopters with no control group, deposits read as revenue, an election-quarter effect annualized into a TAM claim.

*This is the sound half of the Part 0 pair — my own write-up is in `part0/`.*

---

## S2 — Client-portal MAUs → ARR for seat-based SaaS
**quant · subtly flawed** *(seats ≠ usage)*

> Do portal MAUs predict ARR for seat-based SaaS companies?

**Good plan must:**
- Validate the **MAU → billable seats** link directly, against companies that disclose seat counts. Seat-based ARR bills on seats *contracted*; shelfware is normal, so ARR compounds on flat usage and free viewer tiers inflate MAU with no billing.
- Decompose **ARR = seats × price**. MAU is silent on the price/mix half, which carries much of the growth.
- Confirm the portal **is the product**, not an admin or billing surface.
- Handle **panel coverage**: enterprise traffic behind SSO/VPN is largely invisible to third-party panels, biasing toward the small accounts that matter least.
- Detrend or first-difference — both series trend up, so a level regression finds a relationship that is mostly common drift.
- Reconcile timing: ARR recognizes on contract, MAU moves on usage; the lead/lag is unstable.

**Bad plan:** regress reported ARR on lagged MAU in levels across SaaS names, report high R² driven by shared trend, present it as a nowcast.

*This is the flawed half of the Part 0 pair — my own write-up is `part0/plausible_but_flawed_mau_arr.md`, which deliberately commits the errors listed above.*

---

## S3 — Identifying European financial institutions from anonymized transaction data
**quant · obviously good** *(capability question, no return hypothesis)*

> Can we reliably identify EU financial institutions from transaction data using only anonymized institution IDs plus panel demographics and spend behavior?

**Good plan must:**
- Keep **identification features strictly separate from validation**. Confirming an institution guess using the same behavioral features that produced it is circular — the single most likely failure here.
- Anchor on **external ground truth**: published deposit market shares, branch/ATM footprints, national banking statistics, known payroll or benefit-payment patterns.
- Hold out **by institution, not by transaction**. A random transaction-level split leaks the same institution into train and test and inflates accuracy.
- Define the label space honestly: hundreds of institutions with a long tail, so aggregate accuracy is meaningless. Needs per-institution precision/recall and an explicit **"no match" class** — refusing to guess is a valid output.
- Address **panel bias**: opt-in panels skew young, urban, digital, which over-identifies neobanks and under-identifies regional and older institutions. Coverage is not uniform across the label space.
- Model **per country** — EU concentration structures differ sharply market to market.
- Check whether the data licence permits institution-level attribution before any of it matters.

**Bad plan:** train a classifier on all available features, report ~90% accuracy on a random transaction-level split, no external ground truth, no per-institution breakdown, no abstain option.

---

## S4 — Hyperscaler removed as guarantor on chip-maker SPV
**fundamental · obviously good**

> A hyperscaler was removed as guarantor on a new SPV with its longstanding chip manufacturer. Are they qualifying a second source and pushing risk onto their primary provider?

**Good plan must:**
- Establish the **accounting null first**. An SPV exists for ring-fenced off-balance-sheet funding, and a parent guarantee is the textbook fact pattern making the guarantor primary beneficiary of a VIE and forcing consolidation. Removal is a canonical deconsolidation move. Skipping this is misreading the instrument.
- Get a **base rate**: how often is a sponsor guarantee released as this kind of structure seasons? Without the counterfactual there is no signal.
- Note the release was **negotiated** — the chip maker and the SPV's lenders agreed. That undercuts "pushing risk onto the provider," since the provider consented.
- Test second-sourcing on **independent evidence**: foundry qualification disclosures, tape-outs, capex and prepayment terms, supply-agreement amendments, hiring.
- Name what would falsify it.

**Bad plan:** treats the guarantor change as intent, assembles a narrative from it plus press reports, no accounting null, no base rate, no independent corroboration.

---

## S5 — Earnings-call sentiment → peer-relative outperformance
**quant · obviously flawed** *(crowded)*

> Does sentiment on earnings calls predict outperformance versus peers?

**Good plan must:**
- Open by establishing **what's already known** — this is among the most mined signals in the literature and in commercial NLP products. The plan should scope decay since publication and what, if anything, is left.
- Separate sentiment from the **earnings surprise it accompanies**. Tone is mechanically correlated with the beat; without SUE and guidance controls the study measures PEAD with extra steps.
- Defend the **peer definition** — GICS sub-industry vs. business-model peers changes the answer more than the sentiment does.
- Split **prepared remarks from Q&A**; scripted language is IR-managed and carries different information.
- Plausibly conclude: two-week feasibility, not a project.

**Bad plan:** run FinBERT over transcripts, sort into quintiles, report the long-short spread as alpha. No surprise control, no peer rigor, no decay analysis.

---

## S6 — N2Y revenue/EBITDA CAGR revisions → multiple re-rating
**quant · obviously flawed** *(near-tautological)*

> Do changes in next-two-year revenue and EBITDA CAGR drive earnings-multiple re-ratings among industry peers? (N2Y = next two years, confirmed.)

**Good plan must:**
- Notice **there is no question as posed**. Multiple is definitionally a function of growth, margins, and discount rate, so "do CAGR changes move multiples" has a known answer. The plan's value is in reframing to something answerable: is the sensitivity stable across regimes, does the market over- or under-react, does re-rating lead or lag the revision.
- Handle **simultaneity** — price moves cause analyst revisions as much as the reverse. Requires event ordering or an instrument.
- Catch the **definitional circularity**: a forward multiple is computed *from* the same estimates being revised, so P/NTM-E moves mechanically when NTM EPS moves. Part of the relationship is arithmetic, not economics.

**Bad plan:** regress ΔEV/EBITDA on ΔCAGR across an industry, report a high R², present it as a finding.

---

## S7 — Positive sell-side channel checks on new logos → guidance raise → long
**fundamental · obviously flawed** *(non-edge)*

> Sell-side checks are incrementally positive on new logo wins. Should we expect a meaningful FY guidance boost at the print, and is this a long?

**Good plan must:**
- Ask **whether it's in the price** before anything else. Sell-side checks are published; the information is consensus by construction. Look at estimate revisions and price action since the notes went out.
- Separate **logo count from ACV from near-term revenue** — enterprise logos ramp over quarters, so bookings don't reach the current fiscal year.
- Treat **guidance as a policy choice**, not a mechanical output. Study this company's own cadence: do they raise in Q1, do they sandbag, what's the historical beat-and-raise pattern? A strong quarter with no raise is a common and non-bearish outcome.
- Note the sampling: channel checks are small, non-random, self-selected among partners with a book to talk.

**Bad plan:** treats the checks as proprietary information, models logos → revenue → guidance raise, sizes a long into the print.

---

## S8 — Round-lot orders as a proxy for tradable retail flow
**quant · subtly flawed** *(proxy polarity)*

> Do round-lot orders identify retail flow profitable to trade against?

**Good plan must:**
- **Challenge the proxy before using it.** The standard retail identification keys off off-exchange (TRF) prints with sub-penny price improvement; round lots skew toward institutional algo child orders. The seed's proxy may select close to the opposite population. The plan must validate against a known-good retail benchmark first — if it can't, the study is dead at step one.
- Account for **round-lot definition and reporting changes** and odd-lot dissemination rules over the sample; the microstructure meaning of "round lot" is not constant.
- Build a real **cost model** for "profitable to trade against": spread, impact, and the fact that wholesalers internalize this flow and see it first. Paper spread here is not attainable.

**Bad plan:** classify round lots as retail, compute order-flow imbalance, regress forward returns, report a Sharpe with no cost model and no proxy validation.

---

## S9 — Product shortages through next year → LTAs and durable revenue
**fundamental · subtly flawed** *(narrative anchoring)*

> A company guided to shortages lasting through next year. Does that portend more customer long-term agreements and more durable revenue?

**Good plan must:**
- **Refuse the frame.** "Portend durable revenue" is management's preferred conclusion; accepting it is the failure. Durability is the thing to test, not the premise.
- Separate **backlog from demand**: double-ordering across suppliers inflates backlog into phantom demand during shortages.
- Read the **LTA terms** — take-or-pay vs. non-binding capacity reservation, fixed vs. indexed pricing, cancellation penalties, duration. An LTA without volume commitment is a press release.
- Model the **supply response**: the shortage is itself the signal that pulls competitor capacity in, and it lands about when the LTAs mature.
- Use the **historical base rate** — prior shortage cycles in this industry and what happened to LTAs afterward. The 2021–22 semiconductor arc is the reference case.

**Bad plan:** builds revenue durability off a backlog coverage ratio, extrapolates the guided shortage window, no LTA term analysis, no supply response.

---

## S10 — Defensive tone around vendor licence renegotiation
**fundamental · subtly flawed** *(confounded at source)*

> A company went notably defensive around its annual vendor licence renegotiation. Is this a stronger near-term margin risk than communicated, or not a sign of weakening fundamentals?

**Good plan must:**
- Recognize the signal is **confounded at source**: management is expected to be guarded about any live commercial negotiation, since commenting weakens their position and may be contractually restricted. Guardedness is the baseline, not the news.
- If tone is used at all, build a **control set** of guarded-tone instances with benign outcomes. Without it there's no discriminating power.
- Pivot to **harder evidence**: the licence as a share of COGS, prior renegotiation outcomes, switching costs and vendor market power, the vendor's own pricing actions and commentary, contract disclosure.
- Get the **direction right** — the company is the *buyer*, so this is input cost. A plan framing it as pricing power or revenue has misread the seed.
- Produce a **sensitivity table**: margin impact per X% price increase, which is decision-useful regardless of how the tone reads.

**Bad plan:** builds a tone-scoring exercise across transcripts, treats defensiveness as informative, no benign-outcome control, no sizing of the exposure.

---

# Cut (4)

Kept for reference, not in the working set.

- **C1 — "strategic alternatives" → market-adjusted returns** (quant). Well-documented event study; the naive version is priced instantly. Sits between buckets, which makes the gold label ambiguous.
- **C2 — investor-day competitor share ceiling raised vs. prior call** (fundamental). A sound seed, but it overlaps S9 and S10 on reading management disclosure; the slot buys more coverage elsewhere.
- **C3 — risk-factor changes → shorts** (fundamental). Real flaw — risk factors are lawyer-drafted boilerplate added defensively after peer litigation, so changes reflect legal contagion more than company-specific news. Weaker discriminator than the four subtle seeds kept.
- **C4 — adverse selection in thin prediction-market books** (quant). Underspecified rather than flawed: the ">30% of the time" threshold isn't defined enough (horizon, marking, baseline) to admit a gold answer.
