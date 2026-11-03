# S2 — plan (claude-code subagent)

> Do monthly active users on a company's client-facing portal predict ARR for SaaS companies on seat-based pricing?

## What we are actually claiming

The economic story is narrow and worth stating precisely, because the whole design follows from it. For a company that charges per seat, revenue is the product of seats sold and price per seat. Seats sold is a contractual number that only updates at renewal or at a mid-term expansion event, but the number of humans who actually log in and use the product moves continuously and moves *first*. A customer whose employees stopped logging in three months ago will not expand at renewal and may downgrade; a customer whose usage has doubled will be upsold. So logged-in portal activity should be a leading indicator of net revenue retention, and net revenue retention is the dominant term in ARR growth for mature seat-based SaaS.

The formal hypothesis: **conditional on lagged ARR growth and sell-side consensus, year-over-year growth in unique monthly visitors to a company's authenticated product domain has positive incremental predictive power for that company's year-over-year ARR growth one to two quarters ahead, and this relationship is materially stronger for seat-priced companies than for consumption-priced ones.**

The second clause is the part that makes the study worth doing. If the effect is the same for Snowflake and Datadog as it is for Asana and Smartsheet, then we have not found a seat-expansion signal — we have found a generic "healthy company gets more web traffic" correlation, which is already in the price. The consumption cohort is not a robustness check bolted on at the end; it is the control group and it goes in the first regression.

The null we are trying to kill is that portal traffic is a coincident, not leading, measure — that it tracks seats already sold and already reported, and adds nothing beyond consensus.

## Universe

Start from US- and Israel-listed application software companies with a market cap above $1bn and a majority of revenue from subscription. That is roughly 120 tickers. Then apply three screens, in this order, and keep the rejection log because the log is itself a finding.

First, **pricing model classification**. For each company, pull the public pricing page (current, plus Wayback Machine snapshots at each quarter-end back to 2016) and the revenue recognition and disaggregation notes in the 10-K. Code each company's primary SKU as seat-based, consumption/usage-based, transaction-based, or entity-based (per device, per contact, per location, per employee-managed). Require ≥60% of revenue from seat-priced SKUs to enter the treatment cohort. Atlassian, Asana, Monday, Smartsheet, HubSpot's core seats, Salesforce, DocuSign, Box, Dropbox, Freshworks, Zoom's enterprise SKU, Workday, Bill.com's subscription line all plausibly qualify; Snowflake, Confluent, Datadog, Twilio, MongoDB Atlas, Cloudflare and Fastly go in the consumption control cohort; Samsara (device), Klaviyo (contacts), Toast and Shopify (transaction), Procore (construction volume) go in a third "other-unit" bucket that we use only as a second placebo. Do this by hand. It takes an analyst two days and it is the single highest-leverage step in the project.

Second, **web-primary access**. This screen kills the study if applied honestly, so apply it early. A large share of the best seat-based names are consumed through native desktop or mobile clients that never touch a browser panel — Slack, Zoom's meeting client, Dropbox's sync agent. If most seats never load `app.company.com` in a browser, web panel MAU measures the wrong population. For each candidate, determine whether the primary daily workflow is browser-based. Keep browser-primary names in the core sample; move client-primary names to a secondary sample where the MAU input is a blend of web panel data and mobile/desktop app panel data, and analyze that sample separately rather than pooling it.

Third, **panel reliability floor**. Require the identified portal domains to show at least 50,000 monthly unique visitors in the vendor panel and at least 24 consecutive months of unbroken coverage. Below roughly 50k the vendor's estimates are extrapolated from a handful of panelists and the month-to-month noise swamps any signal.

Expect to land at 35–50 seat-based names and 15–25 consumption names, over 2016–2025. That is on the order of 1,500 firm-quarters in total and perhaps 900 in the treatment cohort. Size the ambitions to that number: this is a fundamental forecasting tool and a position-sizing input, not a standalone systematic factor with a Sharpe ratio.

## Data

**Portal traffic.** Similarweb, at subdomain granularity, monthly, via the Investor Intelligence product or the Digital Rank/Traffic API. The critical requirement is subdomain-level output — `app.asana.com`, `app.smartsheet.com`, `id.atlassian.com`, `*.atlassian.net`, `app.hubspot.com` — because the marketing site (`www.`) measures top-of-funnel demand generation, which is a *different* signal with different timing, and mixing the two destroys the study. Budget for a six-figure annual license; if the budget is not there, Datos or a Chrome-extension-derived panel gives a cheaper but noisier substitute and the reliability analysis below becomes even more essential.

For each company, build the domain map by hand: log in to a trial account and record every hostname the authenticated session touches, then cross-check against the company's DNS records and their status/trust pages. Re-verify the map every four quarters — companies migrate portals, and an unnoticed migration looks exactly like a collapse in usage.

**Second, independent traffic panel.** Sensor Tower or Apptopia for mobile MAU, and a second web panel if affordable. We need two independent noisy measurements of the same latent quantity, for the instrumental-variables correction described below. Do not skip this.

