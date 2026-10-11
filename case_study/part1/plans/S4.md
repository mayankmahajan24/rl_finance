# S4 — plan (claude-opus-5)

> A hyperscaler was removed as a guarantor on a new SPV with its longstanding chip manufacturer. Is this a sign they are qualifying a second source and pushing risk back onto their primary provider?

---

# Research Plan: Guarantor Removal on a Hyperscaler–Foundry/ASIC SPV as a Second-Source Signal

## 0. First, pin the fact pattern down

Before any analysis, the analyst spends the first day establishing exactly what happened, because the idea as stated contains three unverified assumptions: that a guarantee existed, that it was *removed* rather than *released on a pre-agreed schedule*, and that the hyperscaler's economic commitment changed as a result.

Identify the SPV by legal name and jurisdiction. Work from the disclosure that triggered the idea backward to primary documents: SEC EDGAR full-text search (efts.sec.gov, covers 2001+) on the SPV name plus terms like "Guaranty," "Guarantor Release," "Parent Guarantee," "Capacity Reservation Agreement"; the 8-K Item 1.01/1.02/2.03 stream for both parties; exhibit lists (EX-10.x) for amendments and amended-and-restated credit agreements; the 10-K/20-F footnotes on Guarantees and Indemnifications (ASC 460), Variable Interest Entities (ASC 810), Contractual Obligations, and Related Party Transactions. For non-US counterparties: Taiwan's MOPS, where listed companies must disclose endorsement/guarantee (背書保證) balances monthly and material contract changes promptly; Korea's DART; Japan's EDINET; Luxembourg RCS/RESA and Irish CRO, where guarantee deeds for financing SPVs are frequently filed in full. Pull LSEG LPC DealScan for the loan tranche history including the guarantor list at each amendment, and Bloomberg CACS/DDIS for the SPV's debt if it issues. Rating agency pre-sale and issuer reports (Moody's, S&P, Fitch) are the single richest source: if a guarantee disappears, the agency explains in prose what replaced it and whether notching changed. Also run UCC-1 and UCC-3 searches in the relevant Secretary of State databases — a terminated financing statement or a change in secured party tells you whether collateral moved with the guarantee.

The deliverable from this step is a one-page fact sheet: entity chart, capital structure of the SPV, who guaranteed what before, what the amendment changed, effective date, and — critically — the disclosure date versus the effective date.

## 1. The hypothesis, stated so it can be wrong

**H1 (the researcher's thesis):** The hyperscaler has qualified or is qualifying an alternate supplier, and is deliberately reducing its financial exposure to the primary provider's capacity build, shifting utilization and capex risk onto the supplier's balance sheet. Prediction: the supplier's share of that program declines, contract liabilities and prepayments stagnate or fall, and evidence of a second design win appears within 12–18 months.

**H0 (the boring explanation, and the base case):** The guarantee release was pre-negotiated at inception, triggered automatically by a completion test, DSCR test, or ratings/leverage condition, or was removed for accounting reasons — to avoid a guarantee liability under ASC 460, to avoid consolidating the SPV as a VIE under ASC 810, or to keep the obligation out of the contractual obligations table. Economic commitment unchanged.

**H2 (risk transformation, not risk reduction):** The guarantee was replaced by an economically equivalent or stronger instrument — a take-or-pay capacity reservation with liquidated damages, a prepayment, a keepwell, or an equity contribution agreement. This is the most likely way the researcher's thesis is *directionally wrong in a costly way*, because it looks like disengagement and is actually deeper commitment.

**H3 (financing maturation):** The SPV became standalone-financeable — construction complete, third-party customers added, subsidy tranche received (CHIPS Act, METI, EU Chips Act conditions often constrain ownership and support structures) — and lenders no longer required the credit enhancement.

**H4 (program de-scoping):** Not second sourcing, but shrinkage or cancellation of the program. Worse for the supplier than H1 and requires a different trade.

**H5 (regulatory/tax):** Export control, antitrust, transfer pricing, or subsidy-eligibility restructuring.

The research question is not "is H1 true" but "what is the posterior probability of each, and which is mispriced."

## 2. Document forensics: the decisive work

Redline the pre- and post-amendment agreements clause by clause and populate a structured extraction table with these fields: minimum volume or take-or-pay commitment (units and dollars), term, liquidated damages on shortfall, termination-for-convenience fee schedule, prepayment/deposit balance and refundability, capacity reservation fee, exclusivity and its carve-outs, explicit alternate-source or second-source permissions, IP ownership and license scope (does the hyperscaler own the RTL, or license the SerDes/HBM PHY/chiplet interconnect from the supplier?), step-in rights, change-of-control, most-favored-nation pricing, and any keepwell, equity contribution, or comfort letter that appears where the guarantee used to be.

Then check the *original* agreement for a defined "Guarantee Release Date," "Completion Date," "Sponsor Support Termination," or similar. If the release was automatic on a milestone, H0 wins and the idea is largely dead as a signal — though it may still be tradeable if the market misreads it, which is a separate and useful finding.

Use Covenant Review, Xtract Research, or 9fin if the SPV debt is rated and syndicated; they publish clause-level analyses that will save days.

## 3. Did economic commitment actually change? Follow the money

Independent of the legal documents, test whether the hyperscaler's cash and obligations to this supplier grew or shrank. On the supplier side, track quarter by quarter for eight quarters before and however many after: contract liabilities and deferred revenue, "advances from customers" or customer deposits, accounts receivable concentration, the 10% customer disclosure (ASC 280) or equivalent, inventory and days of inventory, purchase commitments to *its* suppliers (a supplier that has quietly lost a customer stops committing to CoWoS/HBM/substrate), and capex versus depreciation. On the hyperscaler side, the contractual obligations table, "other commitments" footnote, and any disclosed prepayments.

The critical test for H2: if prepayments or contract liabilities rose in the same period the guarantee fell away, the hyperscaler substituted cash for credit support and the thesis inverts. If both the guarantee and the prepayments fell, H1 or H4 is live.

## 4. Independent evidence on the second source

Do not let the SPV document carry the whole argument. Assemble corroboration from four independent channels, each with a specific source:

**Design and tape-out evidence.** Monthly revenue disclosures from Taiwanese design-service and ASIC houses (Alchip, GUC, Faraday) and from TSMC/UMC — Taiwan's monthly revenue reporting regime gives you a high-frequency series most models ignore. Watch for NRE-driven step-ups at a candidate second source. Cross-check with Hot Chips, ISSCC, and OCP Global Summit presentations, where hyperscalers disclose accelerator and NIC architecture details and frequently name partners. Check USPTO assignment records and co-assignment patterns; a switch in ASIC partner shows up in co-invented patents 18–24 months ahead of revenue.

**Supply chain flow.** OSAT and test house monthly revenues (Amkor, ASE/SPIL, KYEC), substrate makers (Ibiden, Shinko, AT&S), and ODM assemblers (Quanta, Wiwynn, Celestica, Jabil, Foxconn Industrial Internet). Panjiva/S&P Global bills of lading and Taiwan/Korea customs aggregates at the HS-code level — noting that hyperscaler ASIC flows usually route through ODMs, so entity-level attribution is weak; use these as corroboration, never as primary evidence.

**Labor and organizational signal.** Revelio Labs or LinkUp job-posting data on the hyperscaler's silicon organization and on candidate second suppliers: postings referencing a specific EDA flow, packaging technology, or "dual-source qualification" are informative. Track senior IC engineering moves between the hyperscaler and the candidate alternate.

**Management language.** Run a systematic language diff across the supplier's last eight earnings calls and the hyperscaler's, using AlphaSense or Bloomberg transcript search: frequency and framing of "customer concentration," "second source," "multi-vendor," "prototype," "ramp," "qualification," and the supplier's habit of numbering customers. Note hedging changes, not just topic changes.

Existing Tegus/AlphaSense expert transcripts should be mined before commissioning new expert calls; if new calls are needed, route through compliance with scripted questions that avoid the SPV's contractual terms (see pitfalls).

## 5. Base rates from analogous restructurings

Build a hand-curated case book of 20–35 events in capital-intensive supply chains where a large customer's credit support for a supplier-affiliated SPV or JV was removed, reduced, or restructured. Seed list: the WD/Kioxia Flash Ventures guarantee and lease structures; Micron–Inotera; Apple–GT Advanced (the cautionary case on prepayment-plus-security structures); Apple–Amkor Arizona; TSMC JASM's equity partners; Intel's Brookfield and Apollo semiconductor co-investment programs; Bosch–GlobalFoundries Dresden; and, as adjacent analogs, telecom fiber and data center JV structures (Meta–KKR, Microsoft–BlackRock AIP, Oracle-linked vehicles).

For each case, record the stated reason, whether an offsetting commitment appeared, and the outcome at +8 quarters: did the customer's revenue share at that supplier decline more than 15 percentage points? Did consensus revenue estimates for the supplier fall? This sample is far too small for regression; treat it as structured case-based reasoning with a scoring rubric, and report the base rate honestly as, say, "4 of 22 cases were followed by material share loss" rather than dressing it up as a probability model.

## 6. Market tests: is this priced?

Run a standard event study on the supplier's equity around both the effective date and the disclosure date. Estimator: a four-factor market model (Fama-French three factors plus momentum) augmented with an orthogonalized SOX index return, estimated over 250 trading days ending 30 days before the event, with CARs measured over (-1,+1), (0,+5), and (0,+20). For the base-rate sample, use the Boehmer-Musumeci-Poulsen standardized cross-sectional test, with the Corrado rank test as a non-parametric robustness check given small n and fat tails.

Extend to credit: the supplier's CDS spread change versus CDX IG, and bond OAS from TRACE. And to options: 30- and 90-day implied vol and 25-delta skew around the date.

The key read is not the sign of the CAR but its *magnitude relative to nothing*. If the disclosure was buried in an exhibit and CAR is statistically indistinguishable from zero on normal volume, the information is likely unpriced — which is the entire investment case. If there was a clear negative move on elevated volume, the idea is already consensus and the remaining question is whether it overshot.

## 7. Sizing the economics and expressing the view

Build a program-level model for the supplier: units, ASP, gross margin, NRE versus production revenue, and the capex the SPV was built to support. Three scenarios at a two-year horizon: (a) dual-source with a 70/30 volume split, (b) financing optimization with no share change, (c) program de-scoping with 40%+ volume decline. Translate each to revenue, EPS, and a defensible multiple, and weight by the posterior probabilities from Sections 2–5.

Note the asymmetry of expression: this is almost never a trade in the hyperscaler, where the program is immaterial to consolidated earnings. The trade lives in the primary supplier (short or underweight), the candidate second source (long), and the second-order names whose economics are share-agnostic (OSAT, substrate, design services), which can serve as a hedge or as the cleanest long if you believe the program grows regardless of who wins it. A pair — short primary versus long alternate, beta- and SOX-neutralized — isolates the share-shift view from AI-capex direction, which is the dominant risk factor and one you are not trying to take.

## 8. Kill criteria, stated in advance

The thesis is dead if any of the following is found: the original agreement contains a scheduled or milestone-triggered guarantee release; the amendment leaves minimum volume commitments unchanged or increases them; contract liabilities or customer prepayments at the supplier rise in the two quarters around the event; a rating agency attributes the release to construction completion, third-party customer diversification, or subsidy conditions; or no tape-out, NRE, or hiring evidence of a second source appears within twelve months of the guarantee change. Write these down before the work starts and hold to them.

## 9. Pitfalls to watch

The dominant error is conflating a legal guarantee with an economic commitment. Sophisticated buyers routinely trade a guarantee for a take-or-pay, which increases their exposure while shrinking the disclosed one. A related error is entity confusion: "removed as guarantor" often means removed and *replaced* by another group entity — sometimes a stronger one — and SPV naming conventions make this easy to misread. Read the entity chart, not the headline.

Custom silicon is not fungible. Even where a second source is genuinely qualified, switching depends on who owns the RTL and whether the SerDes, HBM PHY, and chiplet interconnect IP travel with the design; packaging and system qualification alone run 12–24 months. A correct thesis can lose money for two years, so the timeline must be built into position sizing and into the choice between equity, options, and credit.

Beware confirmation bias in the corroborating channels — Taiwan supply chain press in particular reports directional rumors that are frequently right in substance and wrong in magnitude and timing. Require two independent channels before upgrading a hypothesis.

On compliance: contractual terms of a private SPV agreement are exactly the kind of information an expert network call can turn into MNPI. Keep expert calls to industry structure, qualification timelines, and general practice; never to the specific contract. Document the provenance of every input, confirm licensing terms on customs data, and have compliance pre-clear the source list.

Finally, guard against the small-sample seduction of the base-rate case book. Twenty hand-picked cases with survivorship in what got disclosed will not generate a reliable probability. Use it to structure judgment, not to manufacture precision.

## 10. Timeline and deliverables

Days 1–3: fact sheet and entity chart, all primary documents pulled. Days 4–7: clause-level redline and extraction table, financial commitment reconciliation, rating agency review. Days 8–11: second-source corroboration across the four channels, base-rate case book. Days 12–13: event study and pricing tests, scenario model. Day 14: a decision memo containing the hypothesis scorecard with explicit posteriors and the evidence weighting behind each, the recommended expression with sizing and hedge, the kill criteria, and a monitoring dashboard — Taiwanese monthly revenue prints, EDGAR/MOPS/DART filing alerts on the named entities, rating actions, and OSAT revenue — with named owners and a weekly refresh.
