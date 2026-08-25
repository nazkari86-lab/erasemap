from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryVerdict,
    ExecutedObservation,
    GraphHypothesis,
    ObservationTrace,
    update_version_space,
)
from erasemap.ghostgraph_bridge import build_controls, build_topology_envelope
from erasemap.ghostgraph_oracle import oracle_select_next
from erasemap.ghostgraph_planner import select_next_experiment
from erasemap.temporal_robust import exact_robust_stabilization_cut
from experiments.ghostgraph_services import GhostGraphServices
from experiments.run_ghostgraph_v1 import (
    ROOT,
    _objects,
    _truth_graph,
    canonical_bytes,
    canonical_sha256,
)


def _sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_inputs(
    protocol_path: Path, reveal_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text())
    reveal = json.loads(reveal_path.read_text())
    if protocol.get("schema_version") != "erasemap-ghostgraph-live-v2":
        raise ValueError("unsupported GhostGraph live v2 protocol")
    if reveal.get("schema_version") != "erasemap-ghostgraph-live-reveal-v2":
        raise ValueError("unsupported GhostGraph live v2 reveal")
    if canonical_sha256(reveal) != protocol["reveal_sha256"]:
        raise ValueError("GhostGraph live v2 reveal commitment mismatch")
    case_ids = [str(item["case_id"]) for item in reveal.get("cases", [])]
    if case_ids != protocol["case_ids"] or len(case_ids) != len(set(case_ids)):
        raise ValueError("GhostGraph live v2 case identity or order drift")
    return protocol, reveal


def _control_graph(graph: GraphHypothesis, control_ids: tuple[str, ...]) -> GraphHypothesis:
    guarded = frozenset(item.removeprefix("guard:") for item in control_ids)
    return GraphHypothesis(
        graph_id=graph.graph_id + "-controlled",
        nodes=graph.nodes,
        edges=tuple(item for item in graph.edges if item.edge_id not in guarded),
        initial_node_ids=graph.initial_node_ids,
        residual_node_ids=graph.residual_node_ids,
    )


def _run_live_case(
    services: GhostGraphServices,
    case: dict[str, Any],
    protocol: dict[str, Any],
    case_index: int,
) -> dict[str, object]:
    hypotheses, experiments = _objects(protocol)
    truth = _truth_graph(case, hypotheses, protocol)
    graph_by_id = {item.graph_id: item for item in hypotheses}
    evidence = DiscoveryEvidence.complete()
    observations: tuple[ExecutedObservation, ...] = ()
    used: tuple[str, ...] = ()
    steps: list[dict[str, object]] = []
    while True:
        report = update_version_space(hypotheses, observations, evidence)
        if report.verdict is DiscoveryVerdict.OUT_OF_HYPOTHESIS:
            stopping_reason = "EMPTY_VERSION_SPACE"
            break
        survivors = tuple(graph_by_id[item] for item in report.surviving_graph_ids)
        certificate = select_next_experiment(survivors, experiments, used_ids=used)
        oracle_id, oracle_score = oracle_select_next(survivors, experiments, used)
        score = certificate.selected_score
        production_score = None if score is None else (
            score.largest_bucket,
            score.squared_bucket_sum,
            score.declared_cost,
            score.experiment_id,
        )
        selected = certificate.selected_experiment_id
        if selected is None:
            steps.append(
                {
                    "version_space_before": report.surviving_graph_ids,
                    "selected_experiment_id": None,
                    "oracle_match": oracle_id is None and oracle_score is None,
                    "trace_bits": None,
                    "native_observations": [],
                    "version_space_after": report.surviving_graph_ids,
                }
            )
            stopping_reason = "NO_UNUSED_SEPARATING_EXPERIMENT"
            break
        experiment = next(item for item in experiments if item.experiment_id == selected)
        subject = f"gg-{protocol['confirmatory_seed']}-{case_index}-{selected}"
        bits, native = services.execute_trace(truth, experiment, subject)
        observation = ExecutedObservation(
            experiment,
            ObservationTrace(experiment.checkpoint_node_ids, experiment.time_buckets, bits),
        )
        observations = (*observations, observation)
        used = (*used, selected)
        after = update_version_space(hypotheses, observations, evidence)
        steps.append(
            {
                "version_space_before": report.surviving_graph_ids,
                "selected_experiment_id": selected,
                "oracle_match": selected == oracle_id and production_score == oracle_score,
                "trace_bits": bits,
                "native_observations": [asdict(item) for item in native],
                "version_space_after": after.surviving_graph_ids,
            }
        )
    report = update_version_space(hypotheses, observations, evidence)
    truth_known = truth.graph_id in graph_by_id
    actionable = report.verdict in {
        DiscoveryVerdict.GRAPH_DISCOVERED,
        DiscoveryVerdict.PATH_CLASS_DISCOVERED,
        DiscoveryVerdict.EQUIVALENCE_CLASS,
    }
    false_confident = actionable and (
        not truth_known or truth.graph_id not in report.surviving_graph_ids
    )
    control_ids: tuple[str, ...] = ()
    uncontrolled_recurrence: bool | None = None
    post_control_recurrence: bool | None = None
    retained_loss: bool | None = None
    if actionable and truth_known:
        envelope = build_topology_envelope(report, graph_by_id)
        plan = exact_robust_stabilization_cut(envelope, build_controls(envelope))
        control_ids = plan.control_ids
        all_experiment = next(item for item in experiments if item.experiment_id == "q-all")
        uncontrolled_subject = f"control-unchecked-{case_index}"
        uncontrolled_bits, _ = services.execute_trace(
            truth, all_experiment, uncontrolled_subject
        )
        uncontrolled_recurrence = uncontrolled_bits[-1]
        controlled_subject = f"control-guarded-{case_index}"
        controlled_bits, _ = services.execute_trace(
            _control_graph(truth, control_ids), all_experiment, controlled_subject
        )
        post_control_recurrence = controlled_bits[-1]
        retained_loss = not services.retained_present_everywhere("ghostgraph-retained")
    return {
        "case_id": case["case_id"],
        "truth_graph_id": truth.graph_id,
        "truth_in_hypothesis": truth_known,
        "steps": steps,
        "stopping_reason": stopping_reason,
        "verdict": report.verdict.value,
        "surviving_graph_ids": report.surviving_graph_ids,
        "false_confident": false_confident,
        "control_ids": control_ids,
        "uncontrolled_recurrence": uncontrolled_recurrence,
        "post_control_recurrence": post_control_recurrence,
        "retained_subject_loss": retained_loss,
    }


