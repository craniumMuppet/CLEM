#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from dataclasses import replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from climate_model import ModelConfig
from validation_segmentation import run_segmented
from validate_v2296 import (
    COMMON_VALIDATION_SAMPLE_YEARS,
    _open_water_validation,
    annual_mean_frame,
    common_validation_sample,
    historical_external_metrics,
    seasonal_slope_ratio,
    arctic_transient_metrics,
)
from sea_ice_validation import evaluate_result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--overrides', required=True)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    overrides = json.loads(args.overrides)
    cfg = replace(
        ModelConfig(),
        start_year=1850.0,
        duration_years=177.0,
        scenario='ssp245',
        dt_years=0.05,
        record_every_years=COMMON_VALIDATION_SAMPLE_YEARS,
        auto_initialize_from_1850=False,
        **overrides,
    )
    result = run_segmented(cfg, segment_years=40.0)
    sea = evaluate_result(result)
    cal = sea['calibration']['months']
    dev = sea['validation_informed_development_evaluation']['months']
    rolling = sea['rolling_origin_historical_evaluation']['metrics']
    raw = result.dataframe
    annual = annual_mean_frame(common_validation_sample(raw))
    metrics = historical_external_metrics(annual)
    out = {
        'overrides': overrides,
        'march_area_mean': cal['3']['area']['model_mean_million_km2'],
        'march_area_trend': cal['3']['area']['model_trend_million_km2_per_decade'],
        'march_area_rmse': cal['3']['area']['rmse_million_km2'],
        'march_extent_trend': cal['3']['extent']['model_trend_million_km2_per_decade'],
        'september_area_mean': cal['9']['area']['model_mean_million_km2'],
        'september_area_trend': cal['9']['area']['model_trend_million_km2_per_decade'],
        'september_area_rmse': cal['9']['area']['rmse_million_km2'],
        'september_extent_trend': cal['9']['extent']['model_trend_million_km2_per_decade'],
        'dev_september_area_rmse': dev['9']['area']['rmse_million_km2'],
        'rolling_skill': {k: {
            'persistence': v['model_skill_score_vs_persistence'],
            'trend': v['model_skill_score_vs_expanding_linear_trend'],
        } for k,v in rolling.items()},
        'open_water': _open_water_validation(result),
        'annual_arctic_amplification': metrics['historical_arctic_amplification_1979_2021_ratio'],
        'seasonal_arctic_amplification': {s: seasonal_slope_ratio(raw, months) for s,months in {
            'DJF': (12,1,2), 'MAM': (3,4,5), 'JJA': (6,7,8), 'SON': (9,10,11)
        }.items()},
        'arctic_transient': arctic_transient_metrics(result),
        'sea_ice_gates': {
            'calibration_passed': sea['calibration_passed'],
            'development_passed': sea['validation_informed_development_evaluation_passed'],
            'calibration': sea['calibration_gates'],
            'development': sea['validation_informed_development_evaluation_gates'],
        },
    }
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
