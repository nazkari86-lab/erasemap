from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from erasemap.temporal_multipath import (
    ALL_CARRIERS,
    CARRIER_FACTS,
    MultipathTrial,
    run_coverage_fault_trial,
    run_risk_trial,
    run_safe_trial,
)

PREREGISTRATION_COMMIT = "110bb63110fac66ff3e1b7f504b02b4cb3b57d6e"


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _run_risk_trials(protocol: dict[str, Any]) -> list[MultipathTrial]:
    trials = []
    for family, seeds in protocol["risk_families"].items():
        carriers = (
            ALL_CARRIERS
            if family == "mixed_multicarrier"
            else frozenset({CARRIER_FACTS[family]})
        )
        for seed_value in seeds:
            seed = int(seed_value)
            with tempfile.TemporaryDirectory(prefix=f"erasemap-rse-v2-{seed}-") as root:
                trials.append(
                    run_risk_trial(
                        root,
                        case_id=f"{family}-{seed}",
                        seed=seed,
                        carriers=carriers,
                    )
                )
    return trials


def run(protocol_path: Path, output: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get("schema_version") != "erasemap-rse-multipath-v2":
        raise ValueError("unsupported RSE v2 protocol")
    risk = _run_risk_trials(protocol)
    safe = []
    for seed_value in protocol["safe_seeds"]:
        seed = int(seed_value)
        with tempfile.TemporaryDirectory(prefix=f"erasemap-rse-safe-{seed}-") as root:
            safe.append(run_safe_trial(root, seed=seed))
    coverage_faults = []
    for seed_value in protocol["coverage_fault_seeds"]:
        seed = int(seed_value)
        with tempfile.TemporaryDirectory(prefix=f"erasemap-rse-coverage-{seed}-") as root:
            coverage_faults.append(run_coverage_fault_trial(root, seed=seed))

    all_trials = [*risk, *safe, *coverage_faults]
    metrics = {
        "risk_case_count": len(risk),
        "safe_case_count": len(safe),
        "coverage_fault_case_count": len(coverage_faults),
        "rse_risk_detection_count": sum(
            item.rse_verdict == "REGENERATION_RISK" for item in risk
        ),
        "rse_safe_specificity_count": sum(
            item.rse_verdict == "RSE_VERIFIED" for item in safe
        ),
        "rse_coverage_fail_closed_count": sum(
            item.rse_verdict == "INCOMPLETE_COVERAGE" for item in coverage_faults
        ),
        "snapshot_pcug_false_complete_count": sum(
            item.snapshot_pcug_verdict == "COMPLETE"
            and item.regenerated_without_control
            for item in risk
        ),
        "blanket_carrier_false_incomplete_count": sum(
            item.blanket_carrier_verdict == "INCOMPLETE" for item in safe
        ),
        "post_msc_physical_regeneration_count": sum(
            item.regenerated_after_control for item in risk
        ),
        "exact_oracle_mismatch_count": sum(not item.oracle_match for item in risk),
        "maximum_selected_control_cost": max(
            (item.selected_cost for item in risk), default=0
        ),
    }
    gates = protocol["primary_gates"]
    gate_results = {}
    for key, expected in gates.items():
        metric_key = key.removesuffix("_max")
        observed = metrics[metric_key]
        is_upper_bound = key.endswith("_max") or key == "maximum_selected_control_cost"
        gate_results[key] = (
            observed <= int(expected) if is_upper_bound else observed == int(expected)
        )
    result = {
        "schema_version": "erasemap-rse-multipath-result-v2",
        "protocol_hash": hashlib.sha256(protocol_bytes).hexdigest(),
        "protocol_id": protocol["protocol_id"],
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "evidence_scope": "PROJECT_AUTHORED_PROSPECTIVE_MULTIPATH_LOCAL_LAB",
        "claim_boundary": protocol["claim_boundary"],
        "metrics": metrics,
        "gates": gate_results,
        "passed": all(gate_results.values()) and len(gate_results) == len(gates),
        "trials": [item.payload() for item in all_trials],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(_canonical(result) + "\n")
    (output / "PROVENANCE.json").write_text(
        _canonical(
            {
                "preregistration_commit": PREREGISTRATION_COMMIT,
                "protocol_path": str(protocol_path),
                "protocol_sha256": result["protocol_hash"],
                "runner": "experiments/run_regeneration_safe_erasure_v2.py",
            }
        )
        + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("benchmark/regeneration-safe-erasure-v2.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/regeneration-safe-erasure-v2")
    )
    args = parser.parse_args()
    result = run(args.protocol, args.output)
    print(_canonical({key: result[key] for key in ("metrics", "passed")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
