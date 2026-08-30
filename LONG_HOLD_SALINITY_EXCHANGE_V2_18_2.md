# Long-hold salinity-exchange fix (v2.18.2)

## Problem

Very long capped-CO2 experiments exposed a relaxation oscillator in the reduced AMOC box system. Fast CO2 ramps first weakened the AMOC to near zero. During the subsequent 1000-year hold, the closed surface boxes continued to accumulate salinity anomalies until the northern density contrast restarted convection. The restart overshot to about 36.7 Sv and then collapsed again.

The nearly identical overshoot across several forcing rates showed that this was a structural closed-box artifact rather than a robust climate prediction.

## Fix

v2.18.2 adds conservative background exchange between:

- the Southern Ocean surface box and the external ocean; and
- the South Atlantic upper-limb box and the external ocean.

The exchange is applied to **salinity anomalies relative to the calibrated control-state contrasts**, not to absolute salinity. For a box `b` and the external reservoir `e`, the transported salt anomaly is proportional to:

```text
Q_exchange * [(S_e - S_e,control) - (S_b - S_b,control)]
```

The same salt transport is added to one reservoir and removed from the other, so total salt is conserved exactly apart from floating-point roundoff. Because both anomalies are zero in the control state, the preindustrial calibration is unchanged.

Default effective transports:

- Southern Ocean to external ocean: 5 Sv
- South Atlantic upper limb to external ocean: 2 Sv

These coefficients represent unresolved ventilation, interbasin exchange and boundary/eddy mixing outside the six-box Atlantic closure. They are configurable structural parameters and are not treated as directly observed quantities.

## Stress-test result

For a 1% per year CO2 ramp from 278.3 to 1200 ppm followed by a 1000-year hold:

- v2.18.1 generated a temporary AMOC restart near 36.7 Sv;
- v2.18.2 removed that closed-box restart artifact and preserved conservative salt exchange;
- under the structurally recalibrated v2.27 defaults, AMOC reaches approximately 6.97 Sv and then recovers gradually, with a maximum two-year increase of approximately 0.13 Sv rather than an abrupt restart pulse;
- the v2.27 regression therefore tests the defect directly through recovery-rate and overshoot bounds instead of requiring the trajectory to cross the historical 6 Sv reference;
- total salt remains conserved to approximately a few parts in 1e9;
- the calibrated constant-CO2 control state remains exactly unchanged.

## Effect on ordinary experiments

The default 1850-2100 responses change only slightly. At a 0.1-year exploratory timestep:

- SSP2-4.5 AMOC decline changed from about 7.76% to 7.88%;
- SSP5-8.5 AMOC decline changed from about 21.29% to 21.44%;
- the 40-year 0.1 Sv hosing decline changed from about 12.13% to 12.17%;
- global temperature changes were below 0.0001 C in those comparisons.

The change is nevertheless structurally important for multi-century AMOC behavior. Posterior collapse probabilities produced by older model versions should therefore remain labeled with their original model version and should not be presented as v2.18.2 probabilities without rerunning the ensemble.

## New configuration fields

```text
amoc_southern_external_exchange_sv = 5.0
amoc_south_atlantic_external_exchange_sv = 2.0
```

Setting both values to zero reproduces the old closed-box exchange structure for diagnostic comparison.
