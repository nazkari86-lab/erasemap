from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from erasemap.temporal_multipath import multipath_controls
from erasemap.temporal_robust_lab import (
    OPTIONAL_TRANSITION_IDS,
    brute_force_robust_oracle,
    nominal_plan,
    robust_plan,
    run_robust_physical_trial,
    topology_uncertainty_envelope,
)

PREREGISTRATION_COMMIT = "320e4372e93295f0b1d2d10fe6db9fa6e04a8b2d"


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def run(protocol_path: Path, output: Path) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get("schema_version") != "erasemap-topology-robust-erasure-v1":
        raise ValueError("unsupported TRE protocol")
    if tuple(protocol["optional_transition_ids"]) != OPTIONAL_TRANSITION_IDS:
        raise ValueError("TRE optional transition catalogue differs from preregistration")
    envelope = topology_uncertainty_envelope()
    controls = multipath_controls()
    declared_costs = {item.id: item.cost for item in controls}
    if protocol["declared_control_costs"] != declared_costs:
        raise ValueError("TRE control costs differ from preregistration")
    if int(protocol["maximum_mutations"]) != envelope.max_mutations:
        raise ValueError("TRE mutation budget differs from preregistration")

    nominal = nominal_plan(envelope, controls)
    robust = robust_plan(envelope, controls)
    oracle_ids, oracle_cost, oracle_status = brute_force_robust_oracle(
        envelope, controls
    )
    trials = []
    for mask_value in protocol["shifted_scenario_masks"]:
        mask = int(mask_value)
        for seed_value in protocol["seeds"]:
            seed = int(seed_value)
            with tempfile.TemporaryDirectory(
                prefix=f"erasemap-tre-{mask}-{seed}-"
            ) as root:
                trials.append(
                    run_robust_physical_trial(
                        root,
                        scenario_mask=mask,
                        seed=seed,
                        selected_nominal_plan=nominal,
                        selected_robust_plan=robust,
                    )
                )

    metrics = {
        "scenario_count": len(envelope.scenarios),
        "shifted_case_count": len(trials),
        "uncontrolled_regeneration_count": sum(
            item.uncontrolled_regeneration for item in trials
        ),
        "nominal_plan_regeneration_count": sum(
            item.nominal_plan_regeneration for item in trials
        ),
        "tre_post_control_regeneration_count": sum(
            item.tre_post_control_regeneration for item in trials
        ),
        "tre_oracle_mismatch_count": sum(not item.oracle_match for item in trials),
        "nominal_selected_cost": nominal.total_cost,
        "tre_selected_cost": robust.total_cost,
        "blanket_baseline_cost": declared_costs["destroy_all_latent_carriers"],
        "adversarial_witness_count": sum(bool(item.adversarial_witness) for item in trials),
    }
    gates = {}
    for key, expected_value in protocol["primary_gates"].items():
        metric_key = key.removesuffix("_max")
        observed = int(metrics[metric_key])
        expected = int(expected_value)
        gates[key] = observed <= expected if key.endswith("_max") else observed == expected
    witness = robust.shortest_adversarial_witness
    result = {
        "schema_version": "erasemap-topology-robust-erasure-result-v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_hash": hashlib.sha256(protocol_bytes).hexdigest(),
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "evidence_scope": "PROJECT_AUTHORED_PROSPECTIVE_FINITE_TOPOLOGY_ENVELOPE_LOCAL_LAB",
        "claim_boundary": protocol["claim_boundary"],
        "nominal_plan": {
            "control_ids": nominal.control_ids,
            "cost": nominal.total_cost,
        },
        "robust_plan": {
            "control_ids": robust.control_ids,
            "cost": robust.total_cost,
            "status": robust.status.value,
            "robustness_premium": robust.total_cost - nominal.total_cost,
            "shortest_baseline_witness": (
                {
                    "scenario_id": witness.scenario_id,
                    "mutation_count": witness.mutation_count,
                    "transition_ids": witness.transition_ids,
                    "witness_state": sorted(witness.witness_state),
                }
                if witness is not None
                else None
            ),
        },
        "oracle": {
            "control_ids": oracle_ids,
            "cost": oracle_cost,
            "status": oracle_status,
        },
        "metrics": metrics,
        "gates": gates,
        "passed": all(gates.values()) and len(gates) == len(protocol["primary_gates"]),
        "trials": [item.payload() for item in trials],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(_canonical(result) + "\n")
    (output / "PROVENANCE.json").write_text(
        _canonical(
            {
                "preregistration_commit": PREREGISTRATION_COMMIT,
                "protocol_path": str(protocol_path),
                "protocol_sha256": result["protocol_hash"],
                "runner": "experiments/run_topology_robust_erasure_v1.py",
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
        default=Path("benchmark/topology-robust-erasure-v1.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/topology-robust-erasure-v1")
    )
    args = parser.parse_args()
    result = run(args.protocol, args.output)
    print(_canonical({key: result[key] for key in ("metrics", "passed")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