**Financials.** ARR and ARR-proxy from company IR disclosures where given, otherwise quarterly subscription revenue from Compustat/Capital IQ Point-in-Time, plus current RPO where disclosed. Collect the disclosed operating metrics too — paid customers, customers above $100k ARR, net revenue retention, and for the handful of firms that publish it, actual user counts. Consensus estimates from Visible Alpha (line-item detail, so we can get consensus *subscription* revenue rather than total) with Refinitiv/IBES as fallback. Point-in-time everything: use the consensus as it stood ten days before the print, not the restated final.

**Controls.** Revelio Labs or LinkUp for headcount and job-posting counts, split into sales/quota-carrying versus engineering; G2 and Gartner Peer Insights review velocity as a competitive-displacement control; Glassdoor for the sales-attrition control.

## Constructing the signal

Aggregate monthly unique visitors — not visits, not pageviews — to the mapped portal domains. Adjust each month for weekday count (business software traffic is a weekday phenomenon and a 23-weekday month looks 10% better than a 21-weekday month) and for the December/July holiday troughs, using an X-13-style additive adjustment estimated on the full panel rather than firm by firm.

Form the quarterly value as the *mean* of the three monthly uniques in the fiscal quarter, matched to each company's own fiscal calendar. Do not sum — you would be counting the same users three times, and the sum is contaminated by the month-length effect you just removed.

The primary predictor is the four-quarter log change, `Δ4 log MAU`, then **cross-sectionally demeaned within each calendar quarter across the full universe including the control cohorts**. That demeaning is not cosmetic. Panel vendors re-weight and re-recruit their panels, and a re-weighting shows up as a common level shift across every domain they measure. Demeaning within quarter removes the vendor-wide component and leaves the firm-specific component, which is the only part we have a theory about. Also carry `Δ1 log MAU` (sequential) and the acceleration term `Δ1 log MAU_t − Δ1 log MAU_{t−1}`, since expansion decisions plausibly respond to the change in trend rather than the level.

Timing: Similarweb publishes month *M* around the 8th–12th of month *M+1*, and SaaS companies report roughly 30–45 days after quarter end. So the full-quarter signal is in hand 20–35 days before the print. Record, per firm-quarter, the exact date the third month's data became available, and never use a data point in a backtest before that date.

## Estimation

The workhorse specification, on the seat-based cohort:

`Δ4 log ARR_{i,t+1} = α_i + δ_t + β · Δ4 logMAU_{i,t} + γ' X_{i,t} + ε_{i,t+1}`

with firm fixed effects `α_i`, calendar-quarter fixed effects `δ_t`, and controls `X` comprising `Δ4 log ARR_{i,t}`, `Δ4 log ARR_{i,t−1}`, consensus subscription-revenue growth for quarter *t+1* as of ten days pre-print, `Δ4 log` sales headcount, and `Δ4 log` cRPO. Standard errors by Driscoll–Kraay with four lags — SaaS usage and SaaS revenue are both heavily exposed to a common software-spending cycle, so cross-sectional dependence is the binding inference problem and firm-clustered errors will be too small.

Run the identical specification on the consumption cohort and on the pooled sample with a `seat × MAU` interaction. The interaction coefficient is the headline result.

Report `β` in units a portfolio manager can use: "a firm whose portal MAU grows 10 percentage points faster than the software universe this quarter delivers *x* percentage points faster ARR growth next quarter, controlling for what consensus already expects."

Then three refinements.

