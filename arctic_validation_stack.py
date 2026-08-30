"""Six-source Arctic observational validation stack.

Each product has a distinct scientific role and, where a spatial comparison is
required, an explicit observation-operator file.  A processed scalar time
series alone is not sufficient evidence because EGCM must be evaluated on the
same spatial support as the observation product.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
VALIDATION_ROOT = ROOT / "data" / "validation"
PRIMARY_AREA_DIR = VALIDATION_ROOT / "sea_ice_fixed_mask"
PHYSICAL_DIR = VALIDATION_ROOT / "sea_ice_physical"
OSI_SAF_DIR = VALIDATION_ROOT / "sea_ice_crosscheck" / "osi_saf_osi450a1"
ICE_AGE_DIR = VALIDATION_ROOT / "sea_ice_structural" / "nsidc_0611_v4"

PRIMARY_AREA_OPERATOR = PRIMARY_AREA_DIR / "MODEL_OBSERVATION_OPERATOR.npz"
PIOMAS_OPERATOR = PHYSICAL_DIR / "piomas_common_domain_operator.npz"
CRYOSAT2_OPERATOR = PHYSICAL_DIR / "cryosat2_rdeft4_operator.npz"
ICESAT2_OPERATOR = PHYSICAL_DIR / "icesat2_is2sitmogr4_operator.npz"
OSI_SAF_OPERATOR = OSI_SAF_DIR / "MODEL_OBSERVATION_OPERATOR.npz"


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    product: str
    version: str
    role: str
    provider: str
    required_paths: tuple[str, ...]
    calibrated_to: bool
    independent_check: bool


SOURCES: dict[str, SourceSpec] = {
    "nsidc_g02202_v6": SourceSpec(
        source_id="nsidc_g02202_v6",
        product="NOAA/NSIDC Climate Data Record of Passive Microwave Sea Ice Concentration",
        version="6",
        role="primary_fixed_mask_area_calibration",
        provider="NOAA/NSIDC",
        required_paths=(
            "data/validation/sea_ice_fixed_mask/N_03_fixed_mask.csv",
            "data/validation/sea_ice_fixed_mask/N_09_fixed_mask.csv",
            "data/validation/sea_ice_fixed_mask/MODEL_OBSERVATION_OPERATOR.npz",
            "data/validation/sea_ice_fixed_mask/METADATA.json",
        ),
        calibrated_to=True,
        independent_check=False,
    ),
    "piomas_v2_1": SourceSpec(
        source_id="piomas_v2_1",
        product="PIOMAS Arctic Sea Ice Volume Reanalysis",
        version="2.1",
        role="common_domain_long_record_volume_constraint",
        provider="University of Washington Polar Science Center",
        required_paths=(
            "data/validation/sea_ice_physical/piomas_volume_monthly.csv",
            "data/validation/sea_ice_physical/piomas_common_domain_operator.npz",
            "data/validation/sea_ice_physical/piomas_v2_1_metadata.json",
        ),
        calibrated_to=True,
        independent_check=False,
    ),
    "cryosat2_rdeft4_v1": SourceSpec(
        source_id="cryosat2_rdeft4_v1",
        product="CryoSat-2 Level-4 Sea Ice Elevation, Freeboard, and Thickness",
        version="1",
        role="development_informed_satellite_thickness_constraint",
        provider="NASA NSIDC DAAC",
        required_paths=(
            "data/validation/sea_ice_physical/cryosat2_rdeft4_monthly.csv",
            "data/validation/sea_ice_physical/cryosat2_rdeft4_operator.npz",
            "data/validation/sea_ice_physical/cryosat2_rdeft4_v1_metadata.json",
        ),
        calibrated_to=False,
        independent_check=False,
    ),
    "icesat2_is2sitmogr4_v4": SourceSpec(
        source_id="icesat2_is2sitmogr4_v4",
        product="ICESat-2 L4 Monthly Gridded Sea Ice Thickness",
        version="4",
        role="development_informed_satellite_thickness_constraint",
        provider="NASA NSIDC DAAC",
        required_paths=(
            "data/validation/sea_ice_physical/icesat2_is2sitmogr4_monthly.csv",
            "data/validation/sea_ice_physical/icesat2_is2sitmogr4_operator.npz",
            "data/validation/sea_ice_physical/icesat2_is2sitmogr4_v4_metadata.json",
        ),
        calibrated_to=False,
        independent_check=False,
    ),
    "osi_saf_osi450a1_v3_1": SourceSpec(
        source_id="osi_saf_osi450a1_v3_1",
        product="OSI SAF Global Sea Ice Concentration Climate Data Record OSI-450-a1",
        version="3.1",
        role="development_fixed_mask_area_cross_dataset_diagnostic",
        provider="EUMETSAT OSI SAF",
        required_paths=(
            "data/validation/sea_ice_crosscheck/osi_saf_osi450a1/N_03_fixed_mask_crosscheck.csv",
            "data/validation/sea_ice_crosscheck/osi_saf_osi450a1/N_09_fixed_mask_crosscheck.csv",
            "data/validation/sea_ice_crosscheck/osi_saf_osi450a1/MODEL_OBSERVATION_OPERATOR.npz",
            "data/validation/sea_ice_crosscheck/osi_saf_osi450a1/METADATA.json",
        ),
        calibrated_to=False,
        independent_check=False,
    ),
    "nsidc_0611_v4": SourceSpec(
        source_id="nsidc_0611_v4",
        product="EASE-Grid Sea Ice Age",
        version="4",
        role="multiyear_ice_structural_diagnostic",
        provider="NASA NSIDC DAAC",
        required_paths=(
            "data/validation/sea_ice_structural/nsidc_0611_v4/multiyear_ice_annual.csv",
            "data/validation/sea_ice_structural/nsidc_0611_v4/METADATA.json",
        ),
        calibrated_to=False,
        independent_check=True,
    ),
}

PHYSICAL_METRIC_THRESHOLDS: dict[str, float] = {
    "piomas_volume_normalized_rmse": 0.20,
    "cryosat2_mean_thickness_normalized_rmse": 0.15,
    "icesat2_mean_thickness_normalized_rmse": 0.20,
}

OPERATOR_PATHS: dict[str, Path] = {
    "nsidc_g02202_v6": PRIMARY_AREA_OPERATOR,
    "piomas_v2_1": PIOMAS_OPERATOR,
    "cryosat2_rdeft4_v1": CRYOSAT2_OPERATOR,
    "icesat2_is2sitmogr4_v4": ICESAT2_OPERATOR,
    "osi_saf_osi450a1_v3_1": OSI_SAF_OPERATOR,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def observation_operator_path(source_id: str) -> Path | None:
    return OPERATOR_PATHS.get(source_id)


def _metadata_path_for(spec: SourceSpec) -> Path | None:
    for relative in spec.required_paths:
        if relative.lower().endswith(".json"):
            return ROOT / relative
    return None


def _source_sanity_errors(source_id: str) -> list[str]:
    """Return decisive processed-evidence sanity failures for one source.

    These checks deliberately target catastrophic unit/background errors.  They
    are not skill thresholds and cannot make a model pass validation; they only
    prevent malformed observational evidence from being marked available.
    """
    errors: list[str] = []
    try:
        if source_id == "piomas_v2_1":
            path = PHYSICAL_DIR / "piomas_volume_monthly.csv"
            if path.exists():
                frame = pd.read_csv(path, skipinitialspace=True)
                if "volume_million_km3" not in frame.columns:
                    errors.append("PIOMAS volume file lacks volume_million_km3")
                else:
                    values = pd.to_numeric(frame["volume_million_km3"], errors="coerce").to_numpy(dtype=float)
                    if values.size == 0 or not np.all(np.isfinite(values)) or np.any(values < 0.0):
                        errors.append("PIOMAS common-domain volumes contain missing/non-finite/negative values")
                    elif float(np.max(values)) > 0.1:
                        errors.append(
                            f"PIOMAS common-domain volume maximum {float(np.max(values)):.6f} million km3 exceeds 0.1; probable unit/background error"
                        )
        elif source_id == "osi_saf_osi450a1_v3_1":
            metadata_path = OSI_SAF_DIR / "METADATA.json"
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if metadata.get("temporal_sampling") != "official_monthly_mean_files_only":
                        errors.append("OSI SAF evidence is not certified as official monthly-mean files only")
                except (json.JSONDecodeError, OSError) as exc:
                    errors.append(f"OSI SAF metadata could not be checked: {exc}")
            if OSI_SAF_OPERATOR.exists():
                with np.load(OSI_SAF_OPERATOR) as operator:
                    areas = np.asarray(operator["cell_area_km2"], dtype=float)
                finite = areas[np.isfinite(areas) & (areas > 0.0)]
                if finite.size == 0:
                    errors.append("OSI SAF observation operator has no positive finite cell areas")
                else:
                    median_area = float(np.median(finite))
                    total_area = float(np.sum(finite))
                    if median_area < 1.0 or total_area < 1.0e6:
                        errors.append(
                            f"OSI SAF observation-operator cell areas are implausibly small (median={median_area:.6g} km2, total={total_area:.6g} km2); probable projected-coordinate unit error"
                        )
    except (OSError, ValueError, KeyError) as exc:
        errors.append(f"processed-evidence sanity check failed: {exc}")
    return errors



def _metadata_integrity_errors(spec: SourceSpec, metadata: dict[str, Any] | None) -> list[str]:
    """Verify processed evidence hashes declared by source metadata."""
    if not metadata:
        return []
    errors: list[str] = []
    required = [ROOT / relative for relative in spec.required_paths]
    by_name = {path.name: path for path in required}

    def verify_named(name: str, expected: Any, label: str) -> None:
        if not isinstance(expected, str) or len(expected) != 64:
            errors.append(f"{label} for {name} is not a SHA-256 digest")
            return
        path = by_name.get(name)
        if path is None:
            errors.append(f"{label} references undeclared file {name}")
            return
        if not path.is_file():
            return
        actual = sha256_file(path)
        if actual.lower() != expected.lower():
            errors.append(
                f"{path.relative_to(ROOT)} SHA-256 mismatch: expected {expected}, got {actual}"
            )

    multi = metadata.get("processed_files_sha256")
    if isinstance(multi, dict):
        for name, expected in sorted(multi.items()):
            verify_named(str(name), expected, "processed_files_sha256")

    single = metadata.get("processed_file_sha256")
    if single is not None:
        csv_paths = [path for path in required if path.suffix.lower() == ".csv"]
        if len(csv_paths) == 1:
            verify_named(csv_paths[0].name, single, "processed_file_sha256")
        else:
            errors.append("processed_file_sha256 cannot be mapped uniquely to a required CSV")

    operator = metadata.get("operator_file_sha256")
    if operator is not None:
        operator_name = metadata.get("operator_file")
        if isinstance(operator_name, str) and operator_name in by_name:
            verify_named(operator_name, operator, "operator_file_sha256")
        else:
            npz_paths = [path for path in required if path.suffix.lower() == ".npz"]
            if len(npz_paths) == 1:
                verify_named(npz_paths[0].name, operator, "operator_file_sha256")
            else:
                errors.append("operator_file_sha256 cannot be mapped uniquely to a required NPZ")
    return errors

def source_status(source_id: str) -> dict[str, Any]:
    """Return fail-closed availability and integrity information for one source."""
    spec = SOURCES[source_id]
    resolved = [ROOT / relative for relative in spec.required_paths]
    missing = [str(path.relative_to(ROOT)) for path in resolved if not path.exists()]
    status: dict[str, Any] = asdict(spec)
    status["required_paths"] = list(spec.required_paths)
    status["missing_paths"] = missing
    status["available"] = not missing
    status["file_sha256"] = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in resolved
        if path.exists() and path.is_file()
    }
    metadata_path = _metadata_path_for(spec)
    metadata: dict[str, Any] | None = None
    if metadata_path is not None and metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            status["available"] = False
            status["metadata_error"] = str(exc)
    status["metadata"] = metadata
    integrity_errors = _metadata_integrity_errors(spec, metadata) if not missing else []
    status["integrity_errors"] = integrity_errors
    sanity_errors = _source_sanity_errors(source_id) if not missing else []
    status["sanity_errors"] = sanity_errors
    if integrity_errors or sanity_errors:
        status["available"] = False
    status["status"] = "available" if status["available"] else "missing_or_invalid"
    return status


def validation_stack_status() -> dict[str, Any]:
    statuses = {source_id: source_status(source_id) for source_id in SOURCES}
    available = [key for key, value in statuses.items() if value["available"]]
    missing = [key for key in SOURCES if key not in available]
    core_five_ids = [key for key in SOURCES if key != "nsidc_0611_v4"]
    core_five_available = all(statuses[key]["available"] for key in core_five_ids)
    return {
        "required_source_count": len(SOURCES),
        "available_source_count": len(available),
        "all_six_observational_products_available": len(available) == len(SOURCES),
        "core_five_calibration_validation_stack_complete": core_five_available,
        "ice_age_structural_diagnostic_available": statuses["nsidc_0611_v4"]["available"],
        "available_sources": available,
        "missing_sources": missing,
        "sources": statuses,
        "scientific_design": {
            "primary_area_calibration": "nsidc_g02202_v6",
            "long_volume_constraint": "piomas_v2_1_common_domain",
            "development_informed_satellite_thickness_constraints": [
                "cryosat2_rdeft4_v1",
                "icesat2_is2sitmogr4_v4",
            ],
            "development_area_cross_dataset_diagnostic": "osi_saf_osi450a1_v3_1",
            "structural_multiyear_ice_diagnostic": "nsidc_0611_v4",
            "spatial_comparison_rule": (
                "EGCM is projected onto each product's explicit processed spatial observation operator"
            ),
        },
    }


def _read_csv_checked(path: Path, required: set[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, skipinitialspace=True)
    frame.columns = [str(column).strip() for column in frame.columns]
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name} missing required columns: {missing}")
    return frame


def load_physical_source(source_id: str) -> pd.DataFrame | None:
    """Load one physical evidence stream without merging products together."""
    if source_id not in {
        "piomas_v2_1",
        "cryosat2_rdeft4_v1",
        "icesat2_is2sitmogr4_v4",
    }:
        raise ValueError(f"{source_id!r} is not a physical source")
    if not source_status(source_id)["available"]:
        return None
    if source_id == "piomas_v2_1":
        path = PHYSICAL_DIR / "piomas_volume_monthly.csv"
        frame = _read_csv_checked(path, {"year", "month", "volume_million_km3"})
    elif source_id == "cryosat2_rdeft4_v1":
        path = PHYSICAL_DIR / "cryosat2_rdeft4_monthly.csv"
        frame = _read_csv_checked(path, {"year", "month", "mean_thickness_m"})
    else:
        path = PHYSICAL_DIR / "icesat2_is2sitmogr4_monthly.csv"
        frame = _read_csv_checked(path, {"year", "month", "mean_thickness_m"})
    if frame[["year", "month"]].duplicated().any():
        raise ValueError(f"{path.name} contains duplicate year/month records")
    return frame


def load_osi_saf_month(month: int) -> pd.DataFrame | None:
    if month not in (3, 9):
        raise ValueError("OSI SAF cross-check is defined for March and September")
    if not source_status("osi_saf_osi450a1_v3_1")["available"]:
        return None
    path = OSI_SAF_DIR / f"N_{month:02d}_fixed_mask_crosscheck.csv"
    frame = _read_csv_checked(path, {"year", "area"})
    if frame["year"].duplicated().any():
        raise ValueError(f"{path.name} contains duplicate years")
    return frame


def load_ice_age_annual() -> pd.DataFrame | None:
    if not source_status("nsidc_0611_v4")["available"]:
        return None
    path = ICE_AGE_DIR / "multiyear_ice_annual.csv"
    frame = _read_csv_checked(path, {"year", "month", "multiyear_ice_fraction_of_ice"})
    if frame[["year", "month"]].duplicated().any():
        raise ValueError(f"{path.name} contains duplicate year/month records")
    values = pd.to_numeric(frame["multiyear_ice_fraction_of_ice"], errors="coerce")
    if values.isna().any() or ((values < 0.0) | (values > 1.0)).any():
        raise ValueError(f"{path.name} contains invalid multiyear-ice fractions")
    return frame


def write_stack_status(path: Path | None = None) -> Path:
    destination = path or ROOT / "ARCTIC_VALIDATION_STACK_STATUS_2026.json"
    destination.write_text(
        json.dumps(validation_stack_status(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
