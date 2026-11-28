# NOTES (round 4: simplify, then improve)

**Status: FINISHED** (`DONE` written). 44 of 50 submissions used.

**Result: 0.9662 -> 0.9671** under the new scoring (confidence part 0.9573 -> 0.9572, cleaned part 0.9752 -> 0.9770),
with the file down from **576 to 437 lines**, module-level named constants from **48 to 38**, and run time from
33 s to 14 s a panel on the scorer (11 s locally on the largest practice panel). `solution/score.py` is submission
`h4-nolonepenalty`, byte for byte.

Checked on the delivered file: point-in-time (12 truncations over the 6 practice panels, 0 mismatching cells in the
three columns), runs on its own cleaned output on all 6 practice panels, numpy and pandas only, no gate tripped on
any hidden panel (low-signal share dropped 1.0).

## What was removed, and what each removal cost (each scored alone first)

| rule | lines / constants | cost alone | decision |
|---|---|---|---|
| joint count-and-ticket imputation (`K_BOTH`, `BOTH_CONF`) | 6 / 2 | -.0004 | removed |
| flood: a level as a constant number of extra transactions (`FLOOD_MIN`, `FLOOD_FIT`) | 40 / 2 | -.0002 | removed |
| pooled release of a level across a source's companies (`POOL_*`), and the second pass over every company | 35 / 4 | -.0008 (one panel, 001-2, -.0125) | removed; halves the run time |
| 'too few transactions left to rescale: impute' (`FAINT`) | 6 / 1 | .0000 | removed |
| doubled day bar when several sources are off the same day | 1 / 0 | (round 3: neutral; 1 row locally) | removed |
| `OWN_SURE` (a two-source move mostly one's own lifts the doubled bar) | 3 / 1 | (2 rows locally) | removed |
| `implied()`: separate weighted mean for imputed values | 13 / 0 | .0000 (identical) | removed |
| counting-noise floor from the source's own 28-day count | 3 / 0 | +.0002 | removed |
| 'second day running over 3 sds is imputed' | 3 / 0 | +.0004 (healthy rows broken -5.8 a panel) | removed |
| run level: three days running far off move the level at once (`RUN_DAYS`) | 9 / 1 | -.0001 (cleaned +.0017, conf -.0019) | removed |
| 'fresh level' distinction in the confidence (MV array) | 6 / 0 | .0000 | removed |
| flat -.2 on rows imputed with one sister | 1 / 0 | .0000 | removed |
| graded confidence of discarded rows, sloped yearly confidence, .995 -> .99 slope under 2 sds | 3 / 0 | .0000 together | flattened |

Sum of the costs of the first ten: about -.0012 (c02-clean2 = 0.9650). It was won back, and more, by the confidence
changes below.

**Probed and KEPT because removing costs more than about .001, or is broad:** one measure stuck (-.0232), measured
noise of the level medians (-.0218), partial share of short-window levels (-.0073), 'a level keeps the share it has
reached' (-.0038), count stuck with good dollars: count = dollars / ticket (-.0026), 14-day window (-.0018), the
'steady' test (-.0018), quiet-day noise floor (-.0016), fallback for short histories (-.0015), mirror reading of a
wrong count (-.0010, 15 of 18 panels), 'a level that has ended is dropped on its second day' (-.0008, 12 panels),
two-source sharing (-.0007, 15 panels), lower bar after recent repairs (-.0007: borderline, kept as the only rule
aimed at intermittent faults, 2 lines).

**Kept without a hidden-score reason:** the common level (`MAJORITY_OF`). Removing it changes nothing on the 18 hidden
panels, but on practice task 005 it changes 3170 rows by 25%: a lasting ticket shift of one source of four is
otherwise left split over its three sisters for three years. The hidden panels do not contain the case; new data may.
Not probed: column swap (32629 scored rows), the yearly pattern (named in the instruction), the THIN_* rules (gate),
median-for-level / weighted-mean-for-day (round 3: +.0014).

## What was changed, and why (all in the confidence; no new detection rule)

1. **Kept rows above 3 sds are doubted much faster (q4, +.0007).** .95 at 3 sds falling to .20 at 4 and beyond (was
   .50). Under the new scoring there is no penalty for going under .5, and the first days of a step, ramp or
   multi-day fault sit exactly there. Nothing is gained by doubting between 2 and 3 sds (q3), nor by a steeper
   curve (q8).
2. **One curve for every kept row: rescaled rows are doubted like as-reported ones (q7 vs q6, +.0013).** A rescaled
   row far from its level is on a level that is changing or has ended; before, it lost at most .12.
3. **Run evidence (+.0006 with 2 in place: q7 vs q10).** Two days running on the same side count as sqrt(2) times the
   weaker of the two. A level that lags leaves its rows on one side day after day. This replaces, as doubt, what the
   removed second-day rule did as imputation. Three days (q11, q14) is worse: slow drifts sit on one side and are right.
4. **A row repaired by the mirror reading takes the imputed confidence (h2, +.0003).** It was taking the minimum with
   the other measure's 'kept' confidence, which stood out only because of the wrong count.

Constants of the confidence curve are written in `confidence()` with a comment each (2, 3, 4 sds; .995 / .95 / .20).

## How the new score behaves (worked out from results; use before spending a submission)

- cleaned part = mean repair_share over the 8 kinds x (1 - healthy rows broken / problem rows). **One broken
  healthy row a panel costs about .00024 of the cleaned part**, .00012 of the total. The baseline's 33 a panel cost
  as much as half of all unrepaired problems. Now 22.1.
- confidence part ~ 1 - 4 x (half the mean of the kinds' ce + half the healthy ce): a kind's ce counts 1/4 of its
  value, the healthy ce counts double.
- A kind's ce is carried by few, heavily weighted rows (12 more wrong step rows: step ce +.0037). They are the first
  days of an episode.
- **The pattern of this round: acting early on thin evidence (imputing or moving a level) breaks healthy rows and
  now loses; doubting on the same evidence wins.** Second-day imputation, run level, K_DAY: each removal or raise cut
  broken healthy rows by 5-6 a panel. Lowering a bar (g1) or raising one (q9, x03-nosdq) both lost on one or two
  panels' episodes.
- Raising the confidence of imputed, stuck or rescaled rows loses a little (q1, q2), as in rounds 2 and 3.
- One episode on one panel still moves the total by .001 (001-2: an intermittent fault across a source's companies,
  helped by pooled release, 'home', flaky bar, K_DAY 4; 004-3: one false level on a healthy series under g1).

## Every submission

Probes x01-x04 were made from a scratch copy of the baseline with one off-switch per rule; the delivered file has the
rules really deleted and was checked byte-identical on the six practice panels against the switch version at each
step. 'lines / consts' are given where the file was a real candidate, 'probe' otherwise.

| name | score | conf | clean | lines | consts | what |
|---|---|---|---|---|---|---|
| baseline | 0.9662 | 0.9573 | 0.9752 | 576 | 48 | round 3's r18-final under the NEW scoring (step ce .0399, one-day .0332, ramp .0308, stuck .0234; healthy rows broken 33.2 a panel) |
| x01-noboth | 0.9658 | 0.9563 | 0.9753 | probe | | baseline without the joint count-and-ticket rule (K_BOTH, BOTH_CONF). -.0004: step ce +.0037 from 12 more wrong step rows; 5 tasks down a little. Under the .001 bar: REMOVE |
| x01-noflood | 0.9660 | 0.9570 | 0.9751 | probe | | baseline without flood() (FLOOD_MIN, FLOOD_FIT, ~40 lines). -.0002: step wrong rows +31, ce +.0011. REMOVE |
| x01-nopool | 0.9654 | 0.9565 | 0.9743 | probe | | baseline without the pooled release across companies (POOL_* x4, second pass over every company, ~35 lines; halves the run time). -.0008, of which panel 001-2 alone -.0125 (one intermittent episode: rs .990 -> .984). Under the bar: REMOVE (but it is the dearest removal so far) |
| x02-nofaint | 0.9662 | 0.9572 | 0.9751 | probe | | baseline without 'too few transactions left to rescale: impute' (FAINT). +.0000. REMOVE |
| x02-noflaky | 0.9655 | 0.9573 | 0.9736 | probe | | baseline without the lower day bar after 3 repairs in 14 days (K_FLAKY, FLAKY_N, FLAKY_DAYS). -.0007: intermittent rs .990 -> .979 (panels 002-3 -.0105, 001-2 -.0075), stuck ce -.0014 (5 fewer wrong). Under the bar but it is the only rule aimed at intermittent faults and costs 2 lines: KEPT for now, decide on the combined file |
| x02-nomirror | 0.9652 | 0.9557 | 0.9746 | probe | | baseline without the count/ticket mirror reading (MIRROR's main use). -.0010, 15 of 18 panels down, step ce +.0049, one-day rs -.003. KEEP the rule |
| x02-nostuckone | 0.9430 | 0.9396 | 0.9465 | probe | | baseline without 'one measure stuck' (count alone or dollars alone repeating; STUCK_ONE_DAYS, STUCK_ONE_MIN). -.0232: stuck rs .940 -> .732. ESSENTIAL, keep. Most stuck episodes are one measure only |
| x03-nohome | 0.9654 | 0.9565 | 0.9743 | probe | | baseline without 'a level that has ended is dropped on its second day back'. -.0008, 12 of 18 panels down (001-2 -.0108, the same panel the pooled release helps). KEEP (with the pooled release gone this is the only fast exit) |
| x03-nofew | 0.9647 | 0.9559 | 0.9735 | probe | | baseline without the 'under three same-weekday weeks: last three weeks, any weekday' fallback for the usual relation. -.0015 (002-3 -.0217, step wrong +23, healthy broken +4.1). KEEP |
| x03-nosdq | 0.9444 | 0.9191 | 0.9697 | probe | | baseline with the level medians' noise not measured (fixed 0.6 / 0.5 / 0.4 of the daily sd). -.0218, every panel down, ramp ce .031 -> .132. KEEP the measured sds. (Fixed at the floors 0.4 / 0.32 / 0.25 instead moves 5600 rows locally: not submitted) |
| x03-nopartial | 0.9589 | 0.9460 | 0.9719 | probe | | baseline with short-window levels all-or-nothing at K_LONG instead of a share rising from K_LO to K_HI. -.0073. KEEP the partial share |
| x03-nosteady | 0.9644 | 0.9547 | 0.9741 | probe | | baseline without 'most of the last week must be near the level' (NEAR, STEADY). -.0018, intermittent rs -.010, ramp ce +.0034. KEEP |
| c01-clean | 0.9646 | 0.9553 | 0.9739 | 471 | 38 | baseline with five rules really deleted: joint count-and-ticket (both), flood, pooled release, faint, doubled bar when several sources are off, OWN_SURE. -.0016 = the sum of the single costs (step wrong rows +52, panel 001-2 -.0128 from the pooled release). Each was under the bar alone; together they are not free. Working base from here |
| x04-noimplied | 0.9662 | 0.9573 | 0.9752 | probe | | baseline with imputed rows taken from the day's gap itself instead of the separate implied() weighted mean. Identical on every panel. REMOVE implied() (13 lines) |
| x04-nokeepshare | 0.9624 | 0.9513 | 0.9736 | probe | | baseline without 'a level that stands keeps the share it has reached'. -.0038. KEEP |
| x04-nopair | 0.9655 | 0.9566 | 0.9744 | probe | | baseline without the two-source sharing of a move by each one's own recent weeks. -.0007 but 15 of 18 panels down. KEEP |
| x04-nopred | 0.9664 | 0.9575 | 0.9752 | probe | | baseline without the counting-noise floor from the source's own 28-day median count (the quiet-day floor from the sisters' implied count stays). +.0002. REMOVE |
| x04-noquiet | 0.9646 | 0.9557 | 0.9734 | probe | | baseline without the quiet-day counting-noise floor. -.0016, 15 panels down, healthy rows broken +7.6. KEEP |
| x04-nosecond | 0.9666 | 0.9566 | 0.9766 | probe | | baseline without 'second day running over K_RUN sds, same side, is imputed'. +.0004, 16 of 18 panels up: healthy rows broken 33.2 -> 27.4 (cleaned +.0014), step ce +.0024 (conf -.0007). Under the old scoring this rule was worth +.0011; under the new one a broken healthy row costs more. REMOVE |
| q1-stuck98-scaledhi | 0.9645 | 0.9551 | 0.9739 | probe | | c01 + stuck rows' confidence .90 -> .98 and rescaled rows .97/.99 -> .985/.995. -.0001 vs c01: stuck ce UP .0007 (imputed stuck rows are 'not right' more often than the 17 'wrong' rows say), slow ce -.0004, step +.0004. NOT KEPT |
| q2-imphi | 0.9643 | 0.9548 | 0.9739 | probe | | c01 + imputed rows .82..98 -> .92..99. -.0003 vs c01 (one-day ce +.0008, stuck +.0005). NOT KEPT: imputed confidence should not go up under the new scoring either |
| q3-asislow | 0.9648 | 0.9557 | 0.9739 | probe | | c01 + as-reported rows doubted sooner (z=3: .95 -> .84, z>=4: .50 -> .24). +.0002 vs c01: step ce -.0038, ramp -.0034, intermittent -.0013, multi -.0008, but healthy ce +.0008 (costs 2x) and swap +.0008. About half the healthy cost is rows between 2 and 3 sds where little can be gained: next probe lowers only above 3 |
| c02-clean2 | 0.9650 | 0.9547 | 0.9753 | 447 | 38 | c01 + implied(), the second-day imputation and the own-count noise floor deleted. -.0012 vs baseline (conf -.0026: step ce +.0072 from 59 more wrong step rows; cleaned +.0001: healthy rows broken 33.2 -> 26.8). 14 s a panel (baseline 33 s). Base for the confidence work |
| q4-asis3deep | 0.9657 | 0.9561 | 0.9753 | probe | | c02 + as-reported rows above 3 sds fall faster (.95 at 3 -> .20 at 4, was .50). +.0007 vs c02: step ce -.0034, ramp -.0019, intermittent -.0018, multi -.0011; healthy ce +.0004. As much gained as q3 at half the healthy cost: nothing to gain between 2 and 3 sds |
| q5-runevidence | 0.9652 | 0.9552 | 0.9753 | probe | | c02 + two days running on the same side count as evidence sqrt(2) x the weaker of the two (confidence only; nothing imputed). +.0002: step ce -.0040, stuck ce +.0011 (unflagged first repeats sit on one side and are right), healthy +.0003 |
| q6-run-deep | 0.9656 | 0.9558 | 0.9753 | probe | | c02 + q4 + q5 together. +.0006 vs c02, i.e. LESS than q4 alone: with the deep curve the run evidence costs more on healthy rows (ce +.0010) than it wins. Run evidence NOT KEPT |
| q7-run-deep-scaled | 0.9669 | 0.9585 | 0.9753 | probe | | q6 + rescaled rows doubted on the same curve as as-reported rows (was at most -.12 at 4 sds): one curve for every kept row. +.0013 vs q6: step ce .0394 -> .0320, ramp .0283 -> .0265. A rescaled row far from its level is on a level that is changing or has ended. KEEP this part |
| q8-run-deeper | 0.9655 | 0.9557 | 0.9753 | probe | | q6 with a steeper curve (.95 at 3 -> .31 at 3.8 -> .15 at 4.8). Same as q6: the depth of the curve beyond q4's is flat |
| q9-kday5 | 0.9637 | 0.9541 | 0.9733 | probe | | q6 with K_DAY 4 -> 5. -.0019 vs q6: healthy rows broken 26.8 -> 21.3 as hoped, but intermittent rs .984 -> .960 (panel 001-2 -.0285), step ce +.0072 (33 more wrong). K_DAY stays 4 |
| q10-deep-scaled | 0.9663 | 0.9574 | 0.9753 | probe | | c02 + deep curve + rescaled rows on the same curve, WITHOUT run evidence. +.0013 vs c02 but .0006 under q7: once rescaled rows are judged on the curve the run evidence pays (step ce .0401 vs .0320: a level that lags leaves its rows on one side day after day). So run evidence KEPT after all, with the unified curve |
| x05-n14 | 0.9645 | 0.9535 | 0.9756 | probe | | q10 without the 14-day window (level = 28-day median if it agrees with the 7-day one, else the 7-day). -.0018: ramp ce +.0174, slow +.0097 (one-day ce -.0076, oddly). KEEP the 14-day window |
| x05-ncommon | 0.9663 | 0.9573 | 0.9752 | probe | | q10 without the common level. Identical on the hidden panels (one panel -.0002), yet on practice task 005 it changes 3170 rows by 25%: there a lasting ticket shift of one source of four is otherwise left split over its three sisters for three years. KEPT on that evidence: the hidden panels simply do not contain the case |
| x05-nonec | 0.9637 | 0.9572 | 0.9702 | probe | | q10 without 'count stuck, dollars good: count = dollars / usual ticket'. -.0026 (stuck rs .940 -> .903). KEEP |
| q11-run3 | 0.9668 | 0.9583 | 0.9753 | probe | | q7 with run evidence over 3 days too (sqrt(3) x the weakest of three). -.0001. NOT KEPT: two days is enough |
| q12-common3 | 0.9651 | 0.9563 | 0.9739 | probe | | q7 with the common level applied from 3 sources (MAJORITY_OF 4 -> 3; locally it un-splits the same task-005 shift a year earlier). -.0018 (002-1 -.0145, 004-2 -.0133; multi-day wrong +10, slow +10). NOT KEPT: with three sources two really can be off together |
| x06-norunlevel | 0.9668 | 0.9566 | 0.9770 | probe | | q7 without the run level (3 days running far off the same way move the level at once). -.0001: cleaned +.0017 (healthy rows broken 26.8 -> 22.1), conf -.0019 (multi ce +.0043, ramp +.0022, 15 more wrong step and ramp rows each). Same pattern as the second-day rule: acting early on thin evidence breaks healthy rows. Removable by the bar; next probe pairs the removal with 3-day run evidence in the confidence |
| q14-norunlevel-run3 | 0.9659 | 0.9548 | 0.9770 | probe | | x06 + 3-day run evidence. -.0010 vs q7: slow ce .0028 -> .0114 (a slow drift sits on one side for days and is right). NOT KEPT. Run evidence stays at two days |
| f3-norunlevel-tidy | 0.9668 | 0.9565 | 0.9770 | 439 | 38 | KEPT. q7 without the run level (= x06, checked byte-identical locally) + three cosmetic simplifications of confidence numbers: kept rows flat .995 up to 2 sds, yearly rows a flat .80, discarded rows a flat .05. Same score as x06. Checked: point-in-time (12 truncations over the 6 practice panels, 0 mismatching cells in the three columns), runs on its own cleaned output on all 6 panels, 14 s a panel |
| g1-klo2-khi5 | 0.9642 | 0.9533 | 0.9751 | probe | | f3 with the short-window level bar lower (K_LO 2.5 -> 2.0, K_HI 6 -> 5). -.0026: 10 panels up (ramp ce -.0054, 25 fewer wrong step rows) but panel 004-3 -.0484 (86 more wrong column-swap rows: one false level on a healthy series) and 001-2 -.0105; healthy rows broken +4.1. NOT KEPT: the bars stay |
| h1-nomoving | 0.9668 | 0.9565 | 0.9770 | 437 | 38 | KEPT. f3 without the 'fresh level' distinction in the confidence (rescaled rows .97 on a level four weeks do not yet agree on, .99 otherwise -> all rescaled rows .985): the MV array and its plumbing go. Identical score |
| h2-mirrorconf | 0.9671 | 0.9572 | 0.9770 | 438 | 38 | KEPT. h1 + a row repaired by the mirror reading (count imputed, dollars kept) takes the imputed confidence instead of the minimum with the other measure's 'kept' confidence: that measure stood out only because of the wrong count, and under the deep curve it dragged a repaired row down to .2. +.0003 (step ce -.0017, one-day -.0007; 5 panels up, 1 down). One line, no constant |
| h3-runkept | 0.9668 | 0.9566 | 0.9770 | probe | | h2 with run evidence only when yesterday was kept (not imputed). -.0003: stuck ce -.0015 (the day after a stuck run no longer doubted) but step ce +.0034 (an imputed first day followed by a moderately-off second day is a step's start, and doubting it is right). NOT KEPT |
| h4-nolonepenalty | 0.9671 | 0.9572 | 0.9770 | 437 | 38 | **the delivered `solution/score.py`** (byte-identical to this submission). h2 tidied (comments, an unused return value) and without the flat -.2 on rows imputed with one sister only. Identical score on every panel |

## Tried and not kept / not submitted

- Fixed level-noise fractions at the floors 0.4 / 0.32 / 0.25 instead of measured sds: moves 5600 rows locally, and
  x03-nosdq showed how sensitive this is. Not submitted.
- Removing `growing` (THIN_EDGE): changes 1994 blank rows locally, gate risk. Not submitted.
- Excluding only a stuck yesterday from the run evidence: h3 says about +.0002 (stuck ce -.0015). A new branch for
  under .001: left out.
- Joint count-and-ticket evidence as doubt instead of imputation: at most the +.0004 the removed rule had. Left out.
- K_DAY 4.5: from q9 (K_DAY 5) I expect a small loss; not submitted.

## Warnings for the next person

- **Local testing this round used each practice panel on its own** (run, diff of outputs between two versions,
  point-in-time, own-output). Round 3's notes describe a 'truth' built by lining the practice panels up against each
  other: the brief forbids that now and nothing in this round used it. So every keep / drop decision here rests on
  the hidden-panel score of a single-change submission, not on a local estimate.
- The removals of flood, the joint rule and the pooled release cost .0014 together and are kept out for simplicity,
  as the brief asks. If score matters more than lines, the pooled release (+.0008, but all of it on one panel) is the
  first to put back; it doubles the run time.
- The common level is kept on practice evidence alone (see above). Do not remove it on the strength of the hidden
  score.
- Do not lower the level bars or the day bar to catch first days: it was tried in both directions this round and
  loses on single episodes. First days are now handled by doubt (the curve and the run evidence).
- Where the remaining loss is: stuck repair_share .940 (imputed values are no closer than the sisters' noise, and
  flagging repeats earlier did not help in rounds 2-3), step / one-day / ramp ce about .03 each (first days under
  3 sds, which nothing local can tell from noise), 22 healthy rows broken a panel (real bursts of small sources).
