from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from erasemap.erasure_tomography import ProbeDesign, TomographyVerdict, certify_design
from experiments.erasure_tomography_services import (
    RedisTomographyAdapter,
    run_redis_tomography_case,
)
from experiments.open_transfer_services import DockerService

ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_COMMIT = "5e5adc893e990983e49370f5e96fa9f786425bfb"


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _design(protocol: dict[str, Any]) -> ProbeDesign:
    return ProbeDesign(
        tuple(protocol["candidate_mechanism_ids"]),
        tuple(tuple(row) for row in protocol["probe_rows"]),
        int(protocol["max_failures"]),
        int(protocol["error_budget"]),
    )


def _wait_for_redis(adapter: RedisTomographyAdapter, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if adapter.ping():
                return
        except (RuntimeError, OSError) as exc:
            last_error = exc
        time.sleep(0.2)
    if last_error is not None:
        raise TimeoutError("Redis tomography service readiness timeout") from last_error
    raise TimeoutError("Redis tomography service readiness timeout")


def _metrics(trials: list[dict[str, object]], protocol: dict[str, Any]) -> dict[str, int]:
    valid = [item for item in trials if item["active_ids"]]
    safe = [item for item in trials if not item["active_ids"]]
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


def _gates(metrics: dict[str, int], protocol: dict[str, Any]) -> dict[str, bool]:
    gates = {}
    for gate_id, expected_value in protocol["primary_gates"].items():
        metric_id = gate_id.removesuffix("_max")
        expected = int(expected_value)
        gates[gate_id] = (
            metrics[metric_id] <= expected
            if gate_id.endswith("_max")
            else metrics[metric_id] == expected
        )
    return gates


def run(protocol_path: Path, output: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get("schema_version") != "erasemap-erasure-tomography-redis-v1":
        raise ValueError("unsupported Redis tomography protocol")
    design = _design(protocol)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="erasemap-et-redis-") as directory:
        service_root = Path(directory)
        data = service_root / "data"
        data.mkdir()
        service = DockerService(
            family="et-redis",
            image=str(protocol["image"]),
            internal_port=6379,
            root=service_root,
        )
        inspected_image = service.inspect_digest()
        service.start(
            env={},
            mounts=((data, "/data", False),),
            args=("redis-server", "--appendonly", "yes", "--dir", "/data"),
        )
        try:
            readiness = RedisTomographyAdapter(service.container_name)
            _wait_for_redis(readiness)
            trials = []
            for case in protocol["cases"]:
                adapter = RedisTomographyAdapter(service.container_name)
                trial = run_redis_tomography_case(
                    adapter,
                    design,
                    case_id=str(case["case_id"]),
                    seed=int(case["seed"]),
                    active_ids=tuple(case["active_ids"]),
                )
                trials.append(trial.payload())
        finally:
            service.stop()
    metrics = _metrics(trials, protocol)
    gates = _gates(metrics, protocol)
    result = {
        "schema_version": "erasemap-erasure-tomography-redis-result-v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_hash": hashlib.sha256(protocol_bytes).hexdigest(),
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "evidence_scope": protocol["evidence_scope"],
        "claim_boundary": protocol["claim_boundary"],
        "inspected_image": inspected_image,
        "design_certificate": {
            "support_count": certify_design(design).support_count,
            "minimum_outcome_distance": certify_design(design).minimum_outcome_distance,
            "uniquely_decodable": certify_design(design).uniquely_decodable,
        },
        "metrics": metrics,
        "gates": gates,
        "passed": all(gates.values()) and len(gates) == len(protocol["primary_gates"]),
        "trials": trials,
    }
    (output / "result.json").write_text(_canonical(result) + "\n")
    (output / "PROVENANCE.json").write_text(
        _canonical(
            {
                "protocol_sha256": result["protocol_hash"],
                "preregistration_commit": PREREGISTRATION_COMMIT,
                "inspected_image": inspected_image,
                "runner": "experiments/run_erasure_tomography_redis_v1.py",
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
        default=ROOT / "benchmark/erasure-tomography-redis-v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/erasure-tomography-redis-v1",
    )
    args = parser.parse_args()
    result = run(args.protocol, args.output)
    print(_canonical({"metrics": result["metrics"], "passed": result["passed"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
