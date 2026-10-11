# S3 — plan (claude-opus-5)

> Can we reliably identify European financial institutions from transaction data, using only anonymized institution IDs plus the demographics and spend behavior of a panel of customers?

---

# Research Plan: Re-identifying European Financial Institutions in Anonymized Transaction Panels

## 1. The question, stated precisely

The commercial motivation is that European transaction panels are largely useless for financial-sector research in their delivered form. Consumer panels are sold with counterparties for retail merchants named ("Zara", "Carrefour") but with financial counterparties either stripped, hashed, or bucketed into generic categories ("BANK TRANSFER", "INSURANCE"). If we can attach real-world identities — and ultimately tickers — to those hashed IDs, we convert an unusable field into a monthly read on deposit flows, customer acquisition, BNPL origination, brokerage funding, and insurance premium growth for a set of listed European names where sell-side visibility between quarters is poor.

The hypothesis to test is narrower than "can we identify institutions." It is: **for a European retail financial institution with more than roughly 500,000 customers in a country covered by the panel, the joint distribution of (a) its transacting customers' demographics, (b) the morphology and timing of flows to and from it, (c) its co-occurrence with other institutions in the same customer's wallet, and (d) the shape of its time series around known corporate events, is distinctive enough to select the correct institution from a candidate universe of ~700 with rank-1 accuracy above 75% and to support a high-confidence subset with precision above 95%.**

The secondary and more commercially important hypothesis: **a correct mapping produces out-of-sample predictive power for reported KPIs; an incorrect one does not.** That gives us an economic validation that is independent of our labelled data, which will be small.

## 2. Gating item: do this in week one, before any modelling

Two things can kill the project on legal grounds and both must be resolved before an analyst writes code.

First, read the panel vendor's licence. Most European transaction-data contracts contain an explicit prohibition on attempting to re-identify masked counterparties, and some go further and prohibit reverse-engineering of any anonymization. If that clause exists, the project as framed is a contract breach regardless of its statistical merit. The practical resolution is usually commercial rather than technical: ask the vendor to sell a *named* financial-counterparty feed, or to permit identification for a defined list of institutions. Several vendors will do this, because the institutions in question are not their data contributors. Get compliance sign-off in writing.

Second, check whether any institution we intend to trade on is a contributor of the underlying data. If a bank's own open-banking rails supply the panel and we then trade that bank, expect an internal control problem even if it is not technically MNPI. Exclude those names.

Third, on GDPR: entity identification is not itself a personal-data question, since the institutions are legal persons. But the features we build are derived from natural persons' transactions, so hold to a k-anonymity floor — suppress any ID-month-country-cohort cell with fewer than 100 distinct panelists — and never persist row-level data outside the vendor's approved environment.

## 3. Data

**Primary panel.** Target a European bank-transaction (not card-only) panel, because we need direct debits, standing orders, and SEPA credit transfers — card data alone will miss most financial flows. Fable Data is the most direct fit (bank-account-level, UK/DE/IT/ES/FR/PL, multi-million panel, counterparty strings retained for merchants). Alternatives or supplements: an aggregator-derived feed built on Tink or Salt Edge connections, or Consumer Edge's European card panel as a cross-check on the card-visible subset. Request a minimum of 48 months of history at row level (date, panelist ID, hashed counterparty ID, signed amount, channel/type code, MCC where present, currency), plus panelist attributes (birth year band, gender, postcode or NUTS3, income band or inferred income decile, tenure in panel).

**Labelled training data.** This is the binding constraint. Assemble labels from four sources, in descending order of preference: (i) any subset of the feed where financial counterparties are already named — in practice vendors mask inconsistently, and 10–20% of financial IDs often leak through partial strings; (ii) a purchased named feed for one country, to be used strictly as training and never as a validation set for that country's model; (iii) partial structured identifiers if retained — SEPA Creditor Identifiers map to institutions via national registries (Bundesbank issues and publishes DE creditor IDs; similar schemes exist in NL, ES, IT), and IBAN/BLZ prefixes map via the Bundesbank Bankleitzahl file and the SWIFT BIC directory; (iv) hand-labelling by two analysts independently, restricted to IDs with unambiguous fingerprints, with disagreements discarded rather than adjudicated. Budget for 200–300 labelled IDs across six countries and five institution types. Record for each label a provenance code and a subjective difficulty score, because "easy" labels will bias accuracy estimates upward and we will need to correct for that later.

**Candidate universe.** Build a table of roughly 700 European financial institutions: constituents of the STOXX Europe 600 Banks, Insurance and Financial Services indices, plus national mid-cap banks, plus a manually curated fintech list (Revolut, N26, bunq, Monzo, Starling, Wise, Trade Republic, Scalable Capital, Klarna, Alma, Scalapay, Zopa, eToro, Trading 212, Younited, and so on), plus the large mutual and cooperative networks. For each candidate record: countries of retail operation with entry dates, product set, deposit-taking flag, customer count by year, median customer age if published, branch count by NUTS3, corporate-event calendar (launches, rebrands, M&A completions, licence changes, market exits), ticker or private status. This table is the project's most valuable durable asset and will take an analyst two weeks.