def score_records(
    protocol: dict[str, Any], reveal: dict[str, Any], trials: list[dict[str, Any]]
) -> dict[str, object]:
    if [item["case_id"] for item in trials] != protocol["case_ids"]:
        raise ValueError("GhostGraph live trial order drift")
    hypotheses, experiments = _objects(protocol)
    experiment_by_id = {item.experiment_id: item for item in experiments}
    graph_by_id = {item.graph_id: item for item in hypotheses}
    for case, trial in zip(reveal["cases"], trials, strict=True):
        observations: tuple[ExecutedObservation, ...] = ()
        used: tuple[str, ...] = ()
        for step in trial["steps"]:
            report = update_version_space(
                hypotheses, observations, DiscoveryEvidence.complete()
            )
            selected = step["selected_experiment_id"]
            survivors = tuple(graph_by_id[item] for item in report.surviving_graph_ids)
            certificate = select_next_experiment(survivors, experiments, used_ids=used)
            oracle_id, oracle_score = oracle_select_next(survivors, experiments, used)
            score = certificate.selected_score
            production_score = None if score is None else (
                score.largest_bucket,
                score.squared_bucket_sum,
                score.declared_cost,
                score.experiment_id,
            )
            expected_match = (
                selected == certificate.selected_experiment_id == oracle_id
                and production_score == oracle_score
            )
            if step["version_space_before"] != list(report.surviving_graph_ids):
                raise ValueError("GhostGraph live version-space-before mismatch")
            if bool(step["oracle_match"]) != expected_match:
                raise ValueError("GhostGraph live planner/oracle record mismatch")
            if selected is None:
                continue
            experiment = experiment_by_id[str(selected)]
            bits = tuple(bool(item) for item in step["trace_bits"])
            native_bits = tuple(
                bool(item["present"]) for item in step["native_observations"]
            )
            if bits != native_bits:
                raise ValueError("GhostGraph live trace differs from native observations")
            observation = ExecutedObservation(
                experiment,
                ObservationTrace(experiment.checkpoint_node_ids, experiment.time_buckets, bits),
            )
            observations = (*observations, observation)
            used = (*used, str(selected))
            after = update_version_space(
                hypotheses, observations, DiscoveryEvidence.complete()
            )
            if step["version_space_after"] != list(after.surviving_graph_ids):
                raise ValueError("GhostGraph live version-space-after mismatch")
        final = update_version_space(hypotheses, observations, DiscoveryEvidence.complete())
        if trial["verdict"] != final.verdict.value:
            raise ValueError("GhostGraph live final verdict mismatch")
        if trial["surviving_graph_ids"] != list(final.surviving_graph_ids):
            raise ValueError("GhostGraph live final survivor mismatch")
        truth = _truth_graph(case, hypotheses, protocol)
        if trial["truth_graph_id"] != truth.graph_id:
            raise ValueError("GhostGraph live truth reveal mismatch")
    metrics = {
        "case_count": len(trials),
        "false_confident_count": sum(bool(item["false_confident"]) for item in trials),
        "exact_or_path_class_recovery_count": sum(
            item["verdict"]
            in {
                DiscoveryVerdict.GRAPH_DISCOVERED.value,
                DiscoveryVerdict.PATH_CLASS_DISCOVERED.value,
            }
            and item["truth_graph_id"] in item["surviving_graph_ids"]
            for item in trials
            if item["truth_in_hypothesis"]
        ),
        "out_of_hypothesis_detection_count": sum(
            item["verdict"] == DiscoveryVerdict.OUT_OF_HYPOTHESIS.value for item in trials
        ),
        "safe_no_recurrence_count": sum(
            item["verdict"] == DiscoveryVerdict.NO_OBSERVED_RECURRENCE.value for item in trials
        ),
        "planner_oracle_mismatch_count": sum(
            not bool(step["oracle_match"]) for item in trials for step in item["steps"]
        ),
        "post_control_recurrence_count": sum(
            item["post_control_recurrence"] is True for item in trials
        ),
        "retained_subject_loss_count": sum(
            item["retained_subject_loss"] is True for item in trials
        ),
        "cleanup_failure_count": 0,
        "probe_count": sum(
            step["selected_experiment_id"] is not None
            for item in trials
            for step in item["steps"]
        ),
    }
    gates = protocol["gates"]
    passed = (
        metrics["false_confident_count"] <= gates["false_confident_count_max"]
        and metrics["exact_or_path_class_recovery_count"]
        >= gates["exact_or_path_class_recovery_count_min"]
        and metrics["out_of_hypothesis_detection_count"]
        >= gates["out_of_hypothesis_detection_count_min"]
        and metrics["safe_no_recurrence_count"] >= gates["safe_no_recurrence_count_min"]
        and metrics["planner_oracle_mismatch_count"]
        <= gates["planner_oracle_mismatch_count_max"]
        and metrics["post_control_recurrence_count"]
        <= gates["post_control_recurrence_count_max"]
        and metrics["retained_subject_loss_count"]
        <= gates["retained_subject_loss_count_max"]
    )
    return {
        "schema_version": "erasemap-ghostgraph-live-result-v2",
        "decision": "PASS" if passed else "FAIL",
        "metrics": metrics,
        "images": protocol["images"],
        "claim_boundary": protocol["claim_boundary"],
    }


