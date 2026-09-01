# CLEM v2.29.28 R18.5 package audit

## Merge basis

- Validated/data-integrated parent: **R18.4** (`CLEM-v2.29.28-R18.4-NSIDC0611-source.zip`)
- Parent ZIP SHA-256: `9701b9d8d0fc74404ce220374daca682be55338422a1c4554215454f2af56033`
- User repository ZIP SHA-256: `a65a390300ebf171bc6cfacde652de7e1dbf506777b52a04465efb724fd4f55e`
- User repository HEAD: `0850f7768cc80eaf89784cd2ea0a554aeeeb7f5d`
- User R13 tag commit: `9937f9c361bb954a7896cc74db0922bb15cabf85`
- User README commit: `639cb720caeba4000031cf3c213f8a05ff06d0d5`

The user repository had a clean working tree. `git diff v2.29.28-r13..HEAD` showed only `README.md` and the newly added `THIRD_PARTY_DATA.md`. Therefore the R18.4 executable/model/validation tree is authoritative, while the post-R13 public documentation work is merged on top.

## Merge disposition

- `THIRD_PARTY_DATA.md` is copied **byte-for-byte** from the user repository. SHA-256: `c19519b04d67bc7186fff941d9b3d4201ce658007d33c4811b5566c282107f40`.
- The user's expanded public README structure/content is retained, while R13-era sea-ice/validation wording is synchronized to R18.2/R18.4 evidence.
- Active release metadata, `docs/VALIDATION.md`, and `docs/MODEL_LIMITATIONS.md` are synchronized to R18.5.
- No legitimate R18.4 source/provenance file is removed.
- The one generated `__pycache__/arctic_validation_stack.cpython-313.pyc` present in the R18.4 ZIP but excluded from its own source manifest is intentionally not carried forward.
- The uploaded repository's `.git` directory and embedded historical `CLEM-v2.29.28-physics-candidate-r16-source.zip` are not copied into the release source package.

See `R18_5_MERGE_DIFF.json` for the exact intended-tree added/removed/modified file list.

## Governing source identity

| File | SHA-256 | R18.4 -> R18.5 |
|---|---|---|
| `climate_model.py` | `e1553c1baccd7a90974f7879dd664a8a4b447adec5bd93407bbc5dd0e2c9bd90` | byte-identical |
| `sea_ice_observation.py` | `ae630ba91d8eaf194c892b0a83c1b5286c354355c260daff47e7053d80f63d95` | byte-identical |
| `arctic_observation_operator.py` | `28d37a9505d9387434fd5a1157923b8eeed56a253600f2783e6bb31c53e421ba` | byte-identical |
| `sea_ice_validation.py` | `9ab60121dd17e305be548fed63541b505960e3f9d96468b7a152fff53289b05a` | byte-identical |

R18.2 numerical evidence and R18.4 NSIDC-0611 data-integration evidence therefore remain applicable. **No climate integration rerun is required.**

## Verification on merged tree

- Python AST parse: **244 files, 0 failures**
- Focused R18/R18.1/R18.2/v2.29.28 regressions: **27/27 passed**
- `run_release_consistency.sh`: **PASS**
  - CLEM/model/package identity: PASS
  - zero-year/static physics worker: PASS
  - AMOC control density geometry: PASS
  - salt-loop conservation/routing: PASS
  - sea-ice freshwater routing: PASS
  - repaired CLI/default consistency: PASS
  - source invariants: PASS

No expensive climate integration was executed.

## Scientific status

- Arctic observational stack: **6/6 available**
- NSIDC-0611 v4/v4.1 1984-2024: integrated in R18.4
- Independent prospective predictive validation: **`not_available`** until the frozen 2027-2036 holdout observations exist
- Scientific/physics retuning triggered by this merge: **none**
