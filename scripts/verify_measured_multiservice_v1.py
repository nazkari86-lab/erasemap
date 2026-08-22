from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from erasemap.measured_systems import StrategyMeasurement, paired_summary

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "benchmark/measured-multiservice-v1.json"
RESULT = ROOT / "outputs/measured-multiservice-v1/result.json"
SUMMARY = ROOT / "benchmark/results/measured-multiservice-v1-summary.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def measurements(records: list[dict[str, Any]]) -> list[StrategyMeasurement]:
    return [
        StrategyMeasurement(
            int(item["seed"]),
            str(item["strategy"]),
            float(item["seconds"]),
            int(item["bytes_rewritten"]),
            str(item["verdict"]),
            int(item["retained_count"]),
            int(item["expected_retained_count"]),
            float(item["model_weight_delta"]),
        )
        for item in records
    ]


def close(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def verify() -> dict[str, object]:
    protocol = json.loads(PROTOCOL.read_text())
    result = json.loads(RESULT.read_text())
    public = json.loads(SUMMARY.read_text())
    if result["protocol_commitment"] != digest(PROTOCOL):
        raise ValueError("protocol commitment mismatch")
    if public["raw_result_sha256"] != digest(RESULT):
        raise ValueError("raw result hash mismatch")
    calibration_seeds = {int(item["seed"]) for item in result["calibration_records"]}
    holdout_seeds = {int(item["seed"]) for item in result["holdout_records"]}
    if calibration_seeds != set(protocol["calibration_seeds"]):
        raise ValueError("calibration seed set mismatch")
    if holdout_seeds != set(protocol["holdout_seeds"]):
        raise ValueError("holdout seed set mismatch")
    recomputed = cast(
        dict[str, Any],
        paired_summary(
            measurements(result["holdout_records"]),
            bootstrap_seed=int(protocol["bootstrap_seed"]),
            bootstrap_samples=int(protocol["bootstrap_samples"]),
        ),
    )
    numeric = (
        "bytes_reduction",
        "complete_rate",
        "maximum_model_weight_delta",
        "maximum_retained_data_loss_rate",
    )
    if any(not close(float(recomputed[key]), float(result["summary"][key])) for key in numeric):
        raise ValueError("recomputed summary mismatch")
    speedup = recomputed["paired_speedup"]
    if not close(
        float(speedup["geometric_mean"]), float(public["paired_speedup_geometric_mean"])
    ) or any(
        not close(float(left), float(right))
        for left, right in zip(
            speedup["bootstrap_ci95"], public["paired_speedup_bootstrap_ci95"], strict=True
        )
    ):
        raise ValueError("public speedup summary mismatch")
    gates = protocol["gates"]
    expected_gates = {
        "bytes_reduction": float(recomputed["bytes_reduction"])
        >= float(gates["minimum_bytes_reduction"]),
        "complete_rate": float(recomputed["complete_rate"]) >= float(gates["complete_rate"]),
        "model_weight_delta": float(recomputed["maximum_model_weight_delta"])
        <= float(gates["maximum_model_weight_delta"]),
        "retained_data_loss": float(recomputed["maximum_retained_data_loss_rate"])
        <= float(gates["maximum_retained_data_loss_rate"]),
        "speedup_ci95_lower": float(speedup["bootstrap_ci95"][0])
        >= float(gates["minimum_speedup_ci95_lower"]),
    }
    if result["gate_results"] != expected_gates:
        raise ValueError("gate result mismatch")
    selected = result["planner"]["selected_actions"]
    if selected != public["planner_selected_actions"] or result["planner"]["solver_status"] != (
        "OPTIMAL"
    ):
        raise ValueError("planner evidence mismatch")
    decision = "PASS" if all(expected_gates.values()) else "FAIL"
    if decision != result["decision"] or decision != public["decision"]:
        raise ValueError("decision mismatch")
    return {"decision": decision, "holdout_pairs": len(holdout_seeds), "summary": recomputed}


def main() -> int:
    verified = verify()
    print(json.dumps(verified, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
