# splits/

Which tasks are for training, which are the published bench, and which are held out.

| Split | Use | Published | How tasks get there |
|---|---|---|---|
| train | RL training | no | the split's companies; seeds from 100000, as many as needed |
| bench | the fixed eval set | yes, once the source's licence allows | the split's companies; seeds 200000+ |
| heldout | contamination-free measurement; never used for tuning | never | the split's companies; secret random seeds |

Two more folders hold tasks outside these three. `eval`: a source with no split assignment yet
(research_design_case, one eval set until whole firms can be held out). `retired`: below.
A task's folder under `rl/tasks/` is always its split.

**The unit is the company, across every family.** A task is in a split only if every company
whose data it contains is in that split. Disguise doesn't change this: rescaling, renaming and date
shifts don't hide a series' shape from a model that trained on it. Named and anonymised versions of
a case always go together.

**Retired cases leave every split.** A case used while building a harness or grader (run, read,
debugged against) no longer measures anything. If its company is in bench or held-out it can't
move to train either, so it is listed under `retired:` in `<source>.yaml` (keyed by family, then the
task's `case`) with the reason and built with `split: retired`. Nothing trains or evaluates on it.

**Generated families also split by seed.** With the generator in the repo, anyone with a seed can
rebuild a task, so held-out seeds live in `secrets/heldout_seeds.yaml` (gitignored, drawn on the
first held-out build). Back that file up outside the repo. Held-out task ids are numbered, never
seeded, and neither held-out `task.toml` files nor the manifests carry a seed. Bench and held-out
are fixed sets: `splits.seeds()` refuses a count for them; only train takes `--n`/`--controls`.

**A source opts in to a company split in its `source.yaml`**: `company_split` names its
`<source>.yaml` here and `entities` its entities file. A source without one (`company_split: null`)
builds into `eval`.

| File | What it holds |
|---|---|
| `<source>.yaml` | company → split, with `status: proposed` until approved; retired cases |
| `seeds.yaml` | seed ranges per split (held-out: pointer to the secrets file) |
| `manifests/<family>.json` | every task the family built: split, role, workflow, mode, world, status, companies, seed (not held-out), fingerprint of what the model sees, gold fingerprint, `content_sha256` of the whole task (`../FORMAT.md`, Integrity). The committed index of all tasks; the tasks themselves are gitignored (`rl/tasks/`) and rebuilt |
| `secrets/heldout_seeds.yaml` | held-out seeds. Gitignored |
| `check.py` | the rules below |

`python rl/splits/check.py` fails when:

- a company of a split source is in no split or two, or isn't in its entities file
- seed ranges overlap, or a built task's seed is outside its split's range or is a held-out seed
- a task sits outside its split's folder, uses a company of another split, or is in `eval` though
  its source has a company split
- a task is under `retired/` but its `case` isn't listed as retired, or elsewhere though it is
- a held-out task or manifest entry records its seed, or a grader-only file (`harbor.GRADER_ONLY`)
  sits under `environment/` or `prompt/`
- a task differs from its manifest entry (split, fingerprint, gold fingerprint of its family's
  `gold_file`, `content_sha256`) or its `checksums.sha256`, or has no build record
- its network or clock policy is missing or disagrees with its metadata
- its gold provenance is missing or claims an approval that no longer holds
- the leak check fails (`../leakcheck.py`), or the instruction or reference solution needs what the
  image or verifier doesn't have, or the solution reads grader-side files

`--release` adds, over every built task (`../export.py` applies the same rules to just the tasks it
exports):

- every task was built from one commit, with no uncommitted changes to tracked files
- every task models are scored on (train, bench, eval and held-out: anything but retired) has its
  family's current instrument approved (`../instrument.py`) and its gold approved, unchanged since
  review, and recorded so in the task (`../provenance.py`)

```sh
python rl/splits/check.py
python rl/splits/check.py --release
```

Held-out tasks are never exported, so the release check can't see whether they still rebuild from
the secret seeds. On the machine that holds `secrets/`, `python rl/build.py` (held-out included)
followed by `git diff --exit-code -- rl/splits/manifests` shows it: any change to a held-out entry
means the held-out set no longer reproduces (`../review/SIGNOFF.md`, step 5).
