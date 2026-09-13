"""Diagnose salt-advection and FovS semantics in the current CLEM default."""
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import climate_model as cm


BOXES = ("north", "tropical", "south_atlantic_upper", "southern", "deep", "external")


def base_config(**changes):
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
    """Ablation: retain thermodynamics/AMOC dynamics while fixing all salinities."""

    def _salinity_tendency(
        self, state, hosing_sv, hydrological_sv=0.0, greenland_sv=0.0,
        sea_ice_storage_sv=0.0, sea_ice_export_sv=0.0,
    ):
        flux = self._surface_freshwater_fluxes_sv(
            hosing_sv, hydrological_sv, greenland_sv,
            sea_ice_storage_sv, sea_ice_export_sv,
        )
        return np.zeros(6, dtype=float), flux


def transport_diagnostics(model):
    state = model.state
    diag = model._amoc_diagnostics(state)
    salinity = model._salinity_array(state)
    base = model._advective_mixing_salinity_tendency(salinity, state.amoc_sv)
    weak = model._advective_mixing_salinity_tendency(salinity, state.amoc_sv - 1.0)
    return {
        "salinity_psu": dict(zip(BOXES, map(float, salinity))),
        "fovs_southern_boundary_sv": float(diag["fovs_sv"]),
        "freshwater_budget_components_sv": {
            "surface": float(diag["amoc_control_surface_freshwater_sv"]),
            "northern_boundary": float(
                diag["amoc_control_northern_boundary_freshwater_sv"]
            ),
            "southern_gyre": float(diag["amoc_control_southern_gyre_freshwater_sv"]),
            "predicted_fovs": float(diag["amoc_control_budget_predicted_fovs_sv"]),
        },
        "legacy_internal_section_freshwater_sv": float(
            diag["amoc_internal_section_freshwater_sv"]
        ),
        "boundary_and_internal_have_opposite_sign": bool(
            np.sign(diag["fovs_sv"])
            != np.sign(diag["amoc_internal_section_freshwater_sv"])
        ),
        "salinity_tendency_change_for_1sv_weakening_psu_per_century": dict(
            zip(BOXES, map(float, 100.0 * (weak - base)))
        ),
    }


def perturbed_transport_run(model_class):
    model = model_class(base_config())
    model.state.amoc_sv = 15.0
    frame = model.run().dataframe
    return {
        "amoc_sv": {
            "year_10": float(np.interp(10.0, frame.elapsed_years, frame.amoc_sv)),
            "year_50": float(np.interp(50.0, frame.elapsed_years, frame.amoc_sv)),
            "year_100": float(frame.amoc_sv.iloc[-1]),
        },
        "north_salinity_psu_year_100": float(frame.north_salinity_psu.iloc[-1]),
        "south_atlantic_upper_salinity_psu_year_100": float(
            frame.south_atlantic_upper_salinity_psu.iloc[-1]
        ),
    }


def legacy_seed_hosing_run(seed):
    model = cm.ProcessClimateModel(
        base_config(
            initial_fovs_sv=seed,
            amoc_enforce_initial_density_constraint=False,
            freshwater_hosing_sv=0.2,
            freshwater_start_fraction=0.0,
            freshwater_ramp_years=0.0,
        )
    )
    frame = model.run().dataframe
    return {
        "initial_boundary_fovs_sv": float(frame.fovs_sv.iloc[0]),
        "initial_internal_section_freshwater_sv": float(
            frame.amoc_internal_section_freshwater_sv.iloc[0]
        ),
        "final_boundary_fovs_sv": float(frame.fovs_sv.iloc[-1]),
        "final_internal_section_freshwater_sv": float(
            frame.amoc_internal_section_freshwater_sv.iloc[-1]
        ),
        "final_amoc_sv": float(frame.amoc_sv.iloc[-1]),
    }


def main():
    model = cm.ProcessClimateModel(base_config(duration_years=0.1))
    active = perturbed_transport_run(cm.ProcessClimateModel)
    frozen = perturbed_transport_run(FrozenSaltModel)
    result = {
        "scope": (
            "Mechanism diagnosis of the current reduced model; not an observational "
            "FovS estimate or proof of AMOC mono/multistability."
        ),
        "control_budget": transport_diagnostics(model),
        "amoc_only_perturbation": {
            "initial_amoc_sv": 15.0,
            "active_salinity": active,
            "frozen_salinity": frozen,
            "active_minus_frozen_amoc_sv": {
                year: active["amoc_sv"][year] - frozen["amoc_sv"][year]
                for year in active["amoc_sv"]
            },
        },
        "legacy_seed_sensitivity_under_0p2sv_100y_hosing": {
            f"{value:+.2f}": legacy_seed_hosing_run(value)
            for value in (-0.15, 0.0, 0.15)
        },
        "interpretation": {
            "boundary_indicator": (
                "Control FovS is solved from the independently specified surface, "
                "northern-boundary, and southern-gyre freshwater-budget terms."
            ),
            "feedback": (
                "A weaker AMOC reduces tropical-to-north salt import and transiently "
                "slows recovery, but the tested perturbation returns to the control."
            ),
            "legacy_seed": (
                "In freshwater-budget mode, legacy initial_fovs is inactive. It cannot "
                "select the absolute salinity, control contrasts, or FovS."
            ),
        },
    }
    destination = ROOT / "physics_revision_20260912" / "fovs_investigation.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
