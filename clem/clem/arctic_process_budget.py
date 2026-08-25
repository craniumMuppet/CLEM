"""Independent evaluation of production Arctic process-ledger entries."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import numpy as np

ENERGY_INPUT_FIELDS = (
    "reference_ice_transition_wyr_m2",
    "reference_open_water_transition_wyr_m2",
    "formation_energy_change_wyr_m2",
    "melt_energy_change_wyr_m2",
    "mechanical_export_energy_change_wyr_m2",
    "phase_restoring_energy_change_wyr_m2",
    "forced_ocean_heat_convergence_energy_change_wyr_m2",
    "open_water_surface_energy_change_wyr_m2",
    "mechanical_ridging_energy_change_wyr_m2",
    "mechanical_divergence_energy_change_wyr_m2",
)
OCEAN_TRANSFER_FIELDS = (
    "phase_normalization_ocean_transfer_wyr_m2",
    "area_remap_ocean_transfer_wyr_m2",
    "cleanup_ocean_transfer_wyr_m2",
)
AREA_CHANGE_FIELDS = (
    "reference_concentration_transition",
    "formation_area_change",
    "melt_area_change",
    "ridging_area_change",
    "divergence_area_change",
    "compaction_area_change",
    "mechanical_spreading_area_change",
    "support_area_change",
    "final_concentration_support_change",
)
ACTIVITY_FIELDS = {
    "formation": "formation_energy_change_wyr_m2",
    "melt": "melt_energy_change_wyr_m2",
    "mechanical_export": "mechanical_export_energy_change_wyr_m2",
    "phase_restoring": "phase_restoring_energy_change_wyr_m2",
    "ocean_transfer": OCEAN_TRANSFER_FIELDS,
    "ridging": "ridging_area_change",
    "divergence": "divergence_area_change",
}


def _array(entry: Mapping[str, Any], name: str) -> np.ndarray:
    if name not in entry:
        raise KeyError(f"Missing Arctic process-ledger field: {name}")
    return np.asarray(entry[name], dtype=float)


def _scalar(entry: Mapping[str, Any], name: str) -> float:
    if name not in entry:
        raise KeyError(f"Missing Arctic process-ledger field: {name}")
    return float(entry[name])


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    denominator = float(np.sum(weights))
    if denominator <= 0.0:
        raise ValueError("Arctic process-ledger band weights must sum positive")
    return float(np.sum(np.asarray(values, dtype=float) * weights) / denominator)


def evaluate_arctic_process_ledger(
    entries: Iterable[Mapping[str, Any]],
    *,
    energy_tolerance_wyr_m2: float = 1.0e-10,
    area_tolerance: float = 1.0e-12,
    require_activity: bool = True,
    activity_tolerance: float = 1.0e-14,
) -> dict[str, Any]:
    """Recompute conservation against actual receiving reservoir states.

    The evaluator never treats a declared transfer field as proof that energy
    reached its destination. It derives the required surface-to-ocean transfer
    from the initial/final surface reservoirs, then compares that requirement
    with the actual Arctic mixed-layer heat-content change. It separately
    verifies the actual final lower-latitude Atlantic and non-Atlantic ocean
    reservoirs that receive phase-restoring and export compensation.
    """

    materialized = list(entries)
    if not materialized:
        return {
            "entry_count": 0,
            "maximum_energy_closure_residual_wyr_m2": float("inf"),
            "maximum_surface_to_arctic_ocean_residual_wyr_m2": float("inf"),
            "maximum_declared_to_actual_arctic_ocean_residual_wyr_m2": float("inf"),
            "maximum_arctic_ocean_state_transition_residual_wyr_m2": float("inf"),
            "maximum_lower_latitude_compensation_residual_global_wyr_m2": float("inf"),
            "maximum_area_closure_residual": float("inf"),
            "process_activity": {},
            "activity_checks": {},
            "energy_budget_closed": False,
            "area_budget_closed": False,
            "actual_receiving_reservoirs_verified": False,
            "passed": False,
        }

    maximum_surface_to_ocean_residual = 0.0
    maximum_declared_to_receiver_residual = 0.0
    maximum_ocean_transition_residual = 0.0
    maximum_lower_latitude_residual = 0.0
    maximum_lower_latitude_spatial_residual = 0.0
    maximum_area_residual = 0.0
    activity = {name: 0.0 for name in ACTIVITY_FIELDS}
    activity.update(
        {
            "arctic_mixed_layer_receiver": 0.0,
            "lower_latitude_ocean_receiver": 0.0,
        }
    )
    sector_counts: dict[str, int] = {}

    for entry in materialized:
        initial_surface = (
            _array(entry, "initial_ice_energy_wyr_m2")
            + _array(entry, "initial_open_water_heat_wyr_m2")
        )
        expected_surface = initial_surface.copy()
        for field in ENERGY_INPUT_FIELDS:
            expected_surface = expected_surface + _array(entry, field)
        final_surface = (
            _array(entry, "final_ice_energy_wyr_m2")
            + _array(entry, "final_open_water_heat_wyr_m2")
        )

        required_arctic_ocean_receipt = expected_surface - final_surface
        actual_arctic_ocean_receipt = (
            _array(entry, "post_transfer_arctic_mixed_layer_ocean_heat_wyr_m2")
            - _array(entry, "initial_arctic_mixed_layer_ocean_heat_wyr_m2")
        )
        surface_to_ocean_residual = (
            actual_arctic_ocean_receipt - required_arctic_ocean_receipt
        )
        maximum_surface_to_ocean_residual = max(
            maximum_surface_to_ocean_residual,
            float(np.max(np.abs(surface_to_ocean_residual))),
        )

        declared_arctic_ocean_transfer = np.zeros_like(actual_arctic_ocean_receipt)
        for field in OCEAN_TRANSFER_FIELDS:
            declared_arctic_ocean_transfer = (
                declared_arctic_ocean_transfer + _array(entry, field)
            )
        declared_to_receiver_residual = (
            actual_arctic_ocean_receipt - declared_arctic_ocean_transfer
        )
        maximum_declared_to_receiver_residual = max(
            maximum_declared_to_receiver_residual,
            float(np.max(np.abs(declared_to_receiver_residual))),
        )

        ocean_transition_residual = (
            _array(entry, "final_arctic_mixed_layer_ocean_heat_wyr_m2")
            - _array(entry, "post_transfer_arctic_mixed_layer_ocean_heat_wyr_m2")
            - _array(entry, "ocean_surface_flux_energy_change_wyr_m2")
        )
        maximum_ocean_transition_residual = max(
            maximum_ocean_transition_residual,
            float(np.max(np.abs(ocean_transition_residual))),
        )

        weights = _array(entry, "band_area_weights")
        sector_ocean_fraction = _array(entry, "sector_ocean_fraction")
        required_lower_latitude_receipt = -_weighted_mean(
            sector_ocean_fraction
            * (
                _array(entry, "phase_restoring_energy_change_wyr_m2")
                + _array(entry, "forced_ocean_heat_convergence_energy_change_wyr_m2")
                + _array(entry, "mechanical_export_energy_change_wyr_m2")
            ),
            weights,
        )
        actual_atlantic_receiver_change = (
            _array(entry, "final_lower_latitude_atlantic_ocean_heat_wyr_m2")
            - _array(entry, "initial_lower_latitude_atlantic_ocean_heat_wyr_m2")
        )
        actual_non_atlantic_receiver_change = (
            _array(entry, "final_lower_latitude_non_atlantic_ocean_heat_wyr_m2")
            - _array(entry, "initial_lower_latitude_non_atlantic_ocean_heat_wyr_m2")
        )
        source_shape = _array(entry, "lower_latitude_source_shape")
        receiver_atlantic_fraction = _array(
            entry, "receiver_atlantic_ocean_fraction"
        )
        receiver_non_atlantic_fraction = _array(
            entry, "receiver_non_atlantic_ocean_fraction"
        )
        receiver_area_fraction = _weighted_mean(
            source_shape
            * (receiver_atlantic_fraction + receiver_non_atlantic_fraction),
            weights,
        )
        if receiver_area_fraction <= 0.0:
            raise ValueError("Lower-latitude receiving-ocean area must be positive")
        expected_atlantic_receiver_change = (
            required_lower_latitude_receipt
            * source_shape
            * receiver_atlantic_fraction
            / receiver_area_fraction
        )
        expected_non_atlantic_receiver_change = (
            required_lower_latitude_receipt
            * source_shape
            * receiver_non_atlantic_fraction
            / receiver_area_fraction
        )
        lower_latitude_spatial_residual = max(
            float(
                np.max(
                    np.abs(
                        actual_atlantic_receiver_change
                        - expected_atlantic_receiver_change
                    )
                )
            ),
            float(
                np.max(
                    np.abs(
                        actual_non_atlantic_receiver_change
                        - expected_non_atlantic_receiver_change
                    )
                )
            ),
        )
        maximum_lower_latitude_spatial_residual = max(
            maximum_lower_latitude_spatial_residual,
            lower_latitude_spatial_residual,
        )
        actual_lower_latitude_receipt = (
            _scalar(
                entry,
                "final_lower_latitude_atlantic_ocean_heat_global_wyr_m2",
            )
            - _scalar(
                entry,
                "initial_lower_latitude_atlantic_ocean_heat_global_wyr_m2",
            )
            + _scalar(
                entry,
                "final_lower_latitude_non_atlantic_ocean_heat_global_wyr_m2",
            )
            - _scalar(
                entry,
                "initial_lower_latitude_non_atlantic_ocean_heat_global_wyr_m2",
            )
        )
        lower_latitude_residual = (
            actual_lower_latitude_receipt - required_lower_latitude_receipt
        )
        maximum_lower_latitude_residual = max(
            maximum_lower_latitude_residual,
            abs(lower_latitude_residual),
        )

        expected_area = _array(entry, "initial_concentration").copy()
        for field in AREA_CHANGE_FIELDS:
            expected_area = expected_area + _array(entry, field)
        area_residual = _array(entry, "final_concentration") - expected_area
        maximum_area_residual = max(
            maximum_area_residual,
            float(np.max(np.abs(area_residual))),
        )

        for process, fields in ACTIVITY_FIELDS.items():
            if isinstance(fields, tuple):
                value = sum(
                    float(np.max(np.abs(_array(entry, field)))) for field in fields
                )
            else:
                value = float(np.max(np.abs(_array(entry, fields))))
            activity[process] = max(activity[process], value)
        activity["arctic_mixed_layer_receiver"] = max(
            activity["arctic_mixed_layer_receiver"],
            float(np.max(np.abs(actual_arctic_ocean_receipt))),
        )
        activity["lower_latitude_ocean_receiver"] = max(
            activity["lower_latitude_ocean_receiver"],
            abs(actual_lower_latitude_receipt),
        )
        sector = str(entry.get("sector", "unknown"))
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    activity_checks = {
        name: value > activity_tolerance for name, value in activity.items()
    }
    receiver_residual = max(
        maximum_surface_to_ocean_residual,
        maximum_declared_to_receiver_residual,
        maximum_ocean_transition_residual,
        maximum_lower_latitude_residual,
        maximum_lower_latitude_spatial_residual,
    )
    receiver_closed = receiver_residual <= energy_tolerance_wyr_m2
    area_closed = maximum_area_residual <= area_tolerance
    activity_passed = all(activity_checks.values()) if require_activity else True
    return {
        "entry_count": len(materialized),
        "sector_entry_counts": sector_counts,
        "maximum_energy_closure_residual_wyr_m2": receiver_residual,
        "maximum_surface_to_arctic_ocean_residual_wyr_m2": (
            maximum_surface_to_ocean_residual
        ),
        "maximum_declared_to_actual_arctic_ocean_residual_wyr_m2": (
            maximum_declared_to_receiver_residual
        ),
        "maximum_arctic_ocean_state_transition_residual_wyr_m2": (
            maximum_ocean_transition_residual
        ),
        "maximum_lower_latitude_compensation_residual_global_wyr_m2": (
            maximum_lower_latitude_residual
        ),
        "maximum_lower_latitude_compensation_spatial_residual_wyr_m2": (
            maximum_lower_latitude_spatial_residual
        ),
        "maximum_area_closure_residual": maximum_area_residual,
        "energy_tolerance_wyr_m2": float(energy_tolerance_wyr_m2),
        "area_tolerance": float(area_tolerance),
        "process_activity": activity,
        "activity_checks": activity_checks,
        "energy_budget_closed": bool(receiver_closed),
        "area_budget_closed": bool(area_closed),
        "actual_receiving_reservoirs_verified": bool(receiver_closed),
        "required_processes_exercised": bool(activity_passed),
        "passed": bool(receiver_closed and area_closed and activity_passed),
    }
