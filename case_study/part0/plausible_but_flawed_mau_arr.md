# Part 0 — Plausible but doesn't survive desk review

*Written by me, before touching Claude. Corresponds to seed **S2**. Paired with `well_posed_kalshi_draftkings.md` (S1), which uses the same toolkit and survives.*

## Portal MAUs as a leading indicator of ARR in seat-based SaaS

The readout is: among US-listed SaaS companies that price per seat, does the level of monthly active users on the client-facing portal explain reported ARR one to two quarters later, closely enough to call the number before the company prints it? The primary relationship is portal MAU to ending ARR; use subscription revenue run-rate only as a secondary read for names that do not disclose ARR directly.

Use third-party web and mobile panel data mapped to each company's client-facing portal domain and app. Start in 2021, aggregate panel traffic to monthly and quarterly periods, and produce separate web, mobile, and combined source cuts. Pull ARR, subscription revenue, and consensus estimates point-in-time from filings and press releases so restated figures do not leak into the fit. Screening for seat-based pricing and quarterly ARR disclosure gives roughly 35 to 50 names.

Line up each company's quarterly portal MAU against its reported ARR and fit the relationship in logs across the panel, with company effects to absorb persistent differences in panel coverage and price level, and quarter effects to absorb common macro. Test MAU lagged zero, one, and two quarters and carry forward whichever lag fits best. Where a company has enough quarters, fit it on its own so the coefficient reflects that name rather than the pooled average; otherwise fall back to the pooled coefficient. Cluster standard errors by company. Hold out a random 20% of company-quarters, fit on the rest, and report out-of-sample R² and average percentage error against reported ARR. Treat the relationship as usable if average error is under 3% and the MAU coefficient is positive and significant in most of the per-company fits. Then, two weeks ahead of each print, generate a predicted ARR, compare it to consensus, go long the top decile of predicted surprise and short the bottom decile, and hold through the print.

Before interpreting results, confirm the domain and app mapping for each company, check that the panel covers each name densely enough to be stable, and look for level shifts where the vendor has re-baselined its methodology. Use a point-in-time universe that includes delisted names so the fit is not run only on survivors. Compare web, mobile, and combined cuts for the same directional message, and report all three lags rather than only the one that fit best. Treat the output as directional rather than exact, because some names have fewer than twelve quarters of history, the universe is small enough that a handful of large companies drive the pooled fit, and panel coverage of any single company can change without notice.

---

## Why it dies at desk review

It dies on the billing mechanic: seat-based ARR bills on seats *contracted*, not seats used, so shelfware lets ARR compound while MAU is flat, and free viewer tiers let MAU climb on seats that bill nothing. Even where the two co-move, ARR is seats × price and MAU is silent on the price/mix half, which carries most of the growth in a mature seat model. The panel makes this worse rather than better — enterprise traffic behind SSO and VPN is largely invisible to third-party measurement, so coverage skews toward exactly the small accounts contributing least to ARR. A level regression across SaaS names will still print a high R² because both series trend up, which is precisely what makes the result convincing and wrong.

---

## Where the flaws are loaded (not part of the write-up)

| Flaw | Where it sits | Why it reads as fine |
|---|---|---|
| Spurious trend | Para 3, "fit the relationship in logs" — levels, never differenced | Company + quarter effects look like the rigorous choice; they don't remove within-company drift. In prose form there's no equation to inspect, so this is harder to see than in the structured version |
| Leaky validation | Para 3, "hold out a random 20% of company-quarters" | Standard ML hygiene — but it trains on future quarters to predict past ones, and on adjacent quarters of the same company |
| No naive baseline | Para 3, the 3% error bar | ARR is highly autocorrelated, so just extrapolating last quarter clears 3% with no MAU contribution at all. Never compared |
| MAU ≠ billable seats | Para 1, assumed in the readout itself | Never validated against companies that disclose seat counts |
| Price/mix blind | ARR never decomposed into seats × price | Nothing stated is wrong; the omission is invisible |
| Panel coverage bias | Para 4, "look for level shifts where the vendor has re-baselined" | Sounds like the coverage issue and isn't it — says nothing about SSO/VPN enterprise traffic being unobservable |
| Portal ≠ product | Para 2, domain/app mapping | Confirms the mapping is *correct*, never asks whether the portal is the product or an admin/billing surface |
| Generic caveats | Para 4 throughout | Survivorship, thin samples, concentration, lag reporting — all real, all responsible, none of them is what kills this |
