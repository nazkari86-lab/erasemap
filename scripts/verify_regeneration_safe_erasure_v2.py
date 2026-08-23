from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "benchmark/regeneration-safe-erasure-v2.json"
DEFAULT_RESULT = ROOT / "outputs/regeneration-safe-erasure-v2/result.json"
PREREGISTRATION_COMMIT = "110bb63110fac66ff3e1b7f504b02b4cb3b57d6e"


def _expected_risk_cases(protocol: dict[str, Any]) -> list[str]:
    return [
        f"{family}-{int(seed)}"
        for family, seeds in protocol["risk_families"].items()
        for seed in seeds
    ]


def verify(protocol_path: Path, result_path: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    result = json.loads(result_path.read_text())
    if result.get("schema_version") != "erasemap-rse-multipath-result-v2":
        raise ValueError("unsupported RSE v2 result")
    if result.get("protocol_hash") != hashlib.sha256(protocol_bytes).hexdigest():
        raise ValueError("RSE v2 protocol hash mismatch")
    if result.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise ValueError("RSE v2 preregistration commit mismatch")
    trials = result.get("trials")
    if not isinstance(trials, list):
        raise ValueError("RSE v2 trials must be an array")
    case_ids = [str(item["case_id"]) for item in trials]
    expected_ids = [
        *_expected_risk_cases(protocol),
        *(f"safe-{int(seed)}" for seed in protocol["safe_seeds"]),
        *(
            f"coverage-fault-{int(seed)}"
            for seed in protocol["coverage_fault_seeds"]
        ),
    ]
    if case_ids != expected_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("RSE v2 case identities or order mismatch")

    risk = [item for item in trials if item["split"] == "risk"]
    safe = [item for item in trials if item["split"] == "safe"]
    coverage_faults = [item for item in trials if item["split"] == "coverage-fault"]
    metrics = {
        "risk_case_count": len(risk),
        "safe_case_count": len(safe),
        "coverage_fault_case_count": len(coverage_faults),
        "rse_risk_detection_count": sum(
            item["rse_verdict"] == "REGENERATION_RISK" for item in risk
        ),
        "rse_safe_specificity_count": sum(
            item["rse_verdict"] == "RSE_VERIFIED" for item in safe
        ),
        "rse_coverage_fail_closed_count": sum(
            item["rse_verdict"] == "INCOMPLETE_COVERAGE"
            for item in coverage_faults
        ),
        "snapshot_pcug_false_complete_count": sum(
            item["snapshot_pcug_verdict"] == "COMPLETE"
            and item["regenerated_without_control"]
            for item in risk
        ),
        "blanket_carrier_false_incomplete_count": sum(
            item["blanket_carrier_verdict"] == "INCOMPLETE" for item in safe
        ),
        "post_msc_physical_regeneration_count": sum(
            bool(item["regenerated_after_control"]) for item in risk
        ),
        "exact_oracle_mismatch_count": sum(
            not bool(item["oracle_match"]) for item in risk
        ),
        "maximum_selected_control_cost": max(
            (int(item["selected_cost"]) for item in risk), default=0
        ),
    }
    if metrics != result.get("metrics"):
        raise ValueError("RSE v2 metrics do not match trial records")
    if any(
        item["selected_controls"] != item["oracle_controls"]
        or int(item["selected_cost"]) != int(item["oracle_cost"])
        for item in risk
    ):
        raise ValueError("RSE v2 exact/oracle record mismatch")
    if any(not item["coverage_complete"] for item in [*risk, *safe]):
        raise ValueError("RSE v2 complete-coverage split contains a coverage failure")
    if any(item["coverage_complete"] for item in coverage_faults):
        raise ValueError("RSE v2 coverage-fault split passed coverage")

    gates = protocol["primary_gates"]
    expected_gates = {
        "risk_case_count": metrics["risk_case_count"] == int(gates["risk_case_count"]),
        "safe_case_count": metrics["safe_case_count"] == int(gates["safe_case_count"]),
        "coverage_fault_case_count": metrics["coverage_fault_case_count"]
        == int(gates["coverage_fault_case_count"]),
        "rse_risk_detection_count": metrics["rse_risk_detection_count"]
        == int(gates["rse_risk_detection_count"]),
        "rse_safe_specificity_count": metrics["rse_safe_specificity_count"]
        == int(gates["rse_safe_specificity_count"]),
        "rse_coverage_fail_closed_count": metrics["rse_coverage_fail_closed_count"]
        == int(gates["rse_coverage_fail_closed_count"]),
        "snapshot_pcug_false_complete_count": metrics[
            "snapshot_pcug_false_complete_count"
        ]
        == int(gates["snapshot_pcug_false_complete_count"]),
        "blanket_carrier_false_incomplete_count": metrics[
            "blanket_carrier_false_incomplete_count"
        ]
        == int(gates["blanket_carrier_false_incomplete_count"]),
        "post_msc_physical_regeneration_count_max": metrics[
            "post_msc_physical_regeneration_count"
        ]
        <= int(gates["post_msc_physical_regeneration_count_max"]),
        "exact_oracle_mismatch_count_max": metrics["exact_oracle_mismatch_count"]
        <= int(gates["exact_oracle_mismatch_count_max"]),
        "maximum_selected_control_cost": metrics["maximum_selected_control_cost"]
        <= int(gates["maximum_selected_control_cost"]),
    }
    if result.get("gates") != expected_gates:
        raise ValueError("RSE v2 gate result mismatch")
    if bool(result.get("passed")) != all(expected_gates.values()):
        raise ValueError("RSE v2 final decision mismatch")
    return {"metrics": metrics, "passed": all(expected_gates.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
