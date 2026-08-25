from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from erasemap.ghostgraph import GraphHypothesis  # noqa: E402
from erasemap.ghostgraph_action import (  # noqa: E402
    ActionSignature,
    action_signature,
    assess_action_identifiability,
    build_global_policy,
)
from erasemap.ghostgraph_action_oracle import oracle_global_policy_value  # noqa: E402
from erasemap.ghostgraph_t_benchmark import experiments, generate_cases  # noqa: E402
from erasemap.ghostgraph_t_eval import evaluate_strategy  # noqa: E402
from erasemap.holdout_report import wilson95  # noqa: E402

CORE_FILES = (
    "src/erasemap/ghostgraph.py",
    "src/erasemap/ghostgraph_action.py",
    "src/erasemap/ghostgraph_action_oracle.py",
    "src/erasemap/ghostgraph_t_benchmark.py",
    "src/erasemap/ghostgraph_t_eval.py",
    "experiments/run_ghostgraph_t_v1.py",
)


def canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def digest(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


def source_digest(root: Path) -> str:
    payload = [
        {"path": relative, "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest()}
        for relative in CORE_FILES
    ]
    return digest(payload)


def graph_payload(graph: GraphHypothesis) -> dict[str, object]:
    return {
        "graph_id": graph.graph_id,
        "edges": [
            {
                "edge_id": edge.edge_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "operation_id": edge.operation_id,
            }
            for edge in graph.edges
        ],
        "initial_node_ids": list(graph.initial_node_ids),
        "residual_node_ids": list(graph.residual_node_ids),
    }


def case_manifest() -> list[dict[str, object]]:
    return [
        {
            "case_id": case.case_id,
            "split": case.split,
            "expected": case.expected,
            "truth": graph_payload(case.truth),
            "catalogue_ids": [item.graph_id for item in case.catalogue],
        }
        for case in generate_cases()
    ]


def action_payload(item: ActionSignature | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "controllable": item.controllable,
        "minimum_size": item.minimum_size,
        "minimal_control_sets": [list(control) for control in item.minimal_control_sets],
    }


def run(protocol_path: Path, output: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence directory: {output}")
    protocol = json.loads(protocol_path.read_text())
    if protocol.get("schema_version") != "erasemap-ghostgraph-t-v1":
        raise ValueError("unsupported GhostGraph-T protocol")
    if source_digest(ROOT) != protocol["core_sha256"]:
        raise ValueError("GhostGraph-T core source drift")
    manifest = case_manifest()
    if digest(manifest) != protocol["case_manifest_sha256"]:
        raise ValueError("GhostGraph-T case manifest drift")

    cases = generate_cases()
    probes = experiments()
    strategies = tuple(protocol["strategies"])
    catalogues = {
        tuple(item.graph_id for item in case.catalogue): case.catalogue for case in cases
    }
    policies = {key: build_global_policy(value, probes) for key, value in catalogues.items()}
    oracle_mismatches = 0
    identifiability: list[dict[str, object]] = []
    for key, catalogue in catalogues.items():
        policy = policies[key]
        oracle = oracle_global_policy_value(catalogue, probes)
        actual = (
            policy.root_worst_case_cost,
            policy.root_worst_case_probes,
        )
        if oracle is None or actual != oracle[:2]:
            oracle_mismatches += 1
        report = assess_action_identifiability(catalogue, probes)
        identifiability.append(
            {
                "catalogue_ids": list(key),
                "hypotheses": len(catalogue),
                "action_classes": report.action_class_count,
                "identifiable": report.identifiable,
                "information_lower_bound_probes": report.information_lower_bound_probes,
                "maximum_query_outcomes": report.maximum_query_outcomes,
                "global_worst_case_cost": policy.root_worst_case_cost,
                "global_worst_case_probes": policy.root_worst_case_probes,
                "oracle_root": None if oracle is None else list(oracle),
            }
        )

    trials: list[dict[str, object]] = []
    for case_index, case in enumerate(cases):
        key = tuple(item.graph_id for item in case.catalogue)
        truth_action = action_signature(case.truth)
        for strategy_index, strategy in enumerate(strategies):
            outcome = evaluate_strategy(
                strategy,
                case.truth,
                case.catalogue,
                probes,
                global_policy=policies[key],
                random_seed=int(protocol["random_seed"]) + case_index * 17 + strategy_index,
            )
            correct = (
                outcome.verdict == "ACTION_IDENTIFIED"
                and case.expected == "ACTION_IDENTIFIED"
                and outcome.predicted_action == truth_action
            ) or (
                outcome.verdict == "OUT_OF_HYPOTHESIS"
                and case.expected == "OUT_OF_HYPOTHESIS"
            )
            false_confident = outcome.verdict == "ACTION_IDENTIFIED" and not correct
            trials.append(
                {
                    "case_id": case.case_id,
                    "correct": correct,
                    "executed_experiment_ids": list(outcome.executed_experiment_ids),
                    "expected": case.expected,
                    "false_confident": false_confident,
                    "predicted_action": action_payload(outcome.predicted_action),
                    "probe_cost": outcome.probe_cost,
                    "probe_count": len(outcome.executed_experiment_ids),
                    "split": case.split,
                    "strategy": strategy,
                    "truth_action": action_payload(truth_action),
                    "verdict": outcome.verdict,
                }
            )

    strategy_metrics = _aggregate(trials, strategies)
    global_metrics = next(
        item for item in strategy_metrics if item["strategy"] == "global-action-policy"
    )
    exhaustive_metrics = next(
        item for item in strategy_metrics if item["strategy"] == "nonadaptive-exhaustive"
    )
    exact_ablation = next(
        item
        for item in strategy_metrics
        if item["strategy"] == "exact-graph-minimax-ablation"
    )
    gates = {
        "global_false_confident_count": global_metrics["false_confident_count"]
        <= protocol["gates"]["global_false_confident_count_max"],
        "global_correct_count": global_metrics["correct_count"]
        >= protocol["gates"]["global_correct_count_min"],
        "global_ood_detection_count": global_metrics["ood_detection_count"]
        >= protocol["gates"]["global_ood_detection_count_min"],
        "global_mean_probe_count_below_exhaustive": global_metrics["mean_probe_count"]
        < exhaustive_metrics["mean_probe_count"],
        "global_mean_probe_cost_below_exhaustive": global_metrics["mean_probe_cost"]
        < exhaustive_metrics["mean_probe_cost"],
        "global_oracle_mismatch_count": oracle_mismatches
        <= protocol["gates"]["global_oracle_mismatch_count_max"],
        "action_objective_resolves_more_than_exact_graph_ablation": global_metrics[
            "correct_count"
        ]
        > exact_ablation["correct_count"],
    }
    result = {
        "schema_version": "erasemap-ghostgraph-t-result-v1",
        "success": all(gates.values()),
        "claim_boundary": protocol["claim_boundary"],
        "protocol_sha256": digest(protocol),
        "case_manifest_sha256": digest(manifest),
        "core_sha256": source_digest(ROOT),
        "case_count": len(cases),
        "trial_count": len(trials),
        "identifiability": identifiability,
        "strategy_metrics": strategy_metrics,
        "oracle_mismatch_count": oracle_mismatches,
        "gates": gates,
    }
    output.mkdir(parents=True)
    (output / "result.json").write_bytes(canonical(result) + b"\n")
    (output / "trials.jsonl").write_text(
        "".join(canonical(item).decode() + "\n" for item in trials)
    )
    (output / "case-manifest.json").write_bytes(canonical(manifest) + b"\n")
    provenance = {
        "python": sys.version,
        "platform": platform.platform(),
        "protocol": str(protocol_path.relative_to(ROOT)),
        "core_files": list(CORE_FILES),
    }
    (output / "PROVENANCE.json").write_bytes(canonical(provenance) + b"\n")
    return result


def _aggregate(
    trials: list[dict[str, object]],
    strategies: tuple[str, ...],
) -> list[dict[str, object]]:
    by_strategy: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trial in trials:
        by_strategy[str(trial["strategy"])].append(trial)
    output = []
    for strategy in strategies:
        rows = by_strategy[strategy]
        false_confident = sum(bool(item["false_confident"]) for item in rows)
        interval = wilson95(false_confident, len(rows))
        split_correct = {
            split: sum(bool(item["correct"]) for item in rows if item["split"] == split)
            for split in sorted({str(item["split"]) for item in rows})
        }
        output.append(
            {
                "strategy": strategy,
                "trials": len(rows),
                "correct_count": sum(bool(item["correct"]) for item in rows),
                "false_confident_count": false_confident,
                "false_confident_rate": false_confident / len(rows),
                "false_confident_wilson95": None if interval is None else list(interval),
                "ood_detection_count": sum(
                    item["expected"] == "OUT_OF_HYPOTHESIS"
                    and item["verdict"] == "OUT_OF_HYPOTHESIS"
                    for item in rows
                ),
                "unverified_count": sum(item["verdict"] == "UNVERIFIED" for item in rows),
                "mean_probe_count": sum(int(item["probe_count"]) for item in rows)
                / len(rows),
                "mean_probe_cost": sum(int(item["probe_cost"]) for item in rows) / len(rows),
                "split_correct_count": split_correct,
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "benchmark/ghostgraph-t-v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ghostgraph-t-v1",
    )
    args = parser.parse_args()
    result = run(args.protocol, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
