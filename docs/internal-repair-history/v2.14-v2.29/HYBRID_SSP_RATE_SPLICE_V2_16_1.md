# Hybrid SSP rate-splice correction in v2.16.1

## Problem in v2.16.0

The hybrid implementation blended absolute values from the two SSP tables at the same calendar year:

```python
hybrid_value = (1 - weight) * before_value + weight * after_value
```

For a switch from SSP5-8.5 to SSP2-4.5 in 2120, this blended approximately 1398 ppm toward 610 ppm and 11.20 W/m2 toward 5.25 W/m2. With a ten-year transition, the model therefore imposed an artificial removal of roughly 780 ppm CO2 and 6 W/m2 forcing. The rapid GMST fall and AMOC rebound were consequences of that nonphysical level reset.

## v2.16.1 formulation

The hybrid is now constructed as a branch from the state reached on the first pathway:

1. Follow the first SSP exactly until the switch year.
2. Preserve the CO2 concentration and forcing at the switch.
3. Smoothly blend the annual rates of change from the first SSP to the second SSP over the transition duration.
4. Integrate those blended rates forward.

After the transition, the hybrid follows the second SSP's future changes but retains the accumulated level inherited from the first SSP.

## 2120 validation

For SSP5-8.5 to SSP2-4.5 with a 2120 switch and ten-year transition:

| Quantity | v2.16.0 at 2130 | v2.16.1 at 2130 |
|---|---:|---:|
| CO2 | about 615 ppm | about 1462 ppm |
| Total prescribed forcing | about 5.29 W/m2 | about 11.48 W/m2 |
| GMST response | rapid cooling | continued slow warming |
| AMOC response | rapid rebound | continued weakening |

This is still a concentration/forcing splice rather than an emissions-driven carbon-cycle scenario. A physically explicit transition in emissions would require emissions pathways and a carbon-cycle model. The rate splice is the appropriate continuous approximation for the pathway data bundled with this model.
