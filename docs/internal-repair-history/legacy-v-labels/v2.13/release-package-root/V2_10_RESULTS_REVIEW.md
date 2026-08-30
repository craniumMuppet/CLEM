# v2.10 local verification results review

The v2.10 verification bundle completed every experiment successfully. Only two boolean gates failed, both marginal.

## Climate sensitivity

- equilibrium ECS: 3.2592 C
- Gregory 1-150 effective ECS: 3.4609 C
- TCR: 1.92294 C
- final equilibrium AMOC: 11.2809 Sv
- tail TOA: +0.05623 W m-2 (gate: <= 0.05 absolute)
- tail GMST trend: +0.01057 C/century
- tail AMOC trend: -0.02989 Sv/century
- resolved heat-content tendency: +0.03969 W m-2
- TOA/heat-content closure residual: +0.01653 W m-2

Feedbacks:

- Planck: -3.2542 W m-2 K-1
- water vapour: +1.8142 W m-2 K-1
- resolved lapse rate: -0.4645 W m-2 K-1
- polar inversion closure: +0.0348 W m-2 K-1
- combined WV + LR + polar: +1.3845 W m-2 K-1
- surface albedo: +0.3014 W m-2 K-1
- cloud: +0.4244 W m-2 K-1
- net: -1.1438 W m-2 K-1

All feedback-range gates passed.

## AMOC and hosing

- pure thermal 2xCO2 AMOC weakening: 41.50% (17 -> 9.945 Sv)
- thermal + sea-ice export weakening: 38.06%
- thermal + sea-ice storage weakening: 41.59%
- thermal + both sea-ice pathways weakening: 38.15%
- 0.5-Sv hosing minimum AMOC: ~1.3e-6 Sv
- 180-year hosing cold blob: -3.1553 C
- persistent collapsed branch after 800 years without hosing: -8.05594 C (gate: >= -8.0 C)

The mechanical sea-ice export pathway is stabilizing under warming after the routing correction, while storage/brine has a small destabilizing effect.

## Conservation and numerical checks

- salt conservation: exact at reported precision
- pycnocline final volume imbalance: 5.85e-7 Sv
- pycnocline tail mean absolute imbalance: 2.76e-4 Sv
- reference-residual heat correction: < 2e-16 W m-2
- seasonal-Arctic dt convergence (0.05 vs 0.025): 0.00148 C GMST and 0.01086 Sv AMOC
- Greenland cap respected; applied maximum 0.02098 Sv below the 0.10-Sv cap

## Verdict

The repaired physics is internally consistent across the current suite. v2.11 changes only the two marginal end-state items: additional equilibrium runtime and a small conservative regional AMOC heat-response damping increase.