def run_live(protocol_path: Path, reveal_path: Path, output: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    protocol, reveal = _validate_inputs(protocol_path, reveal_path)
    service_root = output.parent / ".ghostgraph-live-services"
    services = GhostGraphServices(
        dict(protocol["images"]),
        service_root,
        timeout=int(protocol["observation_timeout_seconds"]),
    )
    cleanup_complete = False
    try:
        services.start()
        services.seed_retained("ghostgraph-retained")
        trials = [
            _run_live_case(services, case, protocol, index)
            for index, case in enumerate(reveal["cases"])
        ]
    finally:
        services.stop()
        cleanup_complete = services.cleanup_complete()
    if not cleanup_complete:
        raise RuntimeError("GhostGraph live container cleanup failed")
    result = score_records(protocol, reveal, trials)
    output.mkdir(parents=True)
    trials_bytes = b"".join(canonical_bytes(item) + b"\n" for item in trials)
    result_bytes = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    (output / "trials.jsonl").write_bytes(trials_bytes)
    (output / "result.json").write_bytes(result_bytes)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    provenance = {
        "schema_version": "erasemap-ghostgraph-live-provenance-v2",
        "git_revision": revision,
        "protocol_sha256": _sha_file(protocol_path),
        "reveal_sha256": canonical_sha256(reveal),
        "artifacts": {
            "result.json": _sha_file(output / "result.json"),
            "trials.jsonl": _sha_file(output / "trials.jsonl"),
        },
    }
    (output / "PROVENANCE.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol", type=Path, default=ROOT / "benchmark/ghostgraph-live-v2.json"
    )
    parser.add_argument(
        "--reveal", type=Path, default=ROOT / "benchmark/ghostgraph-live-v2-reveal.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/ghostgraph-live-v2"
    )
    args = parser.parse_args()
    result = run_live(args.protocol, args.reveal, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
