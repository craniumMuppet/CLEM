"""Explain and test the sign of CLEM's southern-boundary FovS."""
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import climate_model as cm


BOXES = ("north", "tropical", "south_atlantic_upper", "southern", "deep", "external")


def config(**changes) -> cm.ModelConfig:
    return replace(
        cm.ModelConfig(
            resolution_deg=10.0,
            auto_initialize_from_1850=False,
            seasonal_arctic_enabled=False,
            scenario="constant",
            co2_start_ppm=cm.ModelConfig().co2_reference_ppm,
            duration_years=100.0,
            record_every_years=1.0,
            hydrological_freshwater_sv_per_k=0.0,
            greenland_surface_mass_balance_enabled=False,
            greenland_freshwater_sv_per_k=0.0,
        ),
        **changes,
    )


class FrozenSaltModel(cm.ProcessClimateModel):
    def _salinity_tendency(
        self, state, hosing_sv, hydrological_sv=0.0, greenland_sv=0.0,
        sea_ice_storage_sv=0.0, sea_ice_export_sv=0.0,
    ):
        flux = self._surface_freshwater_fluxes_sv(
            hosing_sv, hydrological_sv, greenland_sv,
            sea_ice_storage_sv, sea_ice_export_sv,
        )
        return np.zeros(6, dtype=float), flux


def control(**changes) -> dict:
    model = cm.ProcessClimateModel(config(duration_years=0.1, **changes))
    diag = model._amoc_diagnostics(model.state)
    salinity = model._salinity_array(model.state)
    base = model._advective_mixing_salinity_tendency(salinity, 17.0)
    weak = model._advective_mixing_salinity_tendency(salinity, 16.0)
    return {
        "configured_external_salinity_seed_psu": model.config.initial_external_salinity_psu,
        "solved_external_salinity_psu": float(model.state.external_salinity_psu),
        "deep_salinity_psu": float(model.state.deep_salinity_psu),
        "south_atlantic_upper_salinity_psu": float(
            model.state.south_atlantic_upper_salinity_psu
        ),
        "boundary_fovs_sv": float(diag["fovs_sv"]),
        "internal_section_freshwater_sv": float(
            diag["amoc_internal_section_freshwater_sv"]
        ),
        "control_box_virtual_freshwater_sv": dict(
            zip(BOXES, map(float, model.baseline_box_virtual_freshwater_sv))
        ),
        "control_surface_freshwater_sv": dict(
            zip(
                BOXES,
                map(
                    float,
                    model.baseline_box_virtual_freshwater_sv
                    - model.baseline_control_boundary_freshwater_sv,
                ),
            )
        ),
        "control_nonoverturning_boundary_freshwater_sv": dict(
            zip(BOXES, map(float, model.baseline_control_boundary_freshwater_sv))
        ),
        "budget_components_sv": {
            "atlantic_surface": float(diag["amoc_control_surface_freshwater_sv"]),
            "northern_boundary": float(diag["amoc_control_northern_boundary_freshwater_sv"]),
            "southern_gyre": float(diag["amoc_control_southern_gyre_freshwater_sv"]),
            "predicted_fovs": float(diag["amoc_control_budget_predicted_fovs_sv"]),
        },
        "one_sv_weakening_tendency_change_psu_per_century": dict(
            zip(BOXES, map(float, 100.0 * (weak - base)))
        ),
    }


def hosing(**changes) -> dict:
    model = cm.ProcessClimateModel(config(
        freshwater_hosing_sv=0.2,
        freshwater_start_fraction=0.0,
        freshwater_ramp_years=0.0,
        **changes,
    ))
    frame = model.run().dataframe
    return {
        "initial_fovs_sv": float(frame.fovs_sv.iloc[0]),
        "final_fovs_sv": float(frame.fovs_sv.iloc[-1]),
        "minimum_amoc_sv": float(frame.amoc_sv.min()),
        "final_amoc_sv": float(frame.amoc_sv.iloc[-1]),
        "final_north_salinity_psu": float(frame.north_salinity_psu.iloc[-1]),
        "final_basin_salt_inventory_anomaly_psu_m3": float(
            frame.amoc_basin_salt_inventory_anomaly_psu_m3.iloc[-1]
        ),
    }


def amoc_only(model_class, **changes) -> dict:
    model = model_class(config(**changes))
    model.state.amoc_sv = 15.0
    frame = model.run().dataframe
    return {
        "year_10_amoc_sv": float(np.interp(10.0, frame.elapsed_years, frame.amoc_sv)),
        "year_50_amoc_sv": float(np.interp(50.0, frame.elapsed_years, frame.amoc_sv)),
        "year_100_amoc_sv": float(frame.amoc_sv.iloc[-1]),
    }


def main() -> None:
    cases = {
        "freshwater_budget_default": {},
        "freshwater_budget_alternative_salt_inventory_seed": {
            "initial_external_salinity_psu": 34.70,
            "initial_fovs_sv": 0.10,
        },
        "legacy_prescribed_hydrography_positive": {
            "amoc_control_salinity_mode": "prescribed_hydrography",
            "initial_external_salinity_psu": 34.70,
        },
        "legacy_prescribed_hydrography_negative": {
            "amoc_control_salinity_mode": "prescribed_hydrography",
            "initial_external_salinity_psu": 35.356,
        },
    }
    result = {
        "sign_identity": "FovS = -q * (S_upper_boundary - S_deep_return) / S0",
        "steady_budget_identity": (
            "FovS = -(surface freshwater + northern-boundary freshwater + "
            "southern-gyre freshwater), when storage is zero"
        ),
        "cases": {},
    }
    for name, changes in cases.items():
        active = amoc_only(cm.ProcessClimateModel, **changes)
        frozen = amoc_only(FrozenSaltModel, **changes)
        result["cases"][name] = {
            "control": control(**changes),
            "hosing_0p2sv_100y": hosing(**changes),
            "amoc_only_active_salinity": active,
            "amoc_only_frozen_salinity": frozen,
            "active_minus_frozen_amoc_sv": {
                key: active[key] - frozen[key] for key in active
            },
        }
    result["interpretation"] = {
        "cause": (
            "The former external reservoir was fresher than the deep return, so its "
            "use as the upper boundary source forced positive FovS."
        ),
        "new_control": (
            "The default salinity contrast is solved from separately specified surface, "
            "northern-boundary, and southern-gyre freshwater terms. Changing either "
            "legacy salinity seed leaves the predicted control FovS unchanged."
        ),
        "remaining_structural_limitation": (
            "The budget components are observational control inputs and the box model "
            "does not predict absolute evaporation, precipitation, runoff, or an "
            "evolving azonal boundary transport. FovS is therefore a conditional "
            "budget prediction, not a free coupled-climate prediction."
        ),
    }
    destination = ROOT / "physics_revision_20260912" / "fovs_sign_investigation.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
