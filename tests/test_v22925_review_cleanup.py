"""Regression checks for the v2.29.29 review cleanup."""
from pathlib import Path
from climate_model import MODEL_VERSION,ModelConfig
from monte_carlo import MONTE_CARLO_PHYSICAL_PARAMETERS,SCIENCE_PRIOR_SPECS
from release_tree_fingerprint import compute_tested_code_fingerprint
ROOT=Path(__file__).resolve().parents[1]
def test_version_and_emergency_guard_semantics():
 cfg=ModelConfig(); assert MODEL_VERSION=="2.29.29"; assert cfg.arctic_max_equivalent_thickness_m==20.0; assert cfg.arctic_max_local_ice_thickness_m==500.0
 for n in ("arctic_max_equivalent_thickness_m","arctic_max_local_ice_thickness_m"): assert n not in MONTE_CARLO_PHYSICAL_PARAMETERS and n not in SCIENCE_PRIOR_SPECS
def test_tested_code_fingerprint_has_reproducible_inventory():
 a=compute_tested_code_fingerprint(ROOT); b=compute_tested_code_fingerprint(ROOT); assert a==b; assert a["file_count"]==len(a["files"]); assert "climate_model.py" in a["files"]; assert "README.md" in a["files"]; assert "TEST_RESULTS_V2_29_26.json" not in a["files"]
def test_local_guard_not_used_in_production_area_equations():
 source=(ROOT/"climate_model.py").read_text(); refs=[line for line in source.splitlines() if "arctic_max_local_ice_thickness_m" in line]; assert all("minimum_supported" not in line for line in refs); assert "next_volume / cfg.arctic_max_local_ice_thickness_m" not in source; assert "equivalent / cfg.arctic_max_local_ice_thickness_m" not in source
