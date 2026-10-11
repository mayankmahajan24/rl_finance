# Part 0 — genuinely well-posed

*Written by me, before touching Claude. Corresponds to seed **S1**.*

## Does Kalshi adoption cannibalize DraftKings wallet share?

The readout is: among users already active on DraftKings, does a first Kalshi transaction coincide with lower subsequent DraftKings retention, spend, or transaction frequency versus DraftKings users who never use Kalshi? The primary pair is DraftKings-to-Kalshi; use DraftKings-to-FanDuel only as the switching benchmark.

Use transaction-level credit card and bank deposit data mapped to DraftKings, Kalshi, and FanDuel activity. Start cohorts in 2021, aggregate each user's activity to monthly and weekly periods, and produce separate credit-card, bank-deposit, and combined source cuts. For Kalshi, use a 3-month forward window because history is short.

Compare two groups of DraftKings users around the month or week when the first group tries Kalshi for the first time. The first group is users who were active on DraftKings and then made their first Kalshi transaction. The comparison group is DraftKings-active users from the same time period who never used Kalshi; use a stable 5% sample of those users so the analysis is repeatable and not too expensive to run. Track DraftKings activity before and after the Kalshi start date, including whether users remain active, how much they spend or deposit, and how often they transact. Show the raw paths, the gap between Kalshi adopters and non-adopters, and the percent gap versus the comparison group. Adjust for any average pre-Kalshi gap between the two groups so the post-Kalshi change is easier to read.

Before interpreting results, confirm the merchant mapping for each product, check that the Kalshi adopter sample is large enough, and make sure adopters and non-adopters looked reasonably similar before the first Kalshi transaction. Compare credit-card, bank-deposit, and combined results for the same directional message, and use weekly versus monthly views to understand timing. Treat the output as directional evidence, not proof of causality, because Kalshi adopters may be different types of users, observed deposits/spend are not the same as betting handle, and Kalshi's short history may leave limited post-adoption data.

---

## Why this one is well-posed

The caveats in the last paragraph are the three things that actually limit the read, and each is named rather than gestured at: **selection** (adopters may be different users), **the measurement gap** (deposits and spend are not betting handle), and **sample truncation** (Kalshi's short history bounds the post-adoption window). None of them is fatal, and each has a stated mitigation in the design — a matched never-adopter comparison group, multiple data-source cuts that must agree directionally, and a pre-period gap adjustment.

Compare with the paired write-up in `plausible_but_flawed_mau_arr.md`, which uses the same toolkit — third-party panel data inferring a company's reported financials — and names four caveats that are all true and none of which is fatal, while the thing that actually kills it goes unmentioned. Same shape, opposite quality. That contrast is the argument this appendix is making.
