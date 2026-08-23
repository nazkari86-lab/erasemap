from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryExperiment,
    DiscoveryVerdict,
    ExecutedObservation,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
    predict_trace,
    relevant_signature,
    update_version_space,
)
from erasemap.ghostgraph_bridge import build_controls, build_topology_envelope
from erasemap.ghostgraph_lab import run_control_trial
from erasemap.ghostgraph_oracle import oracle_select_next
from erasemap.ghostgraph_planner import PlannerScore, select_next_experiment
from erasemap.temporal_robust import exact_robust_stabilization_cut

ROOT = Path(__file__).resolve().parents[1]
ACTIONABLE = frozenset(
    {
        DiscoveryVerdict.GRAPH_DISCOVERED,
        DiscoveryVerdict.PATH_CLASS_DISCOVERED,
        DiscoveryVerdict.EQUIVALENCE_CLASS,
    }
)


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def canonical_sha256(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def core_sha256(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for raw_path in paths:
        path = ROOT / raw_path
        digest.update(raw_path.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _objects(protocol: dict[str, Any]) -> tuple[
    tuple[GraphHypothesis, ...], tuple[DiscoveryExperiment, ...]
]:
    nodes = tuple(GraphNode(str(item)) for item in protocol["node_ids"])
    edge_by_id = {
        str(item["edge_id"]): GraphEdge(
            str(item["edge_id"]),
            str(item["source_id"]),
            str(item["target_id"]),
            str(item["operation_id"]),
        )
        for item in protocol["edge_catalogue"]
    }
    hypotheses = tuple(
        GraphHypothesis(
            graph_id=str(item["graph_id"]),
            nodes=nodes,
            edges=tuple(sorted(edge_by_id[str(edge_id)] for edge_id in item["edge_ids"])),
            initial_node_ids=tuple(protocol["initial_node_ids"]),
            residual_node_ids=tuple(protocol["residual_node_ids"]),
        )
        for item in protocol["hypotheses"]
    )
    experiments = tuple(
        DiscoveryExperiment(
            experiment_id=str(item["experiment_id"]),
            enabled_operation_ids=tuple(item["enabled_operation_ids"]),
            checkpoint_node_ids=tuple(item["checkpoint_node_ids"]),
            time_buckets=int(item["time_buckets"]),
            declared_cost=int(item["declared_cost"]),
        )
        for item in protocol["experiments"]
    )
    return hypotheses, experiments


def _truth_graph(
    case: dict[str, Any],
    hypotheses: tuple[GraphHypothesis, ...],
    protocol: dict[str, Any],
) -> GraphHypothesis:
    by_id = {graph.graph_id: graph for graph in hypotheses}
    if "truth_graph_id" in case:
        return by_id[str(case["truth_graph_id"])]
    raw = case["truth_graph"]
    return GraphHypothesis(
        graph_id=str(raw["graph_id"]),
        nodes=tuple(GraphNode(str(item)) for item in protocol["node_ids"]),
        edges=tuple(
            sorted(
                GraphEdge(
                    str(item["edge_id"]),
                    str(item["source_id"]),
                    str(item["target_id"]),
                    str(item["operation_id"]),
                )
                for item in raw["edges"]
            )
        ),
        initial_node_ids=tuple(raw["initial_node_ids"]),
        residual_node_ids=tuple(raw["residual_node_ids"]),
    )


def _score_tuple(score: PlannerScore | None) -> tuple[int, int, int, str] | None:
    if score is None:
        return None
    return (
        score.largest_bucket,
        score.squared_bucket_sum,
        score.declared_cost,
        score.experiment_id,
    )


def _trial(
    case: dict[str, Any],
    protocol: dict[str, Any],
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
) -> dict[str, object]:
    truth = _truth_graph(case, hypotheses, protocol)
    evidence = DiscoveryEvidence.complete(
        trace_error_budget=int(protocol["domain_caps"]["trace_error_budget"])
    )
    overrides = case.get("evidence_overrides", {})
    if overrides:
        evidence = replace(evidence, **overrides)
    observations: tuple[ExecutedObservation, ...] = ()
    used: tuple[str, ...] = ()
    planner_checks: list[dict[str, object]] = []
    graph_by_id = {graph.graph_id: graph for graph in hypotheses}

    while True:
        report = update_version_space(hypotheses, observations, evidence)
        if report.verdict in {DiscoveryVerdict.UNVERIFIED, DiscoveryVerdict.OUT_OF_HYPOTHESIS}:
            break
        survivors = tuple(graph_by_id[item] for item in report.surviving_graph_ids)
        certificate = select_next_experiment(survivors, experiments, used_ids=used)
        oracle_id, oracle_score = oracle_select_next(survivors, experiments, used)
        production_score = _score_tuple(certificate.selected_score)
        planner_checks.append(
            {
                "surviving_graph_ids": report.surviving_graph_ids,
                "used_experiment_ids": used,
                "production_experiment_id": certificate.selected_experiment_id,
                "production_score": production_score,
                "oracle_experiment_id": oracle_id,
                "oracle_score": oracle_score,
                "match": certificate.selected_experiment_id == oracle_id
                and production_score == oracle_score,
            }
        )
        if certificate.selected_experiment_id is None:
            break
        experiment = next(
            item
            for item in experiments
            if item.experiment_id == certificate.selected_experiment_id
        )
        observations = (
            *observations,
            ExecutedObservation(experiment, predict_trace(truth, experiment)),
        )
        used = (*used, experiment.experiment_id)

    report = update_version_space(hypotheses, observations, evidence)
    truth_known = truth.graph_id in graph_by_id
    signature = relevant_signature(truth)
    false_confident = False
    if report.verdict is DiscoveryVerdict.GRAPH_DISCOVERED:
        false_confident = not truth_known or report.surviving_graph_ids != (truth.graph_id,)
    elif report.verdict in {
        DiscoveryVerdict.PATH_CLASS_DISCOVERED,
        DiscoveryVerdict.EQUIVALENCE_CLASS,
    }:
        false_confident = not truth_known or truth.graph_id not in report.surviving_graph_ids

    control_ids: tuple[str, ...] = ()
    plan_status: str | None = None
    uncontrolled: bool | None = None
    post_control: bool | None = None
    retained_loss: bool | None = None
    if report.verdict in ACTIONABLE and truth_known and signature.edge_paths:
        envelope = build_topology_envelope(report, graph_by_id)
        plan = exact_robust_stabilization_cut(envelope, build_controls(envelope))
        control_ids = plan.control_ids
        plan_status = plan.status.value
        physical = run_control_trial(truth, control_ids)
        uncontrolled = physical.uncontrolled_recurrence
        post_control = physical.post_control_recurrence
        retained_loss = physical.retained_subject_loss

    return {
        "case_id": str(case["case_id"]),
        "truth_graph_id": truth.graph_id,
        "truth_in_hypothesis": truth_known,
        "evidence": asdict(evidence),
        "observations": [
            {
                "experiment_id": item.experiment.experiment_id,
                "trace_bits": item.trace.bits,
            }
            for item in observations
        ],
        "planner_checks": planner_checks,
        "verdict": report.verdict.value,
        "surviving_graph_ids": report.surviving_graph_ids,
        "path_signatures": [asdict(item) for item in report.path_signatures],
        "false_confident": false_confident,
        "control_ids": control_ids,
        "control_plan_status": plan_status,
        "uncontrolled_recurrence": uncontrolled,
        "post_control_recurrence": post_control,
        "retained_subject_loss": retained_loss,
    }


def _summary(trials: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, object]:
    known = [item for item in trials if item["truth_in_hypothesis"]]
    nonsingleton = [
        item
        for item in known
        if item["verdict"] in {
            DiscoveryVerdict.PATH_CLASS_DISCOVERED.value,
            DiscoveryVerdict.EQUIVALENCE_CLASS.value,
        }
    ]
    containment = sum(
        item["truth_graph_id"] in item["surviving_graph_ids"] for item in nonsingleton
    )
    metrics: dict[str, object] = {
        "false_confident_count": sum(bool(item["false_confident"]) for item in trials),
        "exact_unique_graph_recovery_count": sum(
            item["verdict"] == DiscoveryVerdict.GRAPH_DISCOVERED.value
            and tuple(item["surviving_graph_ids"]) == (item["truth_graph_id"],)
            for item in known
        ),
        "path_class_recovery_count": sum(
            item["verdict"] == DiscoveryVerdict.PATH_CLASS_DISCOVERED.value
            and item["truth_graph_id"] in item["surviving_graph_ids"]
            for item in known
        ),
        "true_graph_containment_count": containment,
        "true_graph_containment_rate": containment / len(nonsingleton) if nonsingleton else 1.0,
        "out_of_hypothesis_detection_count": sum(
            item["verdict"] == DiscoveryVerdict.OUT_OF_HYPOTHESIS.value for item in trials
        ),
        "unverified_negative_count": sum(
            item["verdict"] == DiscoveryVerdict.UNVERIFIED.value for item in trials
        ),
        "adaptive_probe_count": sum(len(item["observations"]) for item in trials),
        "exhaustive_probe_count": len(trials) * len(protocol["experiments"]),
        "planner_oracle_mismatch_count": sum(
            not check["match"] for item in trials for check in item["planner_checks"]
        ),
        "post_control_recurrence_count": sum(
            item["post_control_recurrence"] is True for item in trials
        ),
        "retained_subject_loss_count": sum(
            item["retained_subject_loss"] is True for item in trials
        ),
    }
    gates = protocol["gates"]
    passed = (
        cast(int, metrics["false_confident_count"]) <= gates["false_confident_count_max"]
        and cast(int, metrics["exact_unique_graph_recovery_count"])
        >= gates["exact_unique_graph_recovery_count_min"]
        and cast(int, metrics["path_class_recovery_count"])
        >= gates["path_class_recovery_count_min"]
        and cast(float, metrics["true_graph_containment_rate"])
        >= gates["true_graph_containment_rate_min"]
        and cast(int, metrics["out_of_hypothesis_detection_count"])
        >= gates["out_of_hypothesis_detection_count_min"]
        and cast(int, metrics["unverified_negative_count"])
        >= gates["unverified_negative_count_min"]
        and cast(int, metrics["planner_oracle_mismatch_count"])
        <= gates["planner_oracle_mismatch_count_max"]
        and cast(int, metrics["post_control_recurrence_count"])
        <= gates["post_control_recurrence_count_max"]
        and cast(int, metrics["retained_subject_loss_count"])
        <= gates["retained_subject_loss_count_max"]
        and (
            cast(int, metrics["adaptive_probe_count"])
            < cast(int, metrics["exhaustive_probe_count"])
            if gates["adaptive_probe_count_must_be_less_than_exhaustive"]
            else True
        )
    )
    metrics["decision"] = "PASS" if passed else "FAIL"
    return metrics


def compute_result(
    protocol_path: Path, reveal_path: Path
) -> tuple[dict[str, object], list[dict[str, object]]]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    reveal = json.loads(reveal_path.read_text())
    if protocol.get("schema_version") != "erasemap-ghostgraph-v1":
        raise ValueError("unsupported GhostGraph protocol")
    if reveal.get("schema_version") != "erasemap-ghostgraph-reveal-v1":
        raise ValueError("unsupported GhostGraph reveal")
    if core_sha256(protocol["core_files"]) != protocol["core_sha256"]:
        raise ValueError("GhostGraph core hash drift")
    if canonical_sha256(protocol["hypotheses"]) != protocol["hypothesis_catalogue_sha256"]:
        raise ValueError("GhostGraph hypothesis catalogue drift")
    if canonical_sha256(reveal) != protocol["reveal_sha256"]:
        raise ValueError("GhostGraph reveal commitment mismatch")
    cases = reveal.get("cases")
    if not isinstance(cases, list):
        raise ValueError("GhostGraph reveal cases must be an array")
    case_ids = [str(item["case_id"]) for item in cases]
    if case_ids != protocol["case_ids"] or len(case_ids) != len(set(case_ids)):
        raise ValueError("GhostGraph case identity or order drift")
    hypotheses, experiments = _objects(protocol)
    trials = [_trial(case, protocol, hypotheses, experiments) for case in cases]
    result: dict[str, object] = {
        "schema_version": "erasemap-ghostgraph-result-v1",
        "protocol_sha256": "sha256:" + hashlib.sha256(protocol_bytes).hexdigest(),
        "reveal_sha256": canonical_sha256(reveal),
        "core_sha256": protocol["core_sha256"],
        "confirmatory_seed": protocol["confirmatory_seed"],
        "claim_boundary": protocol["claim_boundary"],
        "summary": _summary(trials, protocol),
    }
    return result, trials


def run_experiment(protocol_path: Path, reveal_path: Path, output: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    result, trials = compute_result(protocol_path, reveal_path)
    output.mkdir(parents=True)
    trials_bytes = b"".join(canonical_bytes(item) + b"\n" for item in trials)
    result_bytes = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    (output / "trials.jsonl").write_bytes(trials_bytes)
    (output / "result.json").write_bytes(result_bytes)
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    provenance = {
        "schema_version": "erasemap-ghostgraph-provenance-v1",
        "git_revision": revision,
        "artifacts": {
            "result.json": "sha256:" + hashlib.sha256(result_bytes).hexdigest(),
            "trials.jsonl": "sha256:" + hashlib.sha256(trials_bytes).hexdigest(),
        },
    }
    (output / "PROVENANCE.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmark/ghostgraph-v1.json")
    parser.add_argument("--reveal", type=Path, default=ROOT / "benchmark/ghostgraph-v1-reveal.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/ghostgraph-v1")
    args = parser.parse_args()
    result = run_experiment(args.protocol, args.reveal, args.output)
    print(json.dumps(result["summary"], sort_keys=True))
    return 0 if result["summary"]["decision"] == "PASS" else 1  # type: ignore[index]


if __name__ == "__main__":
    raise SystemExit(main())
