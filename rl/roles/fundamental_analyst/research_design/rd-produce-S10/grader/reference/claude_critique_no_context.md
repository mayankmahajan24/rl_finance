# S10 — critique (claude-code subagent)

> A company went notably defensive around its annual vendor licence renegotiation. Is this a stronger near-term risk to margins than management has communicated, or is it not a sign of weakening fundamentals?

## Verdict

The plan is well-written and the author is clearly a careful thinker — several of its instincts (H2 as the primary test rather than a robustness check, within-speaker hedging differencing, pre-committing to the null) are better than what I usually see. But it is the wrong project. Section "The single-name work, which runs first" answers the question that was asked, and the plan itself concedes this: *"The answer to the researcher's question is the gap between the second and the third."* Everything in weeks two and three is a separate research programme — a 15-year cross-sectional NLP panel — that is bolted on to supply a base rate the single-name case can mostly do without, and that I do not believe can be executed at the stated sample size, on the stated data, in the stated time.

Worse, the parts most likely to generate a *confident* answer are the parts most likely to be wrong. There are at least three defects below that would each independently produce a clean-looking, significant, pre-registered result that is an artifact. Ranked by how much damage they do:

---

## 1. The DEF composite contains the outcome (fatal, and it will produce a "result")

Component 7, guidance-scope narrowing — *"margin guidance moves from point to range, widens, is qualified as 'subject to renewal', or is withdrawn"* — is not a measure of defensiveness. It is management telling you, on the call, that margins are at risk. The primary outcome is realized margin measured against **consensus as of before the call**. So the causal chain is: management guides margin down → component 7 fires → DEF rises → realized margin comes in below the *pre-call* consensus that had not yet incorporated the guidance. You will recover a large, robust, out-of-sample-stable coefficient that says nothing more than "guidance predicts results." It will survive every placebo in the Validation section, because it is not a spurious correlation — it is a real one, of no interest.

Component 6 (prepared-remarks avoidance) has a weaker version of the same problem and is also, contra the sentence introducing the list, *not* computed on topic-relevant Q&A pairs — it is a call-level, prepared-remarks-level variable. The claim that all seven components are computed on the same unit is simply false for 6 and 7.

**Fix or kill:** drop component 7 from the primary composite. If the author wants to keep it, the primary outcome must be measured against **post-call** consensus, which changes what the study is testing (from "does language forecast margins" to "does language forecast margins beyond what management said"), and that is the more interesting question anyway. Either way the headline must report DEF with and without 7 side by side. If the result lives only in the 7-inclusive composite, there is no finding.

## 2. The normalisation is not computable as written (mechanical break)

Components 1–5 are defined only on topic-relevant Q&A pairs. Those pairs exist only on calls where an analyst raised the vendor/licence. Two things follow that the plan does not reckon with:

- **Sector-quarter z-scoring is degenerate.** At the plan's own estimate of 300–800 events over ~64 quarters and ~11 sectors, that is well under one event per sector-quarter cell. You cannot z-score within a cell containing one observation. Z-scoring against *all* calls in the sector-quarter doesn't rescue it, because for non-event calls components 1–5 are undefined (no topic pairs), not zero.
- **The "firm's own trailing eight-quarter mean" is worse.** DEF is undefined in any quarter where the topic wasn't raised. Analysts raise a vendor licence episodically — often only in the renewal quarter itself. So for most events the trailing baseline is built from two or three observations, and a "+1.5σ above own trailing mean" threshold computed on n=2–3 is noise with a decimal point on it. The threshold that defines the treatment variable — "notably defensive" — is the least reliable object in the study.

**Fix or kill:** require a minimum of, say, six prior quarters with ≥2 topic-relevant pairs before an event enters the sample, then report how many events survive. My expectation is that it guts the sample. If it does, the within-firm baseline has to be abandoned in favour of a cross-sectional one, which reintroduces exactly the habitually-opaque-CFO problem the design was built to avoid. This needs to be resolved on paper in week one, not discovered in week two.

