# S8 — plan (claude-opus-5)

> Do round-lot orders identify retail flow that is profitable to trade against?

---

# Research Plan: Do round‑lot orders identify retail flow that is profitable to trade against?

## 1. Sharpening the question before any data is pulled

The idea as stated bundles three separable claims. The analyst should treat them as sequential gates, because failing gate 1 makes gates 2 and 3 uninterpretable.

**Gate 1 — Classification.** Does trade/order size being a round lot (a multiple of 100 shares, and especially exactly 100) carry incremental information about whether the flow originated from a retail account, conditional on what we already observe (venue, subpenny price, price level, time of day)?

**Gate 2 — Toxicity.** Conditional on the flow being round‑lot, is it *non‑toxic* at the market‑making horizon — i.e., does a liquidity provider who takes the other side earn a positive realized spread after the post‑trade midpoint drift?

**Gate 3 — Tradability.** Does an aggregated, signed round‑lot imbalance signal predict returns at horizons a real fund can act on (1–20 days), with the *sign* that says "fade it," and does the resulting long‑short portfolio survive transaction costs, capacity constraints, and controls for short‑term reversal?

Two framing decisions to lock in on day one. First, "round lot" is ambiguous between *executed trade size* (what TAQ shows) and *submitted order size* (what ITCH shows). We test both, but the primary analysis is on trade size, because that is what any signal‑based strategy can actually observe. Second, "profitable to trade against" means something different to a wholesaler (Gate 2 — capture the spread, avoid adverse selection) than to an asset manager (Gate 3 — the flow is wrong and reverts). Report both; they can and do diverge.

**Pre‑registered success criteria.** Gate 1 passes if round‑lot status raises the odds of a retail label by a factor of at least 1.3 in a logit with venue and subpenny controls, and if the Matthews correlation between "round lot" and the retail label exceeds 0.10. Gate 2 passes if the 5‑minute realized spread on 100‑share prints exceeds that on size‑matched non‑round prints (99, 101, etc.) by at least 1.5 basis points with |t| > 3. Gate 3 passes if the value‑weighted decile long‑short earns |t| > 3.0 (the Harvey–Liu–Zhu hurdle, not 2.0), a net‑of‑cost Sharpe above 0.7, and at least $150mm of capacity at 5% of ADV participation. Write these down before running anything.

## 2. Data

**Trades and quotes.** NYSE Daily TAQ via WRDS, January 2016 through the most recent full quarter. Nanosecond timestamps, trade size, exchange code, sale conditions, and the full NBBO. Universe: CRSP share codes 10 and 11, price above $3, listed NYSE/Nasdaq/NYSE American/Arca, at least 250 trading days of history, excluding the first 10 days post‑IPO. That is roughly 3,000 names. For the trade‑level microstructure work (Gate 2), subsample to 500 stocks stratified into five market‑cap quintiles × three price tiers (<$20, $20–$100, >$100), because price level is the key confound for roundness. Scale to full universe only after the design is stable.

**Retail labels — three imperfect ground truths, deliberately triangulated.**

- *BJZZ subpenny algorithm.* For off‑exchange prints (exchange code D), compute Z = 100 × mod(P, 0.01). A wholesaler filling a retail buy prices just inside the ask ($9.9999 against a $10.00 offer), giving Z ≈ 0.99; a retail sell prices just above the bid, giving Z ≈ 0.01. So Z ∈ (0.6, 1) → retail buy, Z ∈ (0, 0.4) → retail sell. The analyst should re‑derive this from first principles on a sample day rather than trusting my statement of the convention.
- *FINRA OTC Transparency data* (otctransparency.finra.org), weekly non‑ATS volume by symbol by firm, free. Sum the volume attributed to the wholesalers — Citadel Securities, Virtu Americas, G1 Execution, Jane Street, Two Sigma Securities, UBS Securities — and divide by total symbol volume to get a symbol‑week retail‑intensity measure. This is the most reliable label we have and it does not depend on any subpenny heuristic.
- *Robintrack* holdings snapshots (May 2018 – August 2020). Daily change in the number of Robinhood accounts holding each symbol is a directional retail‑buying proxy for that window. Use it as a validation cross‑check, not as the main label — Robinhood is a biased slice of retail.

**Order‑level data (secondary).** LOBSTER‑reconstructed Nasdaq TotalView‑ITCH for 100 stocks × 40 randomly selected days spread across the sample. Two uses: (a) it gives the true aggressor side, so we can measure Lee–Ready error rates by size bucket; (b) it gives *submitted* order sizes and cancellations, so we can distinguish round‑lot fills from round‑lot orders.

