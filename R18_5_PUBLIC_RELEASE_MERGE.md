# CLEM v2.29.28 R18.5 public-release merge

## Purpose

R18.5 merges the user's public-release documentation work onto the completed R18.4 source without reverting any R15-R18 model, validation, or observational-data changes.

The uploaded Git repository showed a clean working tree. Relative to tag `v2.29.28-r13`, the only intentional post-R13 commits changed:

- `README.md` (`639cb72`, public README expansion)
- `THIRD_PARTY_DATA.md` (`0850f77`, third-party data attribution)

All executable/model/validation files therefore come from R18.4. The public README content is preserved and synchronized with the later R18.2/R18.4 scientific status rather than copied verbatim where the old R13-era statements had become stale.

## Physics identity

No governing model or observation-operator file changed in this merge. Numerical R18.2 evidence and R18.4 data-integration evidence remain applicable. No climate integration rerun is required.

## Public-release files

- `README.md` SHA-256: `4c6d40e566672200b6c4ce1984e53691915be477f6f3eba44976ea7d74627760`
- `THIRD_PARTY_DATA.md` SHA-256: `c19519b04d67bc7186fff941d9b3d4201ce658007d33c4811b5566c282107f40`
- `LICENSE`: retained from R18.4

The `.git` directory from the uploaded repository and its embedded historical candidate ZIP are not copied into the release source package. R18.4's later provenance files remain intact.
