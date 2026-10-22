# splits/

Which tasks are for training, which are the published bench, and which are held out.

| Split | Use | Published | How tasks get there |
|---|---|---|---|
| train | RL training | no | the split's companies; seeds from 100000, as many as needed |
| bench | the fixed eval set | yes, once the source's licence allows | the split's companies; seeds 200000+ |
| heldout | contamination-free measurement; never used for tuning | never | the split's companies; secret random seeds |

**The unit is the company, across every family.** A task is in a split only if every company
whose data it contains is in that split. Disguise doesn't change this: rescaling, renaming and date
shifts don't hide a series' shape from a model that trained on it. Named and anonymised versions of
a case always go together.

**Generated families also split by seed.** With the generator in the repo, anyone with a seed can
rebuild a task, so held-out seeds live in `secrets/heldout_seeds.yaml` (gitignored, drawn on the
first held-out build). Back that file up outside the repo. Held-out task ids are numbered, never
seeded, and held-out `task.toml` files carry no seed.

| File | What it holds |
|---|---|
| `<source>.yaml` | company → split, with `status: proposed` until approved |
| `seeds.yaml` | seed ranges per split (held-out: pointer to the secrets file) |
| `manifests/txn_panel_<split>.json` | every built task: family, seed, companies, fingerprint, ground-truth hash. Built tasks themselves are gitignored (`rl/tasks/`) and rebuilt from these |
| `secrets/` | held-out seeds and the held-out manifest. Gitignored |
| `check.py` | fails if any company or seed is in two splits, or any built task breaks its split |

```sh
python rl/splits/check.py
```
