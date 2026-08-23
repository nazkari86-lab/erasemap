from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyVerdict,
)
from erasemap.erasure_tomography_oracle import oracle_decode

ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_COMMIT = "5e5adc893e990983e49370f5e96fa9f786425bfb"


def verify(protocol_path: Path, result_path: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    result = json.loads(result_path.read_text())
    if result.get("schema_version") != "erasemap-erasure-tomography-redis-result-v1":
        raise ValueError("unsupported Redis tomography result")
    if result.get("protocol_hash") != hashlib.sha256(protocol_bytes).hexdigest():
        raise ValueError("Redis tomography protocol hash mismatch")
    if result.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise ValueError("Redis tomography preregistration commit mismatch")
    if result.get("inspected_image") != protocol.get("image"):
        raise ValueError("Redis tomography image digest mismatch")
    if result.get("claim_boundary") != protocol.get("claim_boundary"):
        raise ValueError("Redis tomography claim boundary mismatch")
    trials = result.get("trials")
    if not isinstance(trials, list):
        raise ValueError("Redis tomography trials must be an array")
    expected_ids = [str(item["case_id"]) for item in protocol["cases"]]
    actual_ids = [str(item["case_id"]) for item in trials]
    if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
        raise ValueError("Redis tomography case identity or order mismatch")
    design = ProbeDesign(
        tuple(protocol["candidate_mechanism_ids"]),
        tuple(tuple(row) for row in protocol["probe_rows"]),
        int(protocol["max_failures"]),
        int(protocol["error_budget"]),
    )
    for case, trial in zip(protocol["cases"], trials, strict=True):
        if (
            int(trial["seed"]) != int(case["seed"])
            or tuple(trial["active_ids"]) != tuple(case["active_ids"])
        ):
            raise ValueError("Redis tomography trial differs from protocol")
        oracle = oracle_decode(
            design,
            tuple(trial["observations"]),
            TomographyEvidence.complete(),
        )
        report_matches = (
            trial["verdict"] == oracle.verdict.value
            and tuple(trial["support"]) == oracle.support
            and tuple(tuple(item) for item in trial["admissible_supports"])
            == oracle.admissible_supports
            and trial["distance"] == oracle.distance
        )
        if bool(trial["oracle_match"]) != report_matches:
            raise ValueError("Redis tomography oracle flag mismatch")
        digest = str(trial["evidence_sha256"])
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("invalid Redis tomography evidence digest")
    valid = [item for item in trials if item["active_ids"]]
    safe = [item for item in trials if not item["active_ids"]]
    metrics = {
        "valid_case_count": len(valid),
        "exact_support_recovery_count": sum(
            item["verdict"] == TomographyVerdict.LOCALIZED.value
            and tuple(item["support"]) == tuple(item["active_ids"])
            for item in valid
        ),
        "safe_no_recurrence_count": sum(
            item["verdict"] == TomographyVerdict.NO_OBSERVED_RECURRENCE.value
            for item in safe
        ),
        "false_localization_count": sum(
            item["verdict"] == TomographyVerdict.LOCALIZED.value
            and tuple(item["support"]) != tuple(item["active_ids"])
            for item in trials
        ),
        "oracle_mismatch_count": sum(not bool(item["oracle_match"]) for item in trials),
        "post_control_recurrence_count": sum(
            bool(item["post_control_recurrence"]) for item in valid
        ),
        "retained_subject_loss_count": sum(
            bool(item["retained_subject_loss"]) for item in trials
        ),
        "tomography_probe_count": len(protocol["probe_rows"]),
        "individual_audit_probe_count": len(protocol["candidate_mechanism_ids"]),
    }
    if result.get("metrics") != metrics:
        raise ValueError("Redis tomography metrics mismatch")
    gates = {}
    for gate_id, expected_value in protocol["primary_gates"].items():
        metric_id = gate_id.removesuffix("_max")
        expected = int(expected_value)
        gates[gate_id] = (
            metrics[metric_id] <= expected
            if gate_id.endswith("_max")
            else metrics[metric_id] == expected
        )
    if result.get("gates") != gates:
        raise ValueError("Redis tomography gates mismatch")
    passed = all(gates.values()) and len(gates) == len(protocol["primary_gates"])
    if bool(result.get("passed")) != passed:
        raise ValueError("Redis tomography decision mismatch")
    return {"metrics": metrics, "passed": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "benchmark/erasure-tomography-redis-v1.json",
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=ROOT / "outputs/erasure-tomography-redis-v1/result.json",
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
