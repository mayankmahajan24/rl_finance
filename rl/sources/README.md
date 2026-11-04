# sources/

A **source** is one dataset plus the assignment it came with. Every task in the repo is built from
a source by a family (`../families/`), and split by the source's companies (`../splits/`).

| Source | What it is | Families |
|---|---|---|
| [`txn_panel/`](txn_panel/) | Daily card-transaction panel, 16 US airlines and department stores × 4 sensors, 2014–2018, with a description of its known data issues. KPI actuals from SEC XBRL added as grader-only data | kpi_nowcast, data_audit, anomaly_scoring, growth_thesis |
| [`research_design_case/`](research_design_case/) | A research-design case study: seeds, firm briefs, plan pairs, human gold, four models' saved runs | research_design (review; compare as research_funding) |

## Layout of a source

```
<source>/
  source.yaml        provenance, licence status, size, which families use it
  README.md          optional: anything source.yaml can't say in a line
  raw/               the data as received (or its canonical conversion, noted in source.yaml)
  assignment/        the brief that came with it
  annotations/       facts about the data that more than one family needs, written once:
                     entities (the split unit), known artifacts, per-company facts
  grader_only/       derived gold; never reaches a model under test
  build/             scripts that derive annotations/ or grader_only/
  <loader>.py        optional: how families read all of the above
```

`grader_only/` and anything marked GRADER-ONLY in `annotations/` follow the same rule as a task's
grader side: no family may put it where an agent can see it.

## Adding a source

1. Make the folder, put the data in `raw/` and the brief in `assignment/`.
2. Write `source.yaml`, including `licence.status`, one of `unknown`, `internal_only`,
   `licensed_for_eval`, `licensed_for_training` or `public`. `rl/export.py` exports a source's tasks
   for eval use only when it is `licensed_for_eval` or above, for training only when it is
   `licensed_for_training` or `public`; unknown means nothing from this source is published.
3. Write `annotations/entities.yaml`: the unit splits are assigned by (usually the company), and
   which raw identifiers belong to each.
4. Add `../splits/<source>.yaml` assigning every entity to train, bench or heldout, and set
   `company_split` (that file, or null for one eval set) and `entities` (the entities file) in
   `source.yaml`; `lib.source(id)` reads them, and `splits/check.py` picks the source up from there.
5. Build families on it (`../families/README.md`).