**Attenuation.** Panel MAU is a noisy proxy for true active seats, so OLS `β` is biased toward zero by the reliability ratio. Estimate that ratio directly on the subsample of firms that disclose a real user metric (Zoom's historical MAU, Dropbox and Box paying users, Atlassian's customer counts, Slack's pre-acquisition DAU) by regressing the disclosed metric on the panel metric. Then, for the full sample, instrument the Similarweb growth measure with the Sensor Tower/second-panel growth measure. Two independent proxies for the same latent variable, each with independent measurement error, is a textbook multiple-indicator IV and it recovers an unattenuated `β`. If the IV estimate is three times the OLS estimate, that is the honest effect size and it is worth knowing.

**Nonlinearity.** Fit the primary spec with `Δ4 logMAU` entered as quintile dummies. The prior is asymmetry: usage collapse predicts churn sharply, usage acceleration predicts expansion weakly, because expansion is gated by contract timing and procurement while churn is not. If that asymmetry exists, the practical use of the signal is as a downside screen, which is a materially different product than a long-short factor.

**Horizon.** Re-run at t+1 through t+4. A signal that only works at t+1 is probably just picking up the quarter's already-booked seats. A signal that persists to t+3 and t+4 is a genuine leading indicator of renewal-cycle outcomes. Chart the coefficient path.

## Validation

Pre-register the primary specification, the universe screens and the success criteria in a dated document before the first regression is run, and log every subsequent deviation. There are perhaps forty defensible ways to build this signal and at 5% each, one of them will look wonderful.

Declare the hypothesis supported only if all four of the following hold: `β > 0` with a Driscoll–Kraay *t*-statistic above 3; incremental out-of-sample R² over the AR-plus-consensus baseline of at least 3 percentage points; a Diebold–Mariano test on out-of-sample RMSE significant at 5%; and the seat-versus-consumption interaction significant at 5% with the expected sign.

Out-of-sample means expanding window: estimate on 2016Q1 through 2020Q4, predict 2021Q1, roll forward one quarter at a time, refitting each step. Also run leave-one-firm-out, because with fifty firms a single name — Zoom in 2020 is the obvious candidate — can carry the entire result. Plot the distribution of `β` across the fifty leave-one-out fits before believing the pooled number.

Three placebos. Run the same regression using marketing-site (`www.`) traffic instead of portal traffic; if `www.` predicts ARR just as well, the signal is demand generation or general momentum, not seat activity, and the framing of this project is wrong. Run it on the entity-priced cohort (per device, per contact), where the seat mechanism does not apply. And run it against a randomly reassigned mapping of traffic series to tickers, 1,000 draws, to get an empirical null for the *t*-statistic that is robust to the panel's cross-sectional dependence.

Finally, an economic validation distinct from the statistical one. Form quarterly tertiles on the demeaned signal within the seat cohort, long the top and short the bottom, hedged to the IGV software index, entered five days before the earnings date and exited five days after, and separately held for sixty days post-print. Charge 30bp round-trip plus a borrow assumption. Report the earnings-day return separately from the drift, because they answer different questions: the earnings-day return says the signal contains information the market did not have, the drift says the market is slow to incorporate it. Also split the backtest at 2021 — this is a widely known alt-data trade and if the alpha is entirely pre-2021, we are documenting a decayed signal, which is still a publishable internal finding but not a tradeable one.

## Pitfalls to watch

**Free tiers are the big one.** Atlassian, Asana, Notion-likes, Dropbox and HubSpot all run enormous free bases. Most of the MAU we measure are not paying and never will. Worse, the relationship can invert: aggressive free-tier growth can coincide with weak monetization. There is no clean fix with panel data. The partial mitigations are to restrict to weekday business-hours traffic, to weight by high-ARPU geographies (US/UK/DACH share of traffic, which vendors provide), and to control for the disclosed free-versus-paid mix where companies report it. State plainly in the writeup that the freemium names carry an unresolved confound, and check whether `β` differs between freemium and sales-led names — if the signal only works on sales-led enterprise names, say so and restrict the deliverable to those.

**Price is the other half of the identity.** ARR equals seats times price. Atlassian's server-to-cloud migration and Zoom's enterprise repricing moved ARR substantially with no corresponding user movement. Build a hand-maintained price-change calendar from archived pricing pages and include quarter dummies for firms in a repricing window; better, decompose the dependent variable into ARR-per-customer and customer count where disclosure allows, and test whether MAU predicts the count leg specifically. That decomposition is the sharpest version of the test.

**Domain migrations and panel breaks.** Flag any month-over-month change in a series exceeding 30% with no corresponding company news, and investigate every flag by hand before it enters the panel. Untreated, one migration produces a fake ±60% "usage collapse" that lands in the bottom tertile and, if it happens to coincide with a weak print, single-handedly manufactures the result.

**Restatement and look-ahead.** Similarweb revises history when it re-weights, so the series you download today is not the series you would have had in 2019. Ask the vendor for point-in-time vintages; if they cannot supply them (they usually cannot going back far), treat the pre-2024 backtest as contaminated by an unknown amount of restatement bias, freeze a monthly snapshot from today forward, and commit to a genuine forward walk-forward test before sizing anything.

**Inorganic growth.** Drop firm-quarters within two quarters of any acquisition worth more than 5% of trailing revenue; acquired ARR appears in the numerator with no corresponding portal traffic in the denominator.

**Bots and SSO.** Portal domains attract scrapers, uptime monitors and API traffic that panels sometimes count. Prefer unique-visitor metrics over visits, and sanity-check that measured MAU is within a plausible multiple of disclosed seats or customers for the firms that disclose either. If measured MAU exceeds any credible seat count, the domain map is wrong.

## Sequencing

Week one: pricing classification, domain mapping and the web-primary screen, ending with a locked universe and rejection log. Week two: build the traffic panel, run the break-detection and seasonal adjustment, assemble financials and point-in-time consensus, and reconcile panel MAU against disclosed metrics for the calibration subsample. Week three: run the pre-registered primary regression, the cohort interaction, the placebos and the IV correction. Week four: the walk-forward out-of-sample test, the tertile backtest, and a writeup organised around the interaction coefficient and the freemium split.

The realistic good outcome is not a factor. It is a per-name usage dashboard with a calibrated statement of the form "portal MAU explains *x*% of the residual variance in next-quarter seat growth for sales-led seat-priced names, with the relationship strongest on the downside," which an analyst uses to argue with consensus on a specific ticker two weeks before it prints. Design the deliverable for that use from day one.