Related: component 3's within-speaker hedging difference is computed on topic-relevant answers that are frequently one or two responses — a couple of hundred words. Hedge-terms-per-hundred-words on 150 words is dominated by sampling noise. Set a minimum word floor and report attrition.

## 3. Contract status — the H2 test, which the plan calls the most informative test — cannot be dated the way the plan says

Three separate problems, and they compound:

- **Filing date ≠ execution date.** The plan says *"the filing date of the executed amendment is what determines the 'open vs signed at call date' split."* Exhibit 10 amendments are routinely filed with the next 10-Q, up to three months after signing. So a contract signed *before* the call but filed after gets coded "open." That misclassification is not random — it moves observations from the "signed" bucket (where H2 predicts the effect lives) into the "open" bucket (where H2 predicts null), biasing directly against the plan's own headline test. Use the execution date printed in the exhibit, which means reading exhibits, which means this is a manual-labour line item nobody has budgeted.
- **Most annual vendor licence renewals are never filed at all.** 8-K Item 1.01 is triggered by material definitive agreements *outside the ordinary course of business*. A recurring annual vendor licence renewal is close to the definition of ordinary course. The subset that does get filed is selected on being unusually large or unusual in kind — i.e. selected on the dose-response moderator and correlated with the outcome. The "signed" bucket and the "open" bucket will differ in composition, not just in timing.
- **The 2019 regime break.** The plan cites confidential-treatment requests as a materiality signal. The CTR process was replaced in April 2019 by self-redaction under Item 601(b)(10)(iv). That signal exists in the first two-thirds of the sample and vanishes in the last third — which is precisely the 2021–2025 out-of-sample holdout. Universe construction is therefore not stationary across the train/test split, and a failed OOS test would be uninterpretable. Post-2019 self-redaction also strips the pricing terms the cost bridge needs.

**Fix or kill:** hand-date contract status for a pilot of 40 events from exhibit execution dates and vendor-side disclosure, and measure how often the filing-date proxy gets it wrong. If it is wrong more than ~15% of the time, the H2 interaction is not estimable and the plan's central discriminating test is gone.

## 4. No power calculation anywhere

This is the omission that should have been caught before drafting. The plan commits three weeks and a very expensive data stack without once asking what effect size it can detect. Working it through:

- Firm fixed effects plus sector-by-quarter fixed effects, on a sample where **most firms will have exactly one qualifying renewal event**. Singleton firms contribute nothing to a within-firm estimator; firm FE will silently absorb a large fraction of the sample. Either drop firm FE (the within-firm DEF standardisation already handles firm-level style) or acknowledge that identification rests on the minority of firms with multiple events.
- The holdout is 2021–2025 — call it a quarter of the sample, so 75–200 events, of which "notably defensive" at a 1.5σ within-firm threshold might be 15–30. The pre-registered gate ("same sign, at least half the magnitude") will be decided by a handful of observations. It will pass or fail on luck, and either outcome will be over-read.
- The plan's own fallback if n < 200 is to widen from licences to *"supplier and distribution contract renewals generally."* That abandons the mechanism: the dose-response test on licence-cost share of COGS and the "no licence exposure" placebo both become uninterpretable on a sample that is mostly not licences.

**Fix:** compute the minimum detectable effect in basis points of gross margin, under the realistic n after the attrition in points 2 and 3, before spending anything. State the number. If the MDE is larger than the plausible true effect — and for a single vendor line inside COGS I think it is — the panel study is unrunnable and should be cut, not scaled down.

## 5. LLM scorer contamination goes beyond what the plan blinds for

The plan blinds human scorers to dates and subsequent periods. Good. But the LLM scorer's training data covers the entire 2010–2025 sample and its outcomes. Stripping dates does not blind a model that can identify the company and the vendor from three sentences of context and already knows how the renegotiation went. The plan flags "scorer contamination" as *"the subtlest one"* and then applies a remedy that addresses only the human.

**Fix:** entity-mask the transcripts — company, vendor, product, and brand names replaced with placeholders — and score both masked and unmasked. Report the correlation. If DEF moves materially under masking, a chunk of the composite is the model's memory of the outcome, and the study is dead regardless of what the placebos say. Also pin the model version: the calibration is worthless if the scoring run months later uses an updated model.

