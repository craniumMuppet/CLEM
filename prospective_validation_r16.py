"""Evidence-driven evaluator for the frozen CLEM R16 prospective holdout."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_PROTOCOL = ROOT / "validation" / "prospective" / "CLEM_R16_PROSPECTIVE_PROTOCOL.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def evaluate(evidence_json: Path | None = None, protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    base = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha256(protocol_path),
        "reserved_period": protocol["reserved_period"],
        "independent_predictive_scientific_validation_status": "not_available",
        "independent_predictive_scientific_validation_complete": False,
        "independent_predictive_scientific_validation_passed": False,
        "reason": "Prospective evidence bundle not supplied.",
    }
    if evidence_json is None or not evidence_json.exists():
        return base
    evidence = json.loads(evidence_json.read_text(encoding="utf-8"))
    required = int(protocol["reserved_period"]["required_complete_years"])
    years = sorted({int(y) for y in evidence.get("complete_usable_years", [])})
    expected = list(range(int(protocol["reserved_period"]["start_year"]), int(protocol["reserved_period"]["end_year"]) + 1))
    missing_hashes = [d.get("name", "unnamed") for d in evidence.get("datasets", []) if not d.get("raw_sha256") or not d.get("processed_sha256")]
    if years != expected or len(years) < required:
        base["reason"] = f"Need exactly the frozen complete usable years {expected}; received {years}."
        return base
    if missing_hashes:
        base["reason"] = f"Dataset provenance incomplete for: {', '.join(missing_hashes)}."
        return base
    results = evidence.get("results", {})
    variable_results: dict[str, Any] = {}
    all_pass = True
    for spec in protocol["variables"]:
        name = spec["name"]
        item = results.get(name)
        if not isinstance(item, dict):
            base["reason"] = f"Missing preregistered result for {name}."
            return base
        clem_rmse = float(item["clem_rmse"])
        baselines = {str(k): float(v) for k, v in item.get("baseline_rmse", {}).items()}
        if set(protocol["statistical_baselines"]) - set(baselines):
            base["reason"] = f"Missing preregistered baselines for {name}."
            return base
        best = min(baselines.values())
        passed = clem_rmse <= best
        all_pass = all_pass and passed
        variable_results[name] = {"clem_rmse": clem_rmse, "best_baseline_rmse": best, "passed": passed, "reported_metrics": item.get("metrics", {})}
    base.update({
        "independent_predictive_scientific_validation_status": "passed" if all_pass else "failed",
        "independent_predictive_scientific_validation_complete": True,
        "independent_predictive_scientific_validation_passed": bool(all_pass),
        "reason": "Frozen evidence was sufficient and preregistered metrics were evaluated.",
        "variable_results": variable_results,
    })
    return base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path)
    ap.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    payload = evaluate(args.evidence, args.protocol)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
