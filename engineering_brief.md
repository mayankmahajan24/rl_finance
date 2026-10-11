# Engineering brief

For an engineer joining rl_finance who knows software well but has not worked in
finance or reinforcement learning. Read this first, then `rl/README.md` and
`rl/FORMAT.md`.

## 1. What we are building

AI labs (Anthropic, OpenAI, Google and others) improve their models partly by
**reinforcement learning (RL)**: the model attempts a task, a program scores the
attempt, and training nudges the model toward higher-scoring behaviour. Labs buy
the tasks and scoring programs from outside vendors. That bundle is called an
**environment**.

We sell environments for **buy-side finance**: the work done at investment funds
(hedge funds, asset managers) that buy and hold stocks and bonds. The other side,
**sell-side**, is banks writing research and running deals; several competitors
already cover that.

A lab is paying for three things:

1. **Realistic tasks** that current models fail at some of the time. Tasks every
   model solves teach nothing; tasks no model solves give no signal either.
2. **A reward it can trust.** If the scoring program can be fooled, training
   teaches the model to fool it. This is called **reward hacking**, and preventing
   it is the core of our pitch.
3. **Packaging it can run**: a standard format, reproducible, with documented
   quality numbers.

Mayank is the finance expert. He decides what a correct answer is. You build
everything that generates, runs, checks and packages tasks at scale.

## 2. Vocabulary

Just enough to read the code and talk to Mayank.

**RL and evals**

| Term | Meaning here |
|---|---|
| Task | One problem: inputs the model sees, plus a hidden answer key and grader |
| Eval | A fixed set of tasks used to measure models, not train them |
| Environment | Tasks + sandbox/tools + reward, packaged for training |
| Reward | A number in [0, 1] the grader returns for one attempt |
| Gold / gold labels | The expert's answer key. Written by humans, never by a model |
| Grader / judge | Code (sometimes calling a model) that turns an attempt + gold into a reward |
| Reward hacking / gaming | Scoring well without doing the task well (padding, hedging, echoing the rubric) |
| Rubric | A list of pass/fail checks for an open-ended answer ("mentions the margin guidance cut") |
| Held-out set | Tasks kept out of training to test whether learning generalizes |
| Leakage | Answer-key content reaching the model's input. Silently invalidates every result |
| Agreement | How often two experts, or the grader and an expert, give the same verdict |

**Finance**

| Term | Meaning here |
|---|---|
| PM (portfolio manager) | Decides what the fund owns. In our tasks, the person choosing between research plans |
| Analyst / quant researcher | Does the research. Fundamental analysts study companies; quants build statistical signals |
| Fund mandate | The rules a fund invests under: what it may own, how concentrated, how long it holds |
| Thesis | The reason the fund owns a stock ("margins will expand as revenue shifts to software") |
| Earnings | The quarterly results every public company reports |
| Guidance | Management's forecast for coming quarters. Changes to guidance often matter more than the results themselves |
| Consensus | The average of analysts' forecasts. A result "beats" or "misses" consensus |
| EDGAR | The SEC's free public database of company filings |
| 10-Q / 10-K | Quarterly / annual report filed with the SEC |
| 8-K | Filing for a material event. The earnings press release is attached as Exhibit 99.1 |
| XBRL | Machine-readable tags on the financial numbers in filings. This is where code-checkable answer keys come from |
| Point-in-time | Only data available as of a given date. Using later data is **look-ahead bias**, finance's version of leakage |
| Backtest | Simulating a strategy on past data to see whether it would have worked |

## 3. Where things stand

### The origin: the case study (`case_study/`)

Mayank wrote this in August 2026 as a take-home assignment for a finance research
role at Anthropic. It asked whether Claude can turn a rough investment idea into a
research plan, and whether Claude can tell a good plan from a bad one. Two findings
from it drive this company:

- Claude leans on generic research methodology and misses finance-specific
  knowledge. That gap is what our environments target.
- When judging plans, weaker models raise many objections that do not apply. One
  model raised 28.6 issues per review, about half of them invented. A grader that rewards
  catching issues without penalizing invented ones would teach this behaviour. Our
  review grader is built to prevent it.

You won't need to change `case_study/`. Treat it as read-only source data: its
scripts and raw model outputs are what `rl/` is built from and checked against.

### What `rl/` contains today

**52 tasks in 6 "worlds"**, all converted from the case study by
`rl/build_from_case_study.py`. The script is idempotent and regenerates
`rl/worlds/`, `rl/roles/` and `rl/catalog.json`.

Tasks are organized **role → workflow → task**:

```
rl/roles/<role>/<workflow>/<task_id>/
  task.yaml     metadata for the harness. Never shown to the model
  prompt/       what the model sees: system.md, user.md (or user.AB.md / user.BA.md), inputs.json
  grader/       what only the grader sees: gold.json, draft_rubric.json, reference outputs
```

