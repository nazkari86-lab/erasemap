from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "benchmark/topology-robust-erasure-v1.json"
DEFAULT_RESULT = ROOT / "outputs/topology-robust-erasure-v1/result.json"
PREREGISTRATION_COMMIT = "320e4372e93295f0b1d2d10fe6db9fa6e04a8b2d"


def verify(protocol_path: Path, result_path: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    result = json.loads(result_path.read_text())
    if result.get("schema_version") != "erasemap-topology-robust-erasure-result-v1":
        raise ValueError("unsupported TRE result")
    if result.get("protocol_hash") != hashlib.sha256(protocol_bytes).hexdigest():
        raise ValueError("TRE protocol hash mismatch")
    if result.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise ValueError("TRE preregistration commit mismatch")
    if result.get("claim_boundary") != protocol.get("claim_boundary"):
        raise ValueError("TRE claim boundary mismatch")
    trials = result.get("trials")
    if not isinstance(trials, list):
        raise ValueError("TRE trials must be an array")
    expected_case_ids = [
        f"mask-{int(mask)}-{int(seed)}"
        for mask in protocol["shifted_scenario_masks"]
        for seed in protocol["seeds"]
    ]
    case_ids = [str(item["case_id"]) for item in trials]
    if case_ids != expected_case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("TRE case identities or order mismatch")
    if any(int(item["scenario_mask"]) == 0 for item in trials):
        raise ValueError("TRE shifted split contains the nominal scenario")

    nominal = result.get("nominal_plan")
    robust = result.get("robust_plan")
    oracle = result.get("oracle")
    if not all(isinstance(item, dict) for item in (nominal, robust, oracle)):
        raise ValueError("TRE plan records are missing")
    assert isinstance(nominal, dict)
    assert isinstance(robust, dict)
    assert isinstance(oracle, dict)
    if (
        robust.get("control_ids") != oracle.get("control_ids")
        or int(robust["cost"]) != int(oracle["cost"])
        or robust.get("status") != oracle.get("status")
    ):
        raise ValueError("TRE production plan differs from exhaustive oracle")
    if any(
        item["nominal_control_ids"] != nominal["control_ids"]
        or int(item["nominal_cost"]) != int(nominal["cost"])
        or item["tre_control_ids"] != robust["control_ids"]
        or int(item["tre_cost"]) != int(robust["cost"])
        or item["oracle_control_ids"] != oracle["control_ids"]
        or int(item["oracle_cost"]) != int(oracle["cost"])
        for item in trials
    ):
        raise ValueError("TRE trial plan records are inconsistent")

    metrics = {
        "scenario_count": 1 + len(protocol["shifted_scenario_masks"]),
        "shifted_case_count": len(trials),
        "uncontrolled_regeneration_count": sum(
            bool(item["uncontrolled_regeneration"]) for item in trials
        ),
        "nominal_plan_regeneration_count": sum(
            bool(item["nominal_plan_regeneration"]) for item in trials
        ),
        "tre_post_control_regeneration_count": sum(
            bool(item["tre_post_control_regeneration"]) for item in trials
        ),
        "tre_oracle_mismatch_count": sum(
            not bool(item["oracle_match"]) for item in trials
        ),
        "nominal_selected_cost": int(nominal["cost"]),
        "tre_selected_cost": int(robust["cost"]),
        "blanket_baseline_cost": int(
            protocol["declared_control_costs"]["destroy_all_latent_carriers"]
        ),
        "adversarial_witness_count": sum(
            bool(item["adversarial_witness"]) for item in trials
        ),
    }
    if metrics != result.get("metrics"):
        raise ValueError("TRE metrics do not match trial records")
    expected_gates = {}
    for key, expected_value in protocol["primary_gates"].items():
        metric_key = key.removesuffix("_max")
        observed = int(metrics[metric_key])
        expected = int(expected_value)
        expected_gates[key] = (
            observed <= expected if key.endswith("_max") else observed == expected
        )
    if result.get("gates") != expected_gates:
        raise ValueError("TRE gate results do not match recomputed metrics")
    passed = all(expected_gates.values())
    if bool(result.get("passed")) != passed:
        raise ValueError("TRE final decision mismatch")
    return {"metrics": metrics, "passed": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
