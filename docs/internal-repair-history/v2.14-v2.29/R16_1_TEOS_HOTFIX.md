# CLEM v2.29.28 — R16.1 TEOS setup hotfix

R16.1 is a narrow verification hotfix built from the numerically reviewed R16 source.

## Why it exists

The user-run R16 bundle completed 31/34 requested experiments. The only failures were the three TEOS-10 structural-sensitivity runs, all before year 0. They were rejected by the initial-density envelope `[0.68, 1.25]`, which was calibrated for the dimensional linear alpha/beta EOS driver. The TEOS-10 control density contrast is dimensionally larger (R16 setup ratio about `2.693`) even though the hydraulic equations normalize each EOS by its own initialized baseline density driver.

R16.1 therefore:

- retains the positive initial-density sanity check for every EOS;
- retains the `[0.68, 1.25]` absolute density-ratio gate for the linear EOS;
- does **not** apply that linear-EOS envelope to `amoc_density_eos="teos10"`;
- changes no default physics coefficient and no linear-EOS governing equation;
- includes a delta launcher that runs only the three TEOS experiments that did not run in R16.

## Local delta verification

Run:

`run_r16_1_teos_validation.bat`

The launcher requires the optional `gsw` package because every delta experiment uses TEOS-10. It advances the model only in restartable child processes of at most five model years.

Output:

`CLEM_v2.29.28_R16_1_TEOS_validation_results.zip`

The completed 31 non-TEOS R16 experiments are not repeated.