**Returns and characteristics.** CRSP daily for delisting‑adjusted returns, prices, shares outstanding, volume. Compustat for book equity. Ken French's library for factors. Intraday returns constructed from TAQ NBBO midpoints, never from trade prices.

## 3. Construction

**Trade signing.** Lee–Ready with the Holden–Jacobsen interpolated‑timestamp correction and zero quote lag; use the prevailing NBBO from the millisecond immediately preceding the trade. Drop trades with sale conditions indicating non‑standard execution (odd sale conditions, out‑of‑sequence, derivatively priced, auction prints handled separately). Validate the signing against ITCH aggressor flags and report the error rate *by size bucket* — if Lee–Ready misclassifies 100‑share trades at a different rate than 137‑share trades, the entire study is contaminated and needs a different signing approach.

**Size buckets.** Exactly 100; multiples of 100 from 200–400; exactly 500; exactly 1,000; other multiples of 100; odd lots (1–99); mixed lots (>100, not a multiple of 100). Also construct a dollar‑notional partition so that 100 shares of a $400 stock and 100 shares of a $8 stock are not pooled.

**Sequential aggregation.** A single parent order often prints as many child fills. Run everything twice: on raw prints, and on prints aggregated within (stock, venue, side, price, 50ms window). If the round‑lot effect survives only on raw prints, it is an artifact of how algorithms slice.

**Signal.** Round‑lot order imbalance for stock *i* on day *t*:
RLOIB = (buy round‑lot dollar volume − sell round‑lot dollar volume) / (total round‑lot dollar volume), and separately using trade counts. Compute the identical object for BJZZ‑retail flow, for non‑round flow, and for odd‑lot flow, so all four can be horse‑raced in the same regression.

## 4. Methodology

**Stage 1 (Gate 1): is roundness informative about retail?**
Build a trade‑level logit on the ITCH/BJZZ sample: P(retail label) on round‑lot dummies, venue dummies, log price, log trade size, spread, time‑of‑day, with stock‑day fixed effects. Report the marginal contribution of roundness. Then run the confusion matrix: precision, recall, Matthews correlation of "round lot" as a retail classifier. Separately, run a stock‑week panel regression of the wholesaler volume share (FINRA) on the round‑lot volume share, with stock and week fixed effects — this is the label‑independent version and the one I would trust most.

Expect this stage to be the point of maximum surprise. The modal lit‑exchange trade is 100 shares because that is the default algorithmic child size, and since the spread of fractional‑share and dollar‑denominated investing after 2019, a great deal of retail flow arrives in *odd* sizes ("buy $500 of NVDA" → 2.7 shares). It is entirely plausible that the sign has flipped over the sample: round lots signalled retail in 2016 and signal algorithmic institutional slicing in 2025. Run Stage 1 year by year and plot the coefficient path before doing anything else.

