# splits/

Which tasks are for training, which are the published bench, and which are held out.

| Split | Use | Published | How tasks get there |
|---|---|---|---|
| train | RL training | no | the split's companies; seeds from 100000, as many as needed |
| bench | the fixed eval set | yes, once the source's licence allows | the split's companies; seeds 200000+ |
| heldout | contamination-free measurement; never used for tuning | never | the split's companies; secret random seeds |

Two more folders hold tasks outside these three. `eval`: a source with no split assignment yet
(research_design_case, one eval set until whole worlds can be held out). `retired`: below.
A task's folder under `rl/tasks/` is always its split.

**The unit is the company, across every family.** A task is in a split only if every company
whose data it contains is in that split. Disguise doesn't change this: rescaling, renaming and date
shifts don't hide a series' shape from a model that trained on it. Named and anonymised versions of
a case always go together.

**Retired cases leave every split.** A case used while building a harness or grader (run, read,
debugged against) no longer measures anything. If its company is in bench or held-out it can't
move to train either, so it is listed under `retired:` in `<source>.yaml` with the reason and built
with `split: retired`. Nothing trains or evaluates on it.

**Generated families also split by seed.** With the generator in the repo, anyone with a seed can
rebuild a task, so held-out seeds live in `secrets/heldout_seeds.yaml` (gitignored, drawn on the
first held-out build). Back that file up outside the repo. Held-out task ids are numbered, never
seeded, and neither held-out `task.toml` files nor the manifests carry a seed.

| File | What it holds |
|---|---|
| `<source>.yaml` | company → split, with `status: proposed` until approved |
| `seeds.yaml` | seed ranges per split (held-out: pointer to the secrets file) |
| `manifests/<family>.json` | every task the family built: split, role, workflow, mode, world, status, companies, seed (not held-out), fingerprint of what the model sees, gold fingerprint. The committed index of all tasks; the tasks themselves are gitignored (`rl/tasks/`) and rebuilt |
| `secrets/heldout_seeds.yaml` | held-out seeds. Gitignored |
| `check.py` | fails if any company or seed is in two splits, any built task breaks its split, or a built task differs from its manifest |

```sh
python rl/splits/check.py
```
