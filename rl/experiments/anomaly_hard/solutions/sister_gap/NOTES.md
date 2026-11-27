# NOTES (round 2)

**Result: 0.9579 -> 0.9610** (confidence part 0.9408 -> 0.9450, cleaned part 0.9750 -> 0.9771), 28 of 40
submissions used. `solution/score.py` is submission `p24-final` (one comment line reworded since; output byte-identical). Round 2 is
finished (`DONE` written).

Started from `solution/score.py` = round 1's best, `a23-mirrorboth` (0.9579).

## What changed in the solution, and why

Five changes are in, each one scored on its own before it was kept:

1. **Quiet days (p03, +.0014).** The counting-noise floor of the count (1/sqrt(n)) used the source's 28-day median
   count only. On a day that is quiet for the whole business (a holiday) every source has few transactions, so the
   floor now also uses the count the sisters imply for today. Fewer false repairs and fewer distrusted healthy rows.
2. **A level that has ended is dropped on its second day (p07-b3, +.0004).** Before, a level stayed until the 7-day
   median turned (4 days). Now: the second day running more than K_RUN sds off the level in force, same side, and
   nearer the usual relation than the level, restarts the level windows at the first of the two days.
3. **Two usable sources (p10, +.0007).** With exactly two sources reporting, neither can say which one moved, and
   the old code split a shift between both (both wrong). The day's move of the gap is now shared in proportion to
   each source's squared move against its own cleaned values on the same weekday of the last 4 weeks; a source with
   90% of it is also held to the normal day bar instead of the doubled one. The noise sd is still measured on the
   whole gap (measuring it on the shared gap shrinks it and floods healthy rows with repairs: seen in the simulator).
4. **Confidence of imputed rows by how far over the bar they were (p16, +.0003), no-sister rows 0.99 (p17, +.0001).**
   0.82 at the bar rising to 0.98 at twice the bar (was 0.90..0.97): repairs just over the bar are the false alarms.
5. **Count and ticket jointly (p20, +.0002).** A count off under good dollars moves count and ticket opposite ways.
   Where neither is over its own bar but each is over 2 sds and the two are over 4.4 sds jointly (same chance rate as
   4 sds on one measure, chi-square with 2 df), the count is imputed and the dollars kept.

Checked on the delivered file: point-in-time (5 truncations over 4 practice panels, 0 mismatching rows in any of the
three columns), runs on its own cleaned output on all 6 practice panels (no row under 0.5 confidence on either run,
so no alerts on either), about 19 s a panel on one core, numpy and pandas only.

## Every submission