Each task has a **mode**, and graders are written per mode, not per topic:

| Mode | The model's job | Grader | Tasks |
|---|---|---|---|
| review | Find the problems in a research plan | `rl/graders/review_issues.py`: share of expert-flagged blocking issues found, minus 0.1 per invented objection and 0.2 per objection the expert explicitly ruled out | 20 graded, 8 waiting on labels |
| compare | Pick which of two plans to fund | `rl/graders/pairwise_pick.py`: 1 if it matches the expert's pick. Each pair is shown in both orders to cancel position bias | 10 graded, 4 waiting on labels |
| produce | Write a research plan | None yet: needs an expert rubric | 10 |

A **world** is a simulated fund. Today each is a one-paragraph description
(`rl/worlds/<id>/world.yaml`). Making them full worlds (holdings, theses, past
memos, data) is upcoming work.

**Verified.** `rl/replay_case_study.py` re-grades four models' saved outputs with
the new graders and reproduces every headline number from the case study, with no
API calls. The build refuses to write the task tree if any gold text appears in a
model-visible prompt; that leak check has been tested by planting a leak.

**Model runner.** `rl/run.py` runs any Claude model on any task and grades the
result. It has **not yet been run against the live API**; only `--dry-run` has
been exercised.

**Anthropic's financial-services skills.** Anthropic publishes "Agent Skills" for
finance work (github.com/anthropics/financial-services): folders of instructions
the model can load while working. Claude models get them by default; `--skills off`
disables them. Details:

- `rl/skills/config.yaml` pins the source repo to one commit and defines
  **profiles**. The API allows at most 20 skills per request and the repo has 63,
  so the default profile `buy_side_core` is a curated 18. The config records why
  each excluded skill is out.
- `rl/skills/manage.py fetch | check | sync | status` checks out the pinned commit
  into `rl/vendor/` (gitignored), validates against API limits, uploads to the
  Anthropic workspace, and pins uploaded versions in `rl/skills/lock.json`.
  **`sync` has not been run yet.** It writes to the workspace, so check with
  Mayank first.
- Skills attach through the code-execution container (`container.skills` plus the
  code-execution tool). They apply to the model being tested only: the review
  scorer never gets them, so runs with and without skills are graded identically.
  Each run record stores its skills condition, and output files are named
  `__skills-<profile>` or `__skills-off` so the two never mix.

### How to run what exists

Dependencies: Python 3, `anthropic` (installed: 0.89), `pyyaml`. An
`ANTHROPIC_API_KEY` is needed only for `sync` and real runs.

```sh
python rl/build_from_case_study.py         # regenerate tasks; runs the leak check
python rl/replay_case_study.py             # must print "All fingerprints and GRADED.md numbers reproduced."
python rl/skills/manage.py fetch           # check out the pinned skills repo
python rl/skills/manage.py check
python rl/run.py --model claude-opus-5-5 --dry-run               # print a request, no API call
python rl/run.py --model claude-opus-5-5 --dry-run --skills off
```

## 4. Invariants: do not break these

1. **Never edit gold.** Gold labels, rubric items and task wording are Mayank's.
   If something looks wrong or ambiguous, flag it to him; don't fix it. A
   plausible-looking fix to gold invalidates the product.
2. **Nothing under `grader/` may reach the model.** Keep the leak check passing,
   and extend it to every new kind of task.
3. **The replay must keep passing.** It is the regression test showing our graders
   still measure what the case study measured.
4. **Fingerprint every instrument.** Prompts and schemas are hashed
   (`prompt.fingerprint` in each task). Results from different fingerprints, model
   settings or skills conditions must never be merged.
5. **Record errors; don't hide them.** The runner records API failures per task
   rather than retrying silently or switching settings, such as turning skills
   off, to make a request succeed.
6. **Point-in-time data only.** When EDGAR work starts, a task dated D must never
   expose anything filed after D, whether in files, tool results or search indexes.
7. **Grader models never get skills or tools.** Graders are measuring instruments.

## 5. What comes next

In priority order. Mayank owns every item marked *(Mayank)*. You need his input
where an item says so, but you don't need finance knowledge to build any of these.

### 5.1 Smoke test and repo hygiene (first)

- Add `pyproject.toml` or `requirements.txt` and a README setup section.
- Decide whether to upgrade the `anthropic` SDK. 0.89 predates the current Skills
  API: `manage.py` handles both shapes, but that path is untested. Check what
  changes for `case_study/scripts`.
- Turn build + leak check + replay + `manage.py check` into a test suite that runs
  in CI.
- **With Mayank's OK** (it writes to the workspace and spends API credit): run
  `manage.py sync`, then
  `run.py --model claude-opus-5-5 --tasks rd-funding-S1 rd-review-S1-A`, with
  skills on and off.