**Stage 2 (Gate 2): toxicity, identified off a discontinuity in size.**
For every trade compute effective half‑spread ES = q(P − M₀)/M₀, price impact PI = q(M_{t+τ} − M₀)/M₀ for τ ∈ {1s, 10s, 60s, 5m, 30m}, and realized spread RS = ES − PI (the liquidity provider's gross profit). Regress RS on size‑bucket dummies with stock‑day and half‑hour fixed effects, controlling for realized volatility, quoted spread, depth, and log size; two‑way cluster by stock and date.

The clean identification is a **donut regression discontinuity in trade size**: compare 100 vs. {96–99, 101–104}, 500 vs. {490–499, 501–510}, 1,000 vs. the analogous neighbors. Economically, a 101‑share order and a 100‑share order convey the same information; behaviorally, roundness is a marker of unsophisticated order construction. Any RS differential across that boundary is close to a causal estimate of the roundness effect, purged of price level, liquidity, and volatility confounds that plague the level comparison.

**Stage 3 (Gate 3): return predictability.**
Fama–MacBeth cross‑sectional regressions of returns at t+1, t+2…t+20 on the decile rank of RLOIB, with controls: log market cap, book‑to‑market, prior‑month return, prior 12‑2 momentum, Amihud illiquidity, turnover, idiosyncratic volatility, and — critically — the BJZZ retail imbalance and the previous week's return. Newey–West with 5 lags. Then decile portfolio sorts, value‑weighted and equal‑weighted, formed on day t and held 1, 5, and 20 days with overlapping Jegadeesh–Titman portfolios. Report raw returns, FF5+MOM+STR alphas, hit rate, and turnover. Signal is computed from data through the close of day t; positions are entered at the open of t+1 and returns measured open‑to‑open thereafter. Never measure returns using the same day's closing price that the signal used.

**Stage 4: costs and capacity.**
Cost model: half the stock‑day effective spread plus a square‑root impact term, κ·σ·√(participation), κ calibrated to 0.5, with participation capped at 5% of 21‑day ADV. Report the gross alpha, net alpha, break‑even one‑way cost in basis points, and the AUM at which net alpha reaches zero. If the break‑even cost is below 15 bps in a portfolio whose median name has a 12 bp spread, the strategy is dead and should be reported as dead.

## 5. Validation

Split the sample: build and specify everything on 2016–2020, then lock the code and run once on 2021–2025. Report both, and report the ratio.

Three placebos. First, run the identical pipeline on mixed‑lot imbalance, where no retail story applies; a similar result implies we are picking up generic order‑flow reversal, not retail. Second, randomly permute the size labels within stock‑day and confirm the effect vanishes. Third, run the RD at non‑focal thresholds (e.g., 300 vs. 297/303 should be weaker than 500 vs. 497/503 if roundness salience drives the result).

Cross‑sectional consistency checks that must hold if the retail story is right: the effect should be stronger in stocks with high FINRA wholesaler share, stronger in low‑priced and high‑retail‑attention names, stronger in the Robinhood‑heavy 2020 window, and weaker in stocks whose flow is dominated by institutional algorithms. If the alpha is *uncorrelated* with independent retail intensity measures, the mechanism claimed in the title is wrong even if the returns are real.

Finally, benchmark against the direct alternative: does RLOIB add anything to the BJZZ retail imbalance in a joint regression? If BJZZ subsumes it, the honest conclusion is that roundness is a redundant and noisier proxy.

## 6. Pitfalls I would watch for

**The sign of the retail return relation is not obvious.** Boehmer, Jones, Zhang and Zhang find retail order imbalance *positively* predicts returns over the following week; Kaniel, Saar and Titman find the same at short horizons. The premise "profitable to trade against" may be backwards. Run the test two‑sided and be willing to write up "retail round‑lot flow is mildly informed, and the profitable trade is to follow it."

**BJZZ is a degrading label.** Barber, Huang, Jorgensen and Odean document roughly 30% misclassification, and wholesaler execution has drifted toward round pennies and midpoints, which the algorithm cannot see at all. Recall has fallen materially since 2020. This is why the FINRA wholesaler data is in the plan.

**Mechanical reversal masquerading as alpha.** Any signed order imbalance predicts reversal because of temporary price pressure and bid‑ask bounce. Measure returns midpoint‑to‑midpoint, skip a full day between signal and entry, and check that the effect survives after controlling for the contemporaneous return and the prior week's return.

**Roundness is correlated with everything.** Low‑priced, wide‑spread, low‑liquidity stocks have more 100‑share prints, and realized spreads are mechanically larger there. Stock‑day fixed effects plus the size RD are the defenses; do not rely on cross‑sectional controls alone.

**Realized spread is not an achievable P&L.** It measures what the liquidity provider earned on trades that happened, not what an investor could earn by choosing to trade against round lots. Outside of wholesaling and exchange retail liquidity programs, no one can select counterparties. Frame Gate 2 as an estimate of wholesaler economic rents, and keep Gate 3 as the only genuinely investable claim.

**Regime breaks.** Commission‑free trading (late 2019), fractional shares, the 2021 retail episode, the SEC Market Data Infrastructure rule's tiered redefinition of a round lot, and the 2025 tick‑size amendments all move the object under study. Estimate everything year by year and run a Bai–Perron break test on the annual coefficient series. A stable full‑sample coefficient that is the average of a positive first half and a negative second half is worse than useless.

**Multiple testing.** Seven size buckets × five horizons × two weighting schemes is seventy tests. Designate exactly one primary specification in advance (exactly‑100 bucket, dollar‑weighted imbalance, 5‑day horizon, value‑weighted). Everything else is secondary and reported with Benjamini–Hochberg at 10%.

## 7. Timeline

Weeks 1–2: data plumbing, TAQ cleaning, trade signing, and the ITCH validation of Lee–Ready error rates by size. Deliverable — the time series of the share of volume executed at exactly 100 shares, split by venue, 2016 to present. This one chart may settle the question.

Weeks 3–4: Gate 1, all three labels. Deliverable — is roundness a retail classifier, and has that changed?

Weeks 5–6: Gate 2, the size RD on realized spreads.

Weeks 7–8: Gate 3, cross‑sectional predictability and cost/capacity analysis.

Week 9: out‑of‑sample run on the locked 2021–2025 period, placebos, write‑up.

The plan is designed to fail fast. If the Week‑1 chart shows that 100‑share prints are 40% of lit volume and that off‑exchange retail flow has migrated to odd sizes, the honest recommendation at the end of Week 2 is to redirect the effort toward odd‑lot and subpenny identification instead — and that is a successful outcome for a two‑week spend.