| name | score | conf | clean | what |
|---|---|---|---|---|
| baseline | 0.9579 | 0.9408 | 0.9750 | unchanged a23-mirrorboth (same as round 1; the service is deterministic, ~2-3 min per submission) |
| p01-alert | 0.7290 | 0.4830 | 0.9750 | PROBE: as-reported rows' confidence falls to 0.20 (was 0.50) at 4 sd. 53 alerts/panel, precision 0.029 -> confidence part roughly x(0.5+0.5*precision). NEVER go under 0.5 on a kept row unless certain |
| p02-confhi | 0.9573 | 0.9395 | 0.9750 | PROBE: imputed 0.96..0.99 (was 0.90..0.97), rescaled 0.985/0.995 (was 0.97/0.99). Worse: imputed/rescaled rows are not right that often; calibration is already near its best |
| p03-quiet | 0.9593 | 0.9424 | 0.9761 | KEPT. Counting-noise floor of the count also from the count the sisters imply today (a quiet day for the whole business has few transactions in every source). Better on 5 of 6 tasks |
| p04-stuck2 | 0.9592 | 0.9423 | 0.9762 | STUCK_DAYS 3 -> 2 (flag the first identical repeat). No change at all in the stuck numbers (same in round 1's a02). Not kept |
| p05-turn-b | 0.9597 | 0.9434 | 0.9761 | Two days running > K_RUN sds off the level in force, same side = a new state: the level windows restart at its first day. step ce .060->.054, multi .019->.015, ramp .043->.041, BUT slow ce .002->.025 (a standing level was dropped for 2 days at each restart) |
| p05-turn-b1 | 0.9525 | 0.9367 | 0.9682 | as p05-turn-b plus a level taken from 2 days after a restart (instead of 4). Bad: task 001 fell to 0.903, 811 wrong step rows, healthy rows moved doubled. A level from two days locks in wrong states when two sources of a company are off at once |
| p06-turn-home | 0.9598 | 0.9434 | 0.9762 | as p05-turn-b, but a turn away from a standing level keeps that level until the new state has 4 days. slow ce still .025 |
| p07-b3 | 0.9597 | 0.9431 | 0.9762 | only the 'home' half: a level in force is measured afresh once the source is two days back towards its usual relation. Clean: slow ce back to .002, healthy rows moved 69 -> 65, step ce .060 -> .058 |
| p07-b4 | 0.9548 | 0.9378 | 0.9717 | only the 'onset' half (restart when no level is in force). Bad on its own (787 wrong step rows): a short fault now starts a level, and without the 'home' half nothing ends it quickly |
| p08-turn-ref | 0.9597 | 0.9433 | 0.9761 | p06 with 'off' measured against the last 28-day median when no level is in force. slow ce still .025: wrong guess at the cause |
| p09-fresh | 0.9585 | 0.9411 | 0.9758 | onset tried as a 'fresh window, used only if it shows a level' on top of the home half. Worse, slow ce still .025. Onset restarts abandoned (5 submissions): every form of them costs slow drifts ~.023 ce; the simulator does not reproduce that, so do not trust it on slow drifts |
| p10-pair | 0.9604 | 0.9437 | 0.9771 | KEPT. Exactly two usable sources that day: the day's move of the gap is shared between the two in proportion to each one's squared move against its own last 4 same weekdays (cleaned), so the one that jumped takes it; noise sd still measured on the whole gap. Up or flat on all 6 tasks (004 +.003), healthy rows moved 65 -> 59 |
| p11-kday35 | 0.9589 | 0.9422 | 0.9757 | K_DAY 4.0 -> 3.5. Worse (healthy rows moved 59 -> 77, swap/intermittent/slow ce up) and one-day ce did not move: missed one-day faults just under the bar are not what costs there |
| p12-ownconf | 0.9533 | 0.9294 | 0.9771 | imputed rows' confidence from the share of the gap noise that is the source's own (0.55..0.97, median ~0.87). Much worse: one-day ce .039->.052, multi .018->.032, intermittent .006->.015. Imputed values are right far more often than that (the grader's tolerance is generous); intermittent ce .0055 says imputed rows are right ~99% |
| p13-imphi | 0.9598 | 0.9425 | 0.9771 | PROBE: imputed confidence 0.97..0.99 (was 0.90..0.97). Worse by .0012 conf although the kinds' ce barely moved: the loss is on healthy rows imputed by mistake (false alarms cost extra) |
| p14-mvlo | 0.9602 | 0.9433 | 0.9771 | PROBE: rescaled rows on a short-window level 0.93 (was 0.97). Slightly worse |
| p15-alone85 | 0.9589 | 0.9407 | 0.9771 | PROBE: rows with no sister that day 0.85 (was 0.97). No kind's ce moved at all, healthy ce .0020 -> .0034: no scored problem sits on single-source days, and they are ~6.5% of healthy rows. Healthy ce costs about 2.1x its value in the confidence part |
| p16-impslope | 0.9607 | 0.9442 | 0.9771 | KEPT. Imputed confidence 0.82 at the bar rising to 0.98 at twice the bar (was 0.90..0.97): a repair just over the bar is more often a false alarm. healthy ce .0020 -> .0018, stuck ce down |
| p17-alone99 | 0.9605 | 0.9438 | 0.9771 | KEPT. Rows with no sister that day 0.99 (was 0.97) |
| p18-impslope2 | 0.9606 | 0.9440 | 0.9771 | imputed 0.72..0.99: no better than p16 (plateau) |
| p19-lonebar | 0.9603 | 0.9434 | 0.9771 | as-reported rows judged against the doubled bar where it applied (higher confidence on 'several sources off' days). healthy ce -.0001 but step ce +.0016: some of those rows are a step's first days. Not kept |
| p20-both | 0.9610 | 0.9450 | 0.9771 | KEPT (= p10 + p16 + p17 + this). Count and ticket both off, opposite ways, each over 2 sds and 4.4 sds jointly (chi-square equivalent of the 4-sd bar on one measure), neither over its own bar: read as a wrong count, count imputed, dollars kept. step ce .058 -> .054, one-day .039 -> .038; swap ce .002 -> .004 (5 more wrong rows). Up on 5 of 6 tasks |
| p21-both38 | 0.9613 | 0.9457 | 0.9769 | K_BOTH 4.4 -> 3.8. +.0003 overall (step ce .054 -> .051) but only 2 of 6 tasks up (001 +.002), 3 slightly down, healthy rows moved 61 -> 66. Not kept: 4.4 is the value with a reason (same chance rate as the 4-sd bar) |
| p22-ticketfew | 0.9610 | 0.9452 | 0.9769 | ticket noise widened on days with fewer transactions than usual (sampling variance 1/n). Neutral: conf +.0002, clean -.0002 (one-day repair .974 -> .972). Not kept |
| p23-flat | 0.9609 | 0.9448 | 0.9770 | count level and ticket level that cancel (a count shifted under good dollars): dollars left as reported. Neutral: step wrong rows 328 -> 321 but ramp 82 -> 89. Not kept |
| p24-final | 0.9610 | 0.9450 | 0.9771 | **the delivered `solution/score.py`** (p20-both with a dead leftover block removed and the header brought up to date): identical result, as it should be |
| p25-bothquiet | 0.9611 | 0.9450 | 0.9771 | the joint count-and-ticket test with the ticket's z shrunk on days with fewer transactions than usual. +.0001, no task down, 5 fewer wrong rows; not kept (one more constant and formula for a gain that small) |

## What I learned about the score (use this before spending a submission)

- **Never put a kept row under 0.5 unless certain.** p01: 53 alerts a panel at 3% precision cut the confidence part
  roughly by the factor (0.5 + 0.5 x alert precision), 0.94 -> 0.48. The solution raises no alerts at all (discarded
  thin rows at 0.05 are not counted as alerts).
- Fitted on round 1's 26 results: confidence loss ~ 0.17 x (sum of the eight kinds' confidence_error) + a constant
  ~0.02; cleaned loss ~ 0.054 x sum(1 - repair_share) + 0.9 x (1 - share_left_intact) + ~0.013.
- **Healthy rows are expensive.** Healthy confidence_error costs about 2.1x its value in the confidence part (p15),
  i.e. ~12x one kind's; a healthy row moved beyond noise costs in both parts. The ~60 such rows a panel cost about
  0.003 of the score. Anything that lowers a bar (K_DAY 3.5 in p11, K_BOTH 3.8 in p21) pays for its repairs with these.
- A kind's confidence_error moves a lot on very few rows (slow: +1 wrong row, .002 -> .025), so a problem's first
  days must weigh heavily. One early mistake on one episode is expensive.
- Imputed values are right far more often than the gap's noise suggests (intermittent ce .0055): the tolerance is
  generous. Do not lower imputed confidence across the board (p12), and do not raise it either (p13, p02): the
  present levels are at the optimum, only the slope with distance helped.
- Rows with no sister that day carry no scored problem (p15) and are ~6.5% of healthy rows.
- First repeats of a stuck feed are not what stuck loses on: flagging them changed nothing (p04, and a02 in round 1).

## Tried and not kept

- **Restarting the level windows when a new state begins ('onset'), 5 submissions (p05, p06, p08, p09, p07-b4).** It
  helps steps, multi-day and ramps (step ce .060 -> .054) but every form of it costs slow drifts ~.023 ce, and on its
  own (without change 2) it is plainly bad. I did not find the cause; my simulator does not reproduce it. A level
  taken from only two days (p05-turn-b1) is worse still: it locks in wrong states when two sources are off at once.
- Confidence probes: p02, p12, p13, p14, p18, p19 (see table). The as-reported curve was already tuned in round 1.
- K_DAY 3.5 (p11), stuck on the first repeat (p04), ticket noise by transactions (p22), dollars as reported under
  cancelling levels (p23), K_BOTH 3.8 (p21, +.0003 but up on only 2 of 6 tasks), p25 (+.0001).
- Simulator only, not submitted because no gain or worse there: FLAKY_N 2; a third-day-running rule at 2.5 sds;
  imputing at the source's recent relation instead of the year's; weighting sisters by how tightly each tracks the
  source when imputing; not using a stuck source as a sister; the doubled bar only when under two sisters are left;
  sharing a gap by own moves also when one sister is left because the others were marked off.

## Warnings for the next person

- **A local simulator helps but misleads.** I planted known problems on the baseline's cleaned practice panels
  (scratchpad only, nothing of it is in this folder). It correctly predicted p05-turn-b1's failure and the pair
  change's direction, but it said the onset restarts were a large win when the service said a loss, and its totals
  for step/slow swing on one long episode in a two-source company. Use it to find mechanical faults, never to rank
  close variants.
- Changes worth ~.0002 are at the noise of what six tasks can tell apart; I kept only those up on at least five tasks
  with a reason behind the number. The gains left are of that size: the plateau is real at ~0.961.
- Where the remaining loss is, by my reading: the first day or two of a step or ramp before it clears the bar (no
  evidence yet, and confidence cannot go under 0.5 without raising alerts), and ~60 healthy rows a panel repaired by
  mistake. Stuck's repair_share (0.929) did not move under anything I tried.
- If you revisit onset restarts, first find out what a 'slow' episode looks like at its start in the hidden data;
  that is the piece I am missing.