**External anchors for validation.** S&P Capital IQ Pro for bank-level quarterly deposits and loans; the EBA Transparency Exercise for semiannual granular exposures on ~130 banks; national registry filings for private fintechs (Companies House for Revolut and Monzo, Bundesanzeiger for N26 and Trade Republic); company KPI disclosures for customer counts; Sensor Tower or data.ai for country-level monthly app downloads and MAU by app; Similarweb for domain traffic by country; OpenStreetMap/Overture `amenity=bank` POIs with `operator` tags for brand-by-postcode branch footprints; Eurostat and national census data at NUTS3 for demographic reweighting; Visible Alpha or Bloomberg consensus for the surprise tests.

## 4. Feature construction

Aggregate to the ID × country × month level, then collapse to an ID-level profile vector over a fixed 24-month reference window. Build roughly 200 features in six families.

**Customer geography.** Share of the ID's transacting panelists by NUTS3, normalized by the panel's own NUTS3 composition to give a location quotient. This is the single most powerful feature for incumbent banks: CaixaBank's Catalonia concentration, Lloyds' England skew, the regional Sparkassen and Crédit Agricole caisses, Banco BPM's Lombardy weight. Compare directly against OSM branch shares by NUTS3 using cosine similarity.

**Customer demographics.** Age distribution (deciles, plus share under 30), gender split, income decile distribution, panel tenure — all as ratios to panel base rates. Neobanks show a sharp under-35 mode; incumbent savings institutions skew 50+; brokers skew male and high-income.

**Flow morphology.** Signed-flow ratio (inflow value / total value) separates deposit-takers and brokers (bidirectional) from insurers and lenders (unidirectional). Then: share of transactions on round amounts (multiples of 50 and 100); coefficient of variation of per-customer monthly amounts; autocorrelation of per-customer amounts at lag 1 month, which spikes for fixed premiums and amortizing loans; share of amounts that repeat exactly for a given customer across 3+ consecutive months; modal day-of-month and its concentration; share of activity within two business days of country-specific payday; presence of a 3- or 4-installment pattern at 30-day spacing with amounts under €400 (BNPL); presence of small annual or quarterly credits on the 1st of a quarter (interest); implied amortization slope over 60–360 months.

**Channel and product mix.** Distribution across direct debit, standing order, credit transfer, card, and cash withdrawal codes. This differs sharply by country — Germany and Austria are direct-debit cultures, France and Italy lean on cards — so all channel features must be computed as deviations from the country panel mean, not raw.

**Wallet co-occurrence.** Build a bipartite panelist–ID graph, project to an ID–ID graph weighted by normalized pointwise mutual information, and run Leiden community detection. Primary current accounts are mutually exclusive; secondary neobank accounts co-occur with everything; brokers co-occur with each other. Extract for each ID: mean PMI with known primary accounts, share of its customers for whom it receives the largest single monthly inflow (a "primacy" score), and community membership.

**Event fingerprints.** Run PELT changepoint detection (the `ruptures` implementation, L2 cost, penalty tuned by BIC) on each ID's monthly active-customer and value series. Extract changepoint dates, magnitudes, and directions, plus first-appearance and last-appearance dates. Then match against the corporate-event calendar with a ±45-day window. A step-change in Germany in the month Trade Republic launched savings interest, or the merger of two Spanish IDs in the quarter CaixaBank absorbed Bankia, is nearly identifying on its own. This family is where the highest-confidence identifications will come from.

## 5. Method

**Stage one, type classification.** LightGBM multiclass over eight classes: incumbent retail bank, neobank/EMI, consumer lender, BNPL, broker/investment platform, insurer, pension/long-term savings, and payments processor/aggregator. Train on the labelled set with 5-fold stratified CV, grouped by country so the model cannot memorize country-specific quirks. Target macro-F1 ≥ 0.85. Report the confusion matrix; expect the neobank/EMI versus broker boundary and the consumer lender versus BNPL boundary to be the weak spots.

**Stage two, candidate scoring.** For each (ID, candidate) pair that survives hard filters — type match, country of operation overlap, candidate existed during the ID's active window — compute a pair-level feature vector: cosine similarity of NUTS3 geography against branch shares, absolute difference in median customer age, log ratio of panel-implied customer count to reported customer count, Pearson correlation of monthly panel active customers against monthly app MAU and against quarterly reported deposits (growth rates, minimum eight overlapping quarters), and the count of matched changepoint-to-corporate-event pairs. Fit a conditional (McFadden) logit over these pair features on the labelled set, where the choice set is the filtered candidate list and the chosen alternative is the true match. Conditional logit is the right estimator here because it models exactly the quantity we want — which candidate, given the alternatives — and it naturally accommodates variable-size choice sets. Include an explicit outside option ("not in universe") so unlisted mutuals and PSPs are not forced into a false match.