The calibration bar itself is too weak. Correlation 0.7 against **one** human on 100 events cannot separate model error from that one human's idiosyncrasy. You need two or three blind scorers and **human–human** agreement reported first. That is also the cheapest possible kill switch in the whole plan: if two trained analysts cannot agree at α ≥ 0.6 on what "defensive" means, the construct is not measurable and everything downstream is decoration. Run it in week one, on 40 transcripts, before committing to the data spend.

## 6. The week-one kill switch has no error bars, and it is the gate for everything

The materiality test is the right idea in the right place. But the bridge is estimated from *"segment disclosure, historical step-ups at prior renewals, the vendor's published rate card... and the vendor's own reported revenue from this customer."* Companies do not disclose single-vendor licence cost. Realistically the bottom-up estimate of licence-as-a-share-of-COGS carries an uncertainty band wider than the ±30bp threshold it is being compared against. A point estimate run against a point threshold will pass or fail arbitrarily.

**Fix:** state the bridge as a range with the sources of each bound, and require the **lower bound** of the impact to clear the gate. If you cannot bound the licence line to within roughly ±50bp of gross margin, that is itself a kill — you cannot answer the question from public data, and you should say so and stop. The vendor's own disclosed revenue from this customer, where it exists, is the only anchor that isn't a guess; the plan lists it fourth when it should be first.

Same section: the 30bp threshold is absolute where it should be relative — to the dispersion of the consensus margin path and to what actually moves this stock. And note the trap the plan doesn't name: a licence big enough to clear a materiality gate is a licence the sell-side is already modelling. The condition that passes claim 2 is the condition under which claim 3 (incremental information) is weakest. Those two gates fight each other and the plan treats them as independent.

## 7. The primary hypothesis is the wrong sign, and the plan already knows it

Pitfalls says it plainly: *"management may be defensive precisely because the renewal went well... Defensiveness is directionally ambiguous."* That observation invalidates H1's signed prediction. If the sign is ambiguous, the right primary outcome is dispersion or tail — which is H3, currently demoted to a secondary test run with quantile regressions at the end. The question as posed is about **risk**, not about expected margin. The plan has inverted its own hierarchy.

**Fix:** promote H3's tail/absolute-surprise outcome to primary and demote the signed H1 to secondary. This also aligns the study with the option-market evidence the plan is already paying OptionMetrics for.

## 8. Smaller things that still need fixing

- **Unpinned baseline date.** H1 says consensus *"as of the day before the call"*; the outcome definition says *"five trading days before the call."* Two different numbers for the same object, in a plan whose central defence is pre-registration.
- **Outcome aggregation unspecified.** "Realized gross margin over t+1 to t+4 minus the consensus path" — summed, averaged, or four separate quarters? Unstated. That is a free parameter.
- **Standardisation denominator.** Dividing by the trailing 12-quarter SD of the gross margin *level* inflates the denominator for firms with trending margins, shrinking their standardised surprise systematically. Use the SD of past surprises, or of the detrended margin.
- **Continuous vs threshold treatment.** H1 is written continuously ("an increase in defensiveness"); "notably defensive" is defined as a 1.5σ threshold. The primary specification must commit to one. This is exactly the crack post-hoc choice walks through.
- **Equal weights are defended with the wrong argument.** Equal-weighting correlated indicators is near-optimal when the indicators are *comparably informative*. Here they aren't: component 4 (analyst persistence) is mechanically correlated with component 1 (non-answer rate) — analysts re-ask *because* they got a non-answer — so equal weighting double-counts one event, and component 7 is outcome-contaminated. Report component-wise coefficients as a matter of course, not on request.
- **Component 4 is the selection channel, not the clean signal.** The plan calls analyst persistence *"the least gameable component"* and would weight it heavily. But analyst attention is driven by stock weakness — the exact selection problem named three sections later in Pitfalls. It is the most confounded component, not the least.
- **Placebo 2 needs a pre-committed threshold.** "DEF on no-licence-exposure firms should not predict margin surprise" will almost certainly be underpowered to distinguish "null" from "half the main effect." Pre-commit to an equivalence bound or an effect-ratio, otherwise a noisy null gets read as a pass.
- **FactSet Revere is the wrong tool for licensor relationships.** Its coverage is supply-chain and customer relationships; IP/software licensing pairs are thin. Don't build universe construction on it.
- **Cut the job-postings data.** Lightcast/Revelio procurement hiring is decorative here — weak, laggy, and it will never change a decision. It is cost and time with no decision value.
- **Data access is a week-zero question, not a data-section footnote.** If the shop doesn't already license Visible Alpha, the primary outcome does not exist, and the stated fallback (IBES EPS surprise) is one the plan itself rules out two sentences earlier as conflating margin with buybacks and tax. Confirm entitlement before anything else.
- **The single name is in the panel.** Week one establishes how that name turned out; weeks two and three then pre-register a study that includes it. Exclude it from the panel or state the contamination.
- **Option-market evidence is scheduled last and should be nearly first.** "Did IV and 25-delta skew move across this call, and is there a term-structure kink around the renewal date" is a day of work and the single cheapest test of whether the market already knows. Doing it in week one could kill the project before the NLP spend, which is the whole point of a kill switch.
- **EDGAR full-text search will miss incorporation-by-reference.** Material agreements are frequently incorporated by reference to earlier filings rather than re-filed; naive FTS misses them, biasing the universe toward first-time agreements over renewals — i.e. away from exactly the population under study.