- Two things the smoke test must settle:
  - Our tasks require JSON output (`output_config.format`). We could not confirm
    from the docs that this works alongside the code-execution tool that skills
    need. If the API rejects it, design a fallback with Mayank: don't silently
    drop either.
  - The docs disagree on the code-execution tool version
    (`code_execution_20260521` with beta `code-execution-2025-08-25`, versus
    `code_execution_20250825` with no beta). It is configurable in
    `rl/skills/config.yaml`.

**Done when:** both conditions run end to end, rewards are recorded, and CI is
green.

### 5.2 Inspect exporter

Inspect (the UK AI Security Institute's eval framework) is what labs and safety
institutes commonly use. Write an exporter from our task format to an Inspect task
with custom scorers wrapping our graders. Don't change the task format to fit
Inspect; the exporter adapts.

**Done when:** a lab could run our graded tasks with Inspect and get the same
rewards as `run.py`.

### 5.3 Gaming test for the review grader

Prove the reward can't be gamed. For a sample of review tasks, generate
deliberately bad reviews of each type and confirm they score well below good
reviews:

- **Padding:** many generic objections
- **Hedging:** everything marked "could be an issue"
- **Rubric-parroting:** restating the plan's own caveats as objections
- **Confident but wrong:** specific objections that do not apply

*(Mayank)* confirms the attack list and spot-checks that the generated reviews
really are bad.

**Done when:** a report of the score gap per attack type, re-runnable as a check.

### 5.4 Multi-expert labelling and agreement

Today one expert labelled everything. Labs will ask how often experts agree with
each other and with our grader.

- Build a simple labelling form that collects labels in the existing `gold.json`
  format, one copy per expert. It must not show other experts' labels.
- Compute agreement: expert vs expert, and grader vs each expert.
- Fit the review grader's penalty weights (now 0.1 / 0.2, set by hand) against
  expert judgments.
- *(Mayank)* recruits 2 experts, briefs them, and settles disagreements.

**Done when:** agreement numbers are reported for all 30 graded tasks.

### 5.5 First real environment: earnings recap (largest item)

The case-study tasks are single prompt-and-response. Labs want **agentic** tasks:
the model uses tools over many steps. The first one: *a fund analyst writes a
recap of a company's quarterly earnings for their PM, focused on what matters for
the fund's position.*

| You build | *(Mayank)* provides |
|---|---|
| EDGAR ingest: 8-K Exhibit 99.1 press releases, 10-Qs, XBRL financial data, frozen as of each filing date | 10–15 company-quarters with a clear story (e.g. a guidance cut) |
| Answer keys computed from XBRL by code (revenue, margins, guidance figures) | Which facts to extract and how they are defined |
| Agent tools: document search over the snapshot, a filings API that refuses anything after the task date, Python | 2 full fund worlds: mandate, holdings, theses, past memos |
| An agent loop with tool use, plus result logging | The recap template and 2–3 reader contexts (e.g. long holder vs short seller) |
| Fill tasks automatically from template × company × reader context | The rubric format and review of every drafted rubric |
| Rubric drafting: a model drafts pass/fail items, each citing a quote from the source; code verifies every quote exists; drafts go to Mayank in batches | Final sign-off on each task |
| Review-mode variants: plant known errors in good recaps (a wrong number, a missed guidance change, a generic caveat) so the answer key is known by construction | The error types worth planting |

**Done when:** about 20–30 tasks in 1–2 worlds, run on several frontier models,
with difficulty measured (target: models pass 10–70% of the time) and the leak and
point-in-time checks passing.

### 5.6 Later, not MVP

Holding out whole worlds for testing (needs about 5 or more full worlds), a
training-lift demo on an open model, more workflows (backtesting needs licensed
price data first), and rubrics for the 10 produce tasks.

## 6. Working with Mayank

- **Agree formats before building.** The task format exists (`rl/FORMAT.md`). The
  world format, rubric format and recap gold format need agreeing with him early,
  so you can build without finance knowledge.
- **Batch review requests.** His time is the bottleneck. Send 10 tasks, rubric
  drafts or gaming samples at a time, not one by one.
- **Feed rejections back.** Anything he rejects becomes a labelled example used
  in generation prompts or checks, so the same mistake doesn't repeat.
- **When unsure whether something is "correct", ask.** Correctness is his call.
  Pipeline and infrastructure choices are yours.

## 7. Open risks to keep in mind

- **Data licensing.** EDGAR is free and public. Earnings call transcripts,
  consensus estimates and price history generally belong to vendors (S&P, FactSet,
  LSEG) whose licenses typically forbid model training. Don't pull from them until
  licensing is settled.
- **Model terms of service.** Using one provider's model to generate content sold
  to another lab may breach that provider's terms. Record which model produced
  each artifact; this needs a legal answer before generated content ships.
- **Case-study reuse rights** are not yet confirmed. Keep the repo private.
