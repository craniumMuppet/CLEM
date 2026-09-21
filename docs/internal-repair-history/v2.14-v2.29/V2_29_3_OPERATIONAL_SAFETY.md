# v2.29.3 Operational Safety and Thermodynamic Maintenance

v2.29.3 completes the unfinished operational checkpoint on top of the validated v2.29.2 core. It preserves the calibrated freshwater defaults and main climate response while fixing destructive-output risks, worker supervision, GUI shutdown races, unresolved Arctic-lead temperatures, and a repeated Greenland geometry calculation.

## Public defaults

The CLI, desktop GUI, Streamlit interface, metadata, Monte Carlo entrypoint, and target sweep now inherit the `ModelConfig` default CO2 forcing formula. The default is **Meinshausen et al. (2020)**. The older logarithmic expression remains selectable for compatibility and sensitivity experiments.

## Output overwrite safety

Existing output folders are preserved unless the user explicitly approves replacement or passes `--overwrite-output`. Resume runs reuse existing checkpoint directories without deleting them. The output preparer refuses filesystem roots, the home directory, the current working directory, the source directory, and any ancestor whose recursive deletion would remove one of those protected locations.

## Worker supervision and recovery

Monte Carlo and target-sweep members run in individually spawned processes with:

- per-member timeouts;
- periodic heartbeat reporting;
- atomic compatible-fingerprint checkpoints;
- deterministic resume of completed and failed members;
- stale temporary-worker cleanup;
- termination and escalation for unresponsive workers.

The GUI launches simulations in a dedicated process group/session and terminates the complete process tree. A close or stop request made while `Popen` is still launching is retained and applied immediately when the process group becomes available, preventing orphan workers.

## Unresolved Arctic leads

The earlier 1% effective-open threshold was insufficient under a strong freshwater-routing regression: a lead only slightly above 1% could retain area-mean sensible heat that diagnosed as **47.43°C** locally, although cells with at least 5% open water remained below **17.23°C**.

Open fractions below **5%** are now treated as unresolved sub-grid leads. They remain pinned to the freezing interface and transfer sensible heat conservatively to the coupled Arctic ocean. This removes the area singularity without clipping or discarding energy. The original failing freshwater-routing regression passes with the normal release temperature gates enabled.

The exact zero-forcing seasonal reference manifold is advanced analytically only when every forcing, hosing, thermal, salinity, AMOC, Greenland, cloud, snow, and Arctic anomaly check is satisfied. A deliberate 10⁻⁴°C land perturbation bypasses the guard and evolves normally. Interpolated interface temperature is rebuilt from the interpolated ice fraction and open-water temperature, avoiding a nonlinear interpolation mismatch while retaining strict equal-and-opposite heat exchange.

## Runtime maintenance

The Greenland geographic mask and Gaussian melt-driver weights are immutable for a selected grid. v2.29.3 precomputes them once at initialization instead of allocating and evaluating the same 2-D arrays every timestep. This is equation-neutral and restores practical full-period validation performance.

## Validation snapshot

All **18/18 required release gates passed**.

- Historical GMST, 2011–2020: **1.108°C**
- Ocean heat-content gain, 1971–2018: **383.72 ZJ**
- Annual Arctic amplification, 1979–2021: **3.408×**
- DJF / JJA Arctic amplification: **4.540× / 1.636×**
- SSP2-4.5 AMOC weakening by 2100: **20.85%**
- SSP5-8.5 AMOC weakening by 2100: **39.60%**
- SSP2-4.5 / SSP5-8.5 peak resolved open-water temperature: **12.77°C / 17.43°C**
- Abrupt-2×CO2 resolved-energy residual: **−0.0397%**
- 500-year GMST / AMOC drift: **0.0°C / 0.0 Sv**
- 500-year salt residual and cumulative projection correction: **0.0 / 0.0**
- Maximum forced-run pre-projection salt residual: **3.47×10⁻¹⁰ ppm**
- Hosing recovery after 100 years: **81.49%**
- Public-range reference stress: **157 years**, closure **8.62×10⁻⁹ W·yr/m²**

These remain tuning-informed development-regression checks, not independent validation.