**Stage three, global assignment.** One-to-one assignment via the Hungarian algorithm on negative log-probabilities — but *only* within resolved brand groups. Cooperative networks (350+ Sparkassen, 39 Crédit Agricole caisses, the Volksbanken) and multi-brand groups (Santander UK versus Santander España, ING DiBa) violate one-to-one badly. Model these as a two-level hierarchy: assign IDs to groups first, allow many-to-one within a group, and only enforce injectivity at the group level.

**Confidence and thresholds.** Calibrate the logit's probabilities with isotonic regression on a held-out fold. Define the shippable set as IDs where calibrated top-1 probability ≥ 0.90 *and* the log-odds margin over the runner-up ≥ 2.0. Tune those two numbers on the holdout to achieve precision ≥ 95%, and report coverage at that precision. For IDs that fail the margin test but pass the level test, ship a *confusion set* of two or three names rather than a single answer; a set is usable for sector work even when a point identification is not.

## 6. Validation

Four independent tests, in increasing order of how much they should move our confidence.

**Blind holdout.** Hold back 60 labelled IDs stratified by country, type, and size. Report rank-1 accuracy, rank-3 accuracy, and precision at the shipping threshold. Stratify results by the difficulty score recorded at labelling time and report accuracy by difficulty quintile — the headline number will be inflated by the fact that labellable IDs are distinctive ones, and this stratification is how we estimate the true out-of-sample rate.

**Nowcast test.** For every identified listed institution with quarterly reported deposits or customer counts, regress reported YoY growth on panel-derived YoY growth of the mapped ID, with country and quarter fixed effects, on a training window ending Q4 2023 and evaluated on 2024–2025. Require out-of-sample R² ≥ 0.30 and a stable, correctly-signed coefficient. This is the economic test that matters: a correct mapping should nowcast; a wrong one should not.

**Permutation falsification.** Randomly permute the ID-to-candidate mapping within type-and-country strata, 1,000 times, and re-run the nowcast test. The true mapping's out-of-sample R² must sit above the 99th percentile of the permutation distribution. If it does not, we have found correlation, not identity.

**Temporal stability.** Re-estimate the entire pipeline on a disjoint 24-month window and measure mapping agreement (Cohen's kappa against the original). Below 0.7 agreement, the fingerprints are not stable enough to trade on.

## 7. Pitfalls to watch

The most dangerous failure mode is **processor confusion**: what looks like an institution is often Adyen, Worldline, Stripe, or a servicer collecting on behalf of dozens of lenders. Symptoms are implausibly broad customer geography, high wallet co-occurrence with everything, and multimodal amount distributions. Build an explicit processor class in stage one and route these to "unidentifiable" rather than forcing a match.

**Panel bias runs in exactly the wrong direction for this project.** Open-banking panels over-represent young, urban, digitally-native consumers and therefore over-represent neobanks and under-represent the older savings-bank customer base — the very institutions we most want to size. Never use panel share as a proxy for market share. Use only fixed-cohort YoY growth, computed on panelists observed for 13+ consecutive months, winsorized at the 1st and 99th percentiles, and reweighted to Eurostat age × NUTS3 × income cells.

**Consent asymmetry** compounds this: panelists typically link their primary account to the aggregator, so the visible flows to a secondary neobank are complete while the primary bank's *internal* transfers are invisible. Expect systematic under-detection of the institution that is the panelist's own bank, and treat any "primacy" feature with care.

**Multiple testing across 700 candidates and 200 features** will manufacture spurious correlations. Freeze the feature list before touching the holdout, apply Benjamini–Hochberg to any correlation-based anchor tests at q = 0.05, and require every high-confidence identification to rest on at least two mechanistically independent families of evidence — geography plus an event fingerprint, say, not two variants of the same correlation.

**ID instability.** Some vendors rotate hashes on a schedule or reissue IDs after a data-pipeline change. Monitor monthly for ID births, deaths, and volume discontinuities, and build an ID-stitching step (match on customer overlap Jaccard > 0.6 across the break) before assuming an institution has disappeared.

Finally, **the twins problem**: two mid-size regional institutions with overlapping footprints, similar demographics, and no distinguishing corporate events may be genuinely indistinguishable. Report these honestly as confusion sets. Overstating confidence on a handful of names is how this kind of project destroys its own credibility.

## 8. Timeline and kill criteria

Weeks 1–2: legal clearance, data delivery, candidate universe table. Weeks 3–4: feature pipeline and labelled set. Weeks 5–6: type classifier. Weeks 7–9: pair scoring, assignment, calibration. Weeks 10–11: the four validation tests. Weeks 12–13: write-up, coverage report, and production monitoring spec.

Kill or narrow the project if, at week 11, rank-1 accuracy on the blind holdout is below 65% for institutions in the top size quartile, or the permutation test fails, or coverage at 95% precision is below 40 institutions. The most likely graceful retreat is to narrow scope to a subset where fingerprints are strongest — neobanks, brokers, and BNPL in the UK, Germany, and Spain — where launch dates, app-download anchors, and installment morphology give us far more identifying information than we get for incumbent universal banks.
