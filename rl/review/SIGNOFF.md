# Sign-off: from merged code to a releasable sample

Every step here is a human decision; the code refuses to release until each is recorded. Run from the
repo root, in this order. Gold review comes before instrument approval: several files are both gold
inputs and instrument files (kpi_nowcast's `judge.md`, growth_thesis's verifier, the generators,
`panel_perturb.py`), so an edit during review would reopen the approval. Steps 3 and 6 need the
instrument-freeze (#16) and shared-judge (#17) PRs merged.

1. **Gold review** (`rl/provenance.py`). Approve, edit or reject every open item, then commit:

   ```sh
   python rl/review/review.py review --reviewer "Mayank Mahajan" --batch 30
   git add rl/sources/*/provenance.yaml rl/families/*/provenance.yaml rl/review/*.jsonl && git commit -m "Gold review"
   ```

   Commit any gold file you edited with it. Settle the entries marked `unrecorded` (who wrote them) as
   you go.

2. **Rebuild**, so every task records the approved gold, and commit the manifests:

   ```sh
   python rl/build.py && python rl/build.py panel --split train --n 3 --controls 1
   git add rl/splits/manifests && git commit -m "Rebuild after gold review"
   ```

3. **Instrument approval** (`rl/instrument.py`). For each family, read what you are approving, then approve:

   ```sh
   python rl/harness/approve.py                                   # status of every family
   python rl/harness/approve.py --family kpi_nowcast --show       # the instrument, or the diff since approval
   python rl/harness/approve.py --family kpi_nowcast --approve --by "Mayank Mahajan" --note "first approval"
   git add rl/families/*/approval.yaml && git commit -m "Approve instruments"
   ```

   Do it for research_design, kpi_nowcast, data_audit, anomaly_scoring and growth_thesis.

4. **Licences.** In `rl/sources/<source>/source.yaml`, set `licence.status` to `licensed_for_eval`,
   `licensed_for_training` or `public` (or `internal_only`) for `txn_panel` and `research_design_case`,
   with the reason in `licence.note`, and commit.

5. **Release build and export**, stamped with the commit so the archive is reproducible:

   ```sh
   SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python rl/build.py
   SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python rl/build.py panel --split train --n 3 --controls 1
   python rl/splits/check.py --release
   python rl/export.py --split bench --out dist/rl_finance-bench.tar.gz
   ```

6. **Model runs** (spend API credit; each is capped). `export ANTHROPIC_API_KEY=...` first.

   ```sh
   python rl/families/research_design/run.py --model claude-opus-5-5 --budget 25
   python rl/families/kpi_nowcast/run.py --variant calib --model claude-opus-5-5 --reps 5 --budget 100
   python rl/harness/report.py --split bench                      # leaderboard over the run records
   ```

   Then, with answers saved from those runs, the judge stability report (one call per answer per time):
   `python rl/harness/judge_stability.py --times 3 <task_dir>=<output_dir> ...`. Once the leak-check
   PR (#21) lands, the contamination probe: `python rl/harness/canary_probe.py --model claude-opus-5-5 --tries 5`.
