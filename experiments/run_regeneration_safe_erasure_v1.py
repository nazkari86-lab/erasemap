from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from erasemap.temporal_lab import run_temporal_lab_trial


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def run(protocol_path: Path, output: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get("schema_version") != "erasemap-rse-protocol-v1":
        raise ValueError("unsupported RSE protocol")
    seeds = tuple(int(seed) for seed in protocol["seeds"])
    if len(seeds) != len(set(seeds)):
        raise ValueError("RSE protocol seeds must be unique")

    trials = []
    for seed in seeds:
        with tempfile.TemporaryDirectory(prefix=f"erasemap-rse-{seed}-") as root:
            trials.append(run_temporal_lab_trial(root, seed=seed))

    snapshot_false_complete = sum(
        trial.snapshot_complete and trial.regenerated_without_control for trial in trials
    )
    detected = sum(trial.rse_verdict == "REGENERATION_RISK" for trial in trials)
    recurrence = sum(trial.regenerated_after_control for trial in trials)
    coverage_complete = sum(trial.coverage_complete for trial in trials)
    maximum_cost = max((trial.selected_cost for trial in trials), default=0)
    gates = protocol["primary_gates"]
    gate_results = {
        "coverage_complete": coverage_complete == int(gates["coverage_complete_count"]),
        "optimal_control_cost": maximum_cost <= int(gates["optimal_control_cost_max"]),
        "post_control_regeneration": recurrence
        <= int(gates["post_control_regeneration_count_max"]),
        "rse_detection": detected == int(gates["rse_detection_count"]),
        "snapshot_false_complete": snapshot_false_complete
        == int(gates["snapshot_false_complete_count"]),
    }
    result = {
        "schema_version": "erasemap-rse-result-v1",
        "protocol_hash": hashlib.sha256(protocol_bytes).hexdigest(),
        "protocol_id": protocol["protocol_id"],
        "evidence_scope": protocol["status"],
        "claim_boundary": protocol["claim_boundary"],
        "trial_count": len(trials),
        "metrics": {
            "coverage_complete_count": coverage_complete,
            "maximum_selected_control_cost": maximum_cost,
            "post_control_regeneration_count": recurrence,
            "rse_detection_count": detected,
            "snapshot_false_complete_count": snapshot_false_complete,
        },
        "gates": gate_results,
        "passed": all(gate_results.values()),
        "trials": [trial.payload() for trial in trials],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(_canonical(result) + "\n")
    (output / "PROVENANCE.json").write_text(
        _canonical(
            {
                "protocol_path": str(protocol_path),
                "protocol_sha256": result["protocol_hash"],
                "runner": "experiments/run_regeneration_safe_erasure_v1.py",
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
        default=Path("benchmark/regeneration-safe-erasure-v1.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/regeneration-safe-erasure-v1")
    )
    args = parser.parse_args()
    result = run(args.protocol, args.output)
    print(_canonical({key: result[key] for key in ("metrics", "passed", "trial_count")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
