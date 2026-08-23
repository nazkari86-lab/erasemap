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
PREREGISTRATION_COMMIT = "c2f83dfdadc2a9f49082d7c27621aca985d19947"


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _design(protocol: dict[str, Any]) -> ProbeDesign:
    return ProbeDesign(
        tuple(protocol["candidate_mechanism_ids"]),
        tuple(tuple(row) for row in protocol["probe_rows"]),
        int(protocol["max_failures"]),
        int(protocol["error_budget"]),
    )


def _recompute_metrics(
    trials: list[dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, int]:
    valid = [item for item in trials if item["kind"] == "valid"]
    safe = [item for item in trials if item["kind"] == "safe"]
    negative = [item for item in trials if item["kind"] not in {"valid", "safe"}]
    return {
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
        "negative_case_count": len(negative),
        "negative_case_pass_count": sum(
            item["verdict"] == TomographyVerdict.UNVERIFIED.value
            for item in negative
        ),
        "false_localization_count": sum(
            item["verdict"] == TomographyVerdict.LOCALIZED.value
            and tuple(item["support"]) != tuple(item["active_ids"])
            for item in trials
        ),
        "oracle_mismatch_count": sum(not bool(item["oracle_match"]) for item in trials),
        "post_control_recurrence_count": sum(
            item["post_control_recurrence"] is True for item in valid
        ),
        "retained_subject_loss_count": sum(
            bool(item["retained_subject_loss"]) for item in valid
        ),
        "tomography_probe_count": len(protocol["probe_rows"]),
        "individual_audit_probe_count": int(protocol["individual_audit_probe_count"]),
    }


def verify(
    protocol_path: Path,
    reveal_path: Path,
    result_path: Path,
) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    reveal = json.loads(reveal_path.read_text())
    result = json.loads(result_path.read_text())
    if result.get("schema_version") != "erasemap-erasure-tomography-result-v1":
        raise ValueError("unsupported erasure tomography result")
    if result.get("protocol_hash") != hashlib.sha256(protocol_bytes).hexdigest():
        raise ValueError("erasure tomography protocol hash mismatch")
    reveal_hash = _canonical_sha256(reveal)
    if reveal_hash != protocol["support_schedule"]["canonical_sha256"]:
        raise ValueError("erasure tomography reveal commitment mismatch")
    if result.get("reveal_hash") != reveal_hash:
        raise ValueError("erasure tomography result reveal hash mismatch")
    if result.get("preregistration_commit") != PREREGISTRATION_COMMIT:
        raise ValueError("erasure tomography preregistration commit mismatch")
    if result.get("claim_boundary") != protocol.get("claim_boundary"):
        raise ValueError("erasure tomography claim boundary mismatch")
    trials = result.get("trials")
    if not isinstance(trials, list):
        raise ValueError("erasure tomography trials must be an array")
    expected_case_ids = [str(item["case_id"]) for item in reveal["cases"]]
    actual_case_ids = [str(item["case_id"]) for item in trials]
    if actual_case_ids != expected_case_ids or len(actual_case_ids) != len(set(actual_case_ids)):
        raise ValueError("erasure tomography case identity or order mismatch")

    design = _design(protocol)
    for case, trial in zip(reveal["cases"], trials, strict=True):
        if (
            trial["kind"] != case["kind"]
            or int(trial["seed"]) != int(case["seed"])
            or tuple(trial["active_ids"]) != tuple(case["active_ids"])
        ):
            raise ValueError("erasure tomography trial differs from reveal")
        evidence = TomographyEvidence(**trial["evidence"])
        commitments = tuple(trial["subject_commitments"])
        workflows = tuple(bool(item) for item in trial["workflow_evidence_complete"])
        if evidence.subjects_isolated != (len(commitments) == len(set(commitments))):
            raise ValueError("subject-isolation evidence mismatch")
        if evidence.workflows_executed != all(workflows):
            raise ValueError("workflow-execution evidence mismatch")
        oracle = oracle_decode(
            design,
            tuple(bool(item) for item in trial["observations"]),
            evidence,
        )
        reported_oracle = trial["oracle"]
        expected_oracle = {
            "verdict": oracle.verdict.value,
            "support": list(oracle.support),
            "admissible_supports": [list(item) for item in oracle.admissible_supports],
            "distance": oracle.distance,
        }
        if reported_oracle != expected_oracle:
            raise ValueError("erasure tomography oracle record mismatch")
        report_tuple = (
            trial["verdict"],
            tuple(trial["support"]),
            tuple(tuple(item) for item in trial["admissible_supports"]),
            trial["distance"],
        )
        oracle_tuple = (
            oracle.verdict.value,
            oracle.support,
            oracle.admissible_supports,
            oracle.distance,
        )
        if bool(trial["oracle_match"]) != (report_tuple == oracle_tuple):
            raise ValueError("erasure tomography oracle-match flag mismatch")

    metrics = _recompute_metrics(trials, protocol)
    if result.get("metrics") != metrics:
        raise ValueError("erasure tomography metrics mismatch")
    gates = {}
    for gate_id, expected_value in protocol["primary_gates"].items():
        metric_id = gate_id.removesuffix("_max")
        observed = metrics[metric_id]
        expected = int(expected_value)
        gates[gate_id] = observed <= expected if gate_id.endswith("_max") else observed == expected
    if result.get("gates") != gates:
        raise ValueError("erasure tomography gates mismatch")
    passed = all(gates.values()) and len(gates) == len(protocol["primary_gates"])
    if bool(result.get("passed")) != passed:
        raise ValueError("erasure tomography final decision mismatch")
    return {"metrics": metrics, "passed": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "benchmark/erasure-tomography-v1.json",
    )
    parser.add_argument(
        "--reveal",
        type=Path,
        default=ROOT / "benchmark/erasure-tomography-v1-reveal.json",
    )
    parser.add_argument(
        "--result",
        type=Path,
        default=ROOT / "outputs/erasure-tomography-v1/result.json",
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, args.reveal, args.result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
