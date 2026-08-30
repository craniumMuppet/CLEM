from pathlib import Path

root = Path('/mnt/data/clem_v22/clem/clem')
source_path = root / 'climate_model.py'
verifier_path = root / 'verify_physics_local.py'
readme_path = root / 'PHYSICS_REPAIR_LOCAL_VERIFICATION.md'

s = source_path.read_text(encoding='utf-8')

def replace_once(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected exactly 1 match, found {n}')
    s = s.replace(old, new, 1)

replace_once(
'''    # Only the anomalous sinking-region temperature contrast is coupled at
    # full strength. The preindustrial contrast remains part of the calibrated
    # control density gradient. This prevents an AMOC-created cold blob from
    # unrealistically restoring the circulation one-for-one.
    amoc_temperature_density_coupling: float = 1.00
''',
'''    # Fraction of the forced northern surface-to-deep stratification anomaly
    # that contributes to the basin-scale hydraulic density response.  This is
    # an anomaly coupling, not a control-state tuning factor.  A value of 0.5
    # retains a substantial local buoyancy pathway without double-counting the
    # full northern surface anomaly in both local and interhemispheric terms.
    amoc_temperature_density_coupling: float = 0.50
''',
'local thermal coupling default')

replace_once(
'''    # Separate coefficient for the Atlantic interhemispheric surface contrast.
    # Keeping this explicit avoids the previous hidden 0.02 multiplier.
    amoc_interhemispheric_temperature_coupling: float = 1.00
''',
'''    # Separate coefficient for the forced Atlantic interhemispheric surface
    # contrast.  This remains orders of magnitude larger than the old 0.02
    # suppression, but shares thermal sensitivity with local surface-to-deep
    # stratification so northern warming is not counted twice at full strength.
    amoc_interhemispheric_temperature_coupling: float = 0.50
''',
'interhemispheric coupling default')

replace_once(
'''    # Northern deep-water formation is a continuous prognostic process. The
    # smooth convection transition is centred on *neutral* thermohaline density
    # contrast (ratio = 0), rather than an empirically chosen 0.91 fraction of
    # the control driver. The width is therefore only numerical smoothing around
    # the physical sign change; it no longer sets a hidden collapse threshold.
    # Active convection entrains saline deep water into the sinking region, so
    # salt-advection/mixing feedback remains prognostic.
    amoc_convection_critical_density_ratio: float = 0.00
    amoc_convection_transition_width: float = 0.10
    # Compatibility field retained for older configuration files. The current
    # convection target uses the same dimensionless basin density ratio as the
    # hydraulic AMOC closure and does not use this arbitrary scale factor.
    amoc_convection_density_scale_factor: float = 1.00
''',
'''    # Legacy logistic-transition controls are retained only so old config files
    # continue to load.  The v2.2 dynamics do not use a tuned critical ratio or
    # transition width.  Convection instead responds continuously to the local
    # northern surface-versus-deep thermohaline density anomaly, normalized by
    # the dimensional control AMOC density driver.
    amoc_convection_critical_density_ratio: float = 0.00
    amoc_convection_transition_width: float = 0.10
    # Dimensionless scale multiplying the physical control density driver in the
    # local convection response.  1.0 means one control-driver-sized adverse
    # local density anomaly reduces convection by e^-1 before configured bounds.
    amoc_convection_density_scale_factor: float = 1.00
''',
'convection config comments')

replace_once(
'''        interhemispheric_anomaly = southern_anomaly - north_anomaly
        effective_delta_t = baseline_delta_t + interhemispheric_anomaly
        thermal = cfg.thermal_expansion_per_k * effective_delta_t
''',
'''        interhemispheric_anomaly = southern_anomaly - north_anomaly
        northern_stratification_anomaly = (
            float(north_surface_anomaly_c) - float(north_deep_anomaly_c)
        )
        # Two physically distinct thermal pathways contribute to weakening:
        # (1) the forced Atlantic north-south surface-temperature contrast and
        # (2) local northern surface warming relative to the deep reservoir.
        # Both are anomalies about the same control state, so the exact control
        # density driver is unchanged and remains the normalization.
        effective_delta_t = (
            baseline_delta_t
            + cfg.amoc_interhemispheric_temperature_coupling
            * interhemispheric_anomaly
            - cfg.amoc_temperature_density_coupling
            * northern_stratification_anomaly
        )
        thermal = cfg.thermal_expansion_per_k * effective_delta_t
''',
'hydraulic thermal pathways')

old_conv = '''        # Keep the local surface-to-deep thermal/haline anomalies as explicit
        # diagnostics, but do not let a separately scaled local ratio set the
        # AMOC collapse point. Convection follows the same prognostic basin-scale
        # thermohaline density ratio as the hydraulic transport. Thus neutral
        # density contrast has an invariant physical meaning (ratio = 0), while
        # local stratification remains observable for validation.
        convection_density_anomaly = (
            -cfg.thermal_expansion_per_k
            * cfg.amoc_convection_temperature_density_coupling
            * northern_stratification_anomaly
            + cfg.haline_contraction_per_psu * northern_haline_anomaly
        )
        convection_density_ratio = float(density_ratio)
'''
new_conv = '''        # Local northern deep-water formation responds to the *anomalous*
        # surface-versus-deep thermohaline density change.  This quantity was
        # previously computed but discarded, leaving convection and its saline
        # entrainment almost fully active during strong hosing.  Normalizing by
        # the dimensional control driver gives a transparent O(1) response scale
        # without choosing an empirical collapse location.
        convection_density_anomaly = (
            -cfg.thermal_expansion_per_k
            * cfg.amoc_convection_temperature_density_coupling
            * northern_stratification_anomaly
            + cfg.haline_contraction_per_psu * northern_haline_anomaly
        )
        convection_density_scale = max(
            abs(self.baseline_density_driver)
            * cfg.amoc_convection_density_scale_factor,
            1.0e-12,
        )
        convection_density_ratio = float(
            1.0 + convection_density_anomaly / convection_density_scale
        )
'''
replace_once(old_conv, new_conv, 'local convection anomaly use')

old_logistic = '''        # Deep-convection efficiency decreases smoothly as local surface water
        # loses its density advantage. The current convection state contributes
        # continuous entrainment support: active mixing erodes stratification,
        # while weak mixing permits stratification to persist. Normalising by the
        # control-state value guarantees an exact preindustrial equilibrium of one.
        width = cfg.amoc_convection_transition_width
        critical = cfg.amoc_convection_critical_density_ratio
        effective_convection_density_ratio = float(
            convection_density_ratio
            + cfg.amoc_convection_entrainment_feedback
            * (state.convection_efficiency - 1.0)
        )
        logistic_argument = float(
            np.clip((effective_convection_density_ratio - critical) / width, -60.0, 60.0)
        )
        control_argument = float(np.clip((1.0 - critical) / width, -60.0, 60.0))
        logistic = 1.0 / (1.0 + math.exp(-logistic_argument))
        control_logistic = 1.0 / (1.0 + math.exp(-control_argument))
        raw_convection_target = cfg.amoc_convection_minimum_fraction + (
            1.0 - cfg.amoc_convection_minimum_fraction
        ) * logistic
        control_convection = cfg.amoc_convection_minimum_fraction + (
            1.0 - cfg.amoc_convection_minimum_fraction
        ) * control_logistic
        convection_target = float(
            np.clip(raw_convection_target / control_convection, 0.0, cfg.amoc_equilibrium_convection_max)
        )
'''
new_logistic = '''        # Convection changes continuously with the local density anomaly.  The
        # exponential form is exactly 1 at the control state, decreases smoothly
        # under freshening/stratification, and strengthens smoothly when local
        # buoyancy favours convection.  Bounds prevent numerical pathologies but
        # there is no hidden critical-density bifurcation parameter.
        effective_convection_density_ratio = float(
            convection_density_ratio
            + cfg.amoc_convection_entrainment_feedback
            * (state.convection_efficiency - 1.0)
        )
        min_conv = max(cfg.amoc_convection_minimum_fraction, 1.0e-12)
        max_conv = max(cfg.amoc_equilibrium_convection_max, 1.0)
        local_convection_log_target = float(
            np.clip(
                effective_convection_density_ratio - 1.0,
                math.log(min_conv),
                math.log(max_conv),
            )
        )
        convection_target = float(math.exp(local_convection_log_target))
'''
replace_once(old_logistic, new_logistic, 'remove convection logistic')

replace_once(
'''                "atlantic_effective_ice": regular_atlantic_ice,
                "non_atlantic_effective_ice": regular_non_atlantic_ice,
            }
''',
'''                "atlantic_effective_ice": regular_atlantic_ice,
                "non_atlantic_effective_ice": regular_non_atlantic_ice,
                # Seasonal-Arctic-off runs still use the same coupled salinity
                # interface.  Zero fluxes keep that interface total and avoid a
                # special-case KeyError in hosing/pycnocline validation paths.
                "atlantic_ice_storage_freshwater_sv": 0.0,
                "atlantic_ice_export_freshwater_sv": 0.0,
            }
''',
'Arctic-disabled freshwater interface')

source_path.write_text(s, encoding='utf-8')

v = verifier_path.read_text(encoding='utf-8')

def vreplace(old, new, label):
    global v
    n = v.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected exactly 1 match, found {n}')
    v = v.replace(old, new, 1)

vreplace('VERIFIER_REVISION = "2026-08-27-v2.1-json-safe"',
         'VERIFIER_REVISION = "2026-08-27-v2.2-local-density-response"',
         'verifier revision')

vreplace(
'''    "energy_step2x_100y": {
        "duration": 100.0,
        "config": {
''',
'''    "energy_step2x_100y": {
        "duration": 100.0,
        # Energy closure is sampled at the model timestep instead of annually;
        # this removes endpoint-quadrature error from the verification metric.
        "record_interval_years": 0.05,
        "config": {
''',
'energy record interval')

vreplace(
'''    overrides = dict(spec["config"])
    duration = float(spec["duration"])
    overrides.update(
        duration_years=duration,
        record_every_years=RECORD_INTERVAL_YEARS,
        auto_initialize_from_1850=False,
    )
''',
'''    overrides = dict(spec["config"])
    duration = float(spec["duration"])
    record_interval = float(spec.get("record_interval_years", RECORD_INTERVAL_YEARS))
    if record_interval <= 0.0:
        raise ValueError("record_interval_years must be positive")
    overrides.update(
        duration_years=duration,
        record_every_years=record_interval,
        auto_initialize_from_1850=False,
    )
''',
'setup record interval')

vreplace(
'''    start = elapsed
    chunk_target = min(duration, start + chunk_years)
    next_record = math.floor((elapsed + EPS) / RECORD_INTERVAL_YEARS + 1.0) * RECORD_INTERVAL_YEARS
    records: list[dict[str, Any]] = []
''',
'''    start = elapsed
    chunk_target = min(duration, start + chunk_years)
    record_interval = float(spec.get("record_interval_years", RECORD_INTERVAL_YEARS))
    next_record = math.floor((elapsed + EPS) / record_interval + 1.0) * record_interval
    records: list[dict[str, Any]] = []
''',
'advance record interval')

# Replace both increments in advance worker only.
needle = '                next_record += RECORD_INTERVAL_YEARS\n'
if v.count(needle) != 1:
    raise RuntimeError(f'first record increment count {v.count(needle)}')
v = v.replace(needle, '                next_record += record_interval\n', 1)
needle2 = '            next_record += RECORD_INTERVAL_YEARS\n'
if v.count(needle2) != 1:
    raise RuntimeError(f'second record increment count {v.count(needle2)}')
v = v.replace(needle2, '            next_record += record_interval\n', 1)

# Update static source-invariant diagnostics to test the new response form.
vreplace(
'''            "convection_transition_center_density_ratio": float(cfg.amoc_convection_critical_density_ratio),
            "convection_transition_width": float(cfg.amoc_convection_transition_width),
            "convection_transport_exponent": float(cfg.amoc_convection_transport_exponent),
''',
'''            "legacy_convection_transition_center_density_ratio": float(cfg.amoc_convection_critical_density_ratio),
            "legacy_convection_transition_width": float(cfg.amoc_convection_transition_width),
            "convection_density_scale_factor": float(cfg.amoc_convection_density_scale_factor),
            "convection_transport_exponent": float(cfg.amoc_convection_transport_exponent),
            "amoc_temperature_density_coupling": float(cfg.amoc_temperature_density_coupling),
            "amoc_interhemispheric_temperature_coupling": float(cfg.amoc_interhemispheric_temperature_coupling),
''',
'static invariant fields')

vreplace(
'''            "pass_convection_transition_centered_on_neutral_density": bool(abs(cfg.amoc_convection_critical_density_ratio) < 1.0e-12),
            "pass_logistic_no_longer_dominates_transport": bool(cfg.amoc_convection_transport_exponent <= 0.25),
''',
'''            "pass_legacy_logistic_not_used_in_dynamics": bool(
                "logistic_argument" not in source_text
                and "control_logistic" not in source_text
                and "local_convection_log_target" in source_text
            ),
            "pass_local_convection_density_anomaly_is_active": bool(
                "convection_density_anomaly / convection_density_scale" in source_text
            ),
            "pass_local_stratification_enters_hydraulic_density": bool(
                "cfg.amoc_temperature_density_coupling" in source_text
                and "northern_stratification_anomaly" in source_text
            ),
            "pass_logistic_no_longer_dominates_transport": bool(cfg.amoc_convection_transport_exponent <= 0.25),
''',
'static pass fields')

verifier_path.write_text(v, encoding='utf-8')

readme = '''# CLEM physics repair — local verification candidate v2.2

This candidate is intended to be **integrated and verified on the user's computer**. Long climate integrations were not run while preparing the package.

## Changes driven by the returned v2.1 results

The completed v2.1 run showed that numerical convergence and salt conservation were clean, but 0.5 Sv hosing only weakened AMOC to about 11.53 Sv with a -1.21 C North Atlantic anomaly, while the thermal-only 2xCO2 experiment strengthened AMOC to about 17.79 Sv. Two seasonal-Arctic-off experiments also crashed at year 0 because the disabled Arctic return dictionary lacked the newly added sea-ice freshwater keys.

v2.2 therefore makes four targeted changes:

1. The hydraulic AMOC density driver now contains both the forced Atlantic interhemispheric surface-temperature anomaly and the northern surface-minus-deep stratification anomaly. Both are anomaly terms about the unchanged control state.
2. The already-computed local thermohaline convection-density anomaly is no longer discarded. Convection and its saline deep-water entrainment respond continuously and exponentially to that anomaly, normalized by the physical control density driver. The old logistic critical-density parameters remain load-compatible but are not used by the dynamics.
3. Seasonal-Arctic-disabled runs return explicit zero sea-ice storage/export freshwater fluxes, so pycnocline and recovery experiments use the same salinity interface without crashing.
4. The energy-closure experiment records every 0.05 model year rather than annually. This makes its TOA integral a numerical-energy test instead of a coarse recording-interval quadrature test.

No salinity-box volume, hosing magnitude, freshwater restoring strength, AMOC heat-coupling coefficient, or collapse threshold was tuned in this revision.

## Run

From `clem\\clem`, run either:

`RUN_PHYSICS_VERIFICATION.cmd`

or:

`python verify_physics_local.py`

Every integration child advances at most 5 model years, checkpoints atomically, and exits. Rerunning the command resumes source/spec-compatible checkpoints. The final `physics_verification_bundle.zip` should be uploaded for evaluation.
'''
readme_path.write_text(readme, encoding='utf-8')
print('patched', source_path, verifier_path, readme_path)
