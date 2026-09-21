# v2.27.1 Arctic maintenance release

## Scope

v2.27.1 is a maintenance correction to v2.27.0. It does not implement the fractional sea-ice-cell or transient full-energy-balance redesign planned for v2.28. Freshwater coefficients and the calibrated Arctic/AMOC structural defaults are unchanged.

## Reference-cycle cache

The Arctic reference cycle is cached with an eight-entry least-recently-used bound. The key includes the grid, Arctic transition latitudes, Greenland melt-season floor, insolation, albedo, exchange, conduction, snow, pond, mixed-layer, basal-heat, numerical-step, and spin-up inputs that affect the generated cycle. Public cache-clear and cache-information methods support deterministic GUI, Monte Carlo, and test workflows.

## Absolute Arctic ocean climatology

The ocean climatology is bounded to the configured seawater freezing temperature throughout the complete active transition beginning at 55 N, rather than becoming exactly bounded only north of 66 N. A bisection solution preserves the 14 C global area-weighted baseline after this constraint is applied.

## Temperature products

Three products are explicit:

1. `bulk_surface`: land surface plus ocean mixed layer;
2. `near_surface_air`: coherent global near-surface-air proxy;
3. `arctic_interface`: Arctic ocean/sea-ice interface.

Histories, maps, CSV files, figures, summaries, and graphical interfaces label these products separately. `map_at_index` remains a compatibility alias for the bulk-surface product.

## Arctic amplification

The Arctic amplification diagnostic now compares Arctic near-surface-air warming with global near-surface-air warming over the same averaging period. It no longer divides auxiliary Arctic air warming by bulk land/ocean surface warming. Validation and held-out processing use the same definitions.

## Priors and metadata

The built-in effective exchange priors are synchronized with defaults:

- ice-air exchange: 0.01–0.20 W m-2 K-1, default 0.08;
- ice-ocean exchange: 0.05–0.60 W m-2 K-1, default 0.25.

Stale tooltip defaults, package version, dependency metadata, GUI labels, CLI labels, and release documentation are updated to v2.27.1.

## Regression coverage

The maintenance suite verifies:

- freezing bounds and global mean preservation at 2.5, 5, and 10 degree resolution;
- stable generated reference cycles at all three supported resolutions;
- cache sensitivity to Arctic start latitude and Greenland melt-season floor;
- LRU cache bounds;
- consistency between time-series diagnostics and map products;
- a like-for-like global near-surface-air amplification denominator.

## Fresh validation results

The synchronized v2.27.1 records report:

- historical GMST, 2011–2020 relative to 1850–1900: 1.1667 C;
- ocean heat-content change, 1971–2018: 356.23 ZJ;
- near-surface-air Arctic amplification, 1979–2021: 3.3185 times annually, 4.2212 times DJF, 2.1844 times JJA;
- SSP2-4.5 AMOC weakening by 2081–2100: 19.83%;
- SSP5-8.5 AMOC weakening by 2081–2100: 40.31%;
- Greenland SSP2-4.5 cumulative sea-level equivalent by 2100: 89.99 mm;
- 500-year control GMST and AMOC drift: effectively zero;
- 100-year post-hosing recovery: 89.71% of the initial loss.

The lower amplification value relative to v2.27.0 is a definition correction, not a physical recalibration: Arctic and global trends now use the same near-surface-air product.