## What I would actually authorise

Not three weeks. Roughly one, structured as a decision, not a study:

1. **Days 1–2 — Cost bridge with explicit bounds.** Licence line as a share of COGS, stated as a range, anchored on the vendor's disclosed revenue from this customer where available. Reconstruct what Visible Alpha consensus embeds for gross margin over the next four quarters. If the lower bound of a bad-outcome scenario cannot move gross margin more than the noise in the consensus path, write two paragraphs and stop.
2. **Day 3 — Counterparty read.** The vendor's own transcripts, filings, and disclosed customer concentration. The plan lists this fifth under Data; in practice it is usually the highest-information item available and it is nearly free. The other side of the negotiation talks about it, often more freely.
3. **Day 3 — Options.** IV and skew across the call, term structure around the renewal window. One day. Tells you whether the tail is already priced.
4. **Days 4–5 — Hand-built base rate, 40 events, no NLP.** Pick 40 renewal events you can date properly from exhibit execution dates, read the transcripts yourself, and answer only H2's binary: when the contract was already signed at the call date, did defensiveness precede margin damage? That is the one question in the whole plan whose answer would change a position, and forty hand-read cases will answer it better than a 400-event panel built on an uncomputable normalisation, a contaminated composite, and a filing-date proxy that misclassifies in the direction of the hypothesis.
5. **Human-agreement pilot, run alongside.** Two analysts, 40 transcripts, blind. If they don't agree on what defensive means, everything above item 4 is unbuildable and you have learned that for a day of cost rather than three weeks.

If item 4 comes back interesting *and* the shop wants a durable signal rather than an answer on this name, then the panel study is a reasonable thing to scope — as its own project, with a power calculation up front and the composite rebuilt without component 7.

## What is genuinely right

Worth saying, because these are not common. Making H2 the central test rather than a robustness check is the correct instinct and is the single best judgement in the document — the legal-constraint story really is the modal explanation, and most versions of this idea never name it. The within-speaker, within-call hedging difference is a clean piece of construct design. The shifted-window placebo is the right way to catch inadequate pre-trend controls. Insisting on line-item margin consensus rather than EPS surprise is correct and most people get it wrong. The MNPI section is accurate and appropriately placed — expert calls on a live named-counterparty negotiation are a real hazard and the scoping advice is right. And pre-committing to the null as a reportable answer, with a sample sentence written out, is exactly the discipline that stops a three-week project from manufacturing a result. The problem with this plan is not care. It is that the careful machinery is pointed at a question the week-one work already answers.
