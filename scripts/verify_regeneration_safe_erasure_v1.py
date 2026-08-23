from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "benchmark/regeneration-safe-erasure-v1.json"
DEFAULT_RESULT = ROOT / "outputs/regeneration-safe-erasure-v1/result.json"


def verify(protocol_path: Path, result_path: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    result = json.loads(result_path.read_text())
    expected_hash = hashlib.sha256(protocol_bytes).hexdigest()
    if result.get("protocol_hash") != expected_hash:
        raise ValueError("RSE protocol hash mismatch")
    if result.get("protocol_id") != protocol.get("protocol_id"):
        raise ValueError("RSE protocol id mismatch")
    trials = result.get("trials")
    if not isinstance(trials, list) or len(trials) != len(protocol["seeds"]):
        raise ValueError("RSE trial count mismatch")
    if [item.get("seed") for item in trials] != protocol["seeds"]:
        raise ValueError("RSE trial seed order mismatch")

    metrics = {
        "coverage_complete_count": sum(bool(item["coverage_complete"]) for item in trials),
        "maximum_selected_control_cost": max(
            (int(item["selected_cost"]) for item in trials), default=0
        ),
        "post_control_regeneration_count": sum(
            bool(item["regenerated_after_control"]) for item in trials
        ),
        "rse_detection_count": sum(
            item["rse_verdict"] == "REGENERATION_RISK" for item in trials
        ),
        "snapshot_false_complete_count": sum(
            bool(item["snapshot_complete"] and item["regenerated_without_control"])
            for item in trials
        ),
    }
    if result.get("metrics") != metrics:
        raise ValueError("RSE metrics do not match trial records")
    if any(item["shortest_witness"] != ["backup_restore"] for item in trials):
        raise ValueError("RSE shortest witness drift")
    if any(
        item["selected_controls"] != ["persistent-subject-tombstone"] for item in trials
    ):
        raise ValueError("RSE selected control drift")

    gates = protocol["primary_gates"]
    expected_gates = {
        "coverage_complete": metrics["coverage_complete_count"]
        == int(gates["coverage_complete_count"]),
        "optimal_control_cost": metrics["maximum_selected_control_cost"]
        <= int(gates["optimal_control_cost_max"]),
        "post_control_regeneration": metrics["post_control_regeneration_count"]
        <= int(gates["post_control_regeneration_count_max"]),
        "rse_detection": metrics["rse_detection_count"]
        == int(gates["rse_detection_count"]),
        "snapshot_false_complete": metrics["snapshot_false_complete_count"]
        == int(gates["snapshot_false_complete_count"]),
    }
    if result.get("gates") != expected_gates:
        raise ValueError("RSE gate results mismatch")
    if bool(result.get("passed")) != all(expected_gates.values()):
        raise ValueError("RSE final decision mismatch")
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
