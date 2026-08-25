from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryReport,
    DiscoveryVerdict,
    ExecutedObservation,
    GraphHypothesis,
    predict_trace,
    relevant_signature,
    update_version_space,
)
from erasemap.ghostgraph_bridge import build_controls, build_topology_envelope
from erasemap.ghostgraph_lab import run_control_trial
from erasemap.ghostgraph_oracle import oracle_select_next
from erasemap.ghostgraph_planner import PlannerCandidate, select_next_experiment
from erasemap.temporal_robust import exact_robust_stabilization_cut
from experiments.run_ghostgraph_v1 import (
    ROOT,
    _objects,
    _truth_graph,
    canonical_bytes,
    canonical_sha256,
)

ACTIONABLE = frozenset(
    {
        DiscoveryVerdict.GRAPH_DISCOVERED,
        DiscoveryVerdict.PATH_CLASS_DISCOVERED,
        DiscoveryVerdict.EQUIVALENCE_CLASS,
    }
)


def _sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(
    protocol_path: Path, reveal_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text())
    reveal = json.loads(reveal_path.read_text())
    if protocol.get("schema_version") != "erasemap-ghostgraph-v2":
        raise ValueError("unsupported GhostGraph v2 protocol")
    if reveal.get("schema_version") != "erasemap-ghostgraph-reveal-v2":
        raise ValueError("unsupported GhostGraph v2 reveal")
    base_path = ROOT / str(protocol["base_protocol"])
    if _sha_file(base_path) != protocol["base_protocol_sha256"]:
        raise ValueError("GhostGraph v2 base protocol drift")
    for relative, expected in protocol["core_file_sha256"].items():
        if _sha_file(ROOT / relative) != expected:
            raise ValueError(f"GhostGraph v2 core source drift: {relative}")
    if canonical_sha256(reveal) != protocol["reveal_sha256"]:
        raise ValueError("GhostGraph v2 reveal commitment mismatch")
    case_ids = [str(item["case_id"]) for item in reveal.get("cases", [])]
    if case_ids != protocol["case_ids"] or len(case_ids) != len(set(case_ids)):
        raise ValueError("GhostGraph v2 case identity or order drift")
    return protocol, reveal, json.loads(base_path.read_text())


def _candidate_record(candidate: PlannerCandidate) -> dict[str, object]:
    return {
        "experiment_id": candidate.experiment_id,
        "partitions": [
            {"trace_bits": item.trace_bits, "graph_ids": item.graph_ids}
            for item in candidate.partitions
        ],
        "score": asdict(candidate.score),
        "separates": candidate.separates,
    }


def _flat_partitions(
    survivors: tuple[GraphHypothesis, ...], experiments: tuple[Any, ...], used: tuple[str, ...]
) -> list[dict[str, object]]:
    records = []
    for experiment in experiments:
        if experiment.experiment_id in used:
            continue
        buckets: dict[bool, list[str]] = {}
        for graph in survivors:
            bit = any(predict_trace(graph, experiment).bits)
            buckets.setdefault(bit, []).append(graph.graph_id)
        sizes = tuple(len(item) for item in buckets.values())
        records.append(
            {
                "experiment_id": experiment.experiment_id,
                "partitions": [
                    {"trace_bits": [bit], "graph_ids": ids}
                    for bit, ids in sorted(buckets.items())
                ],
                "score": {
                    "largest_bucket": max(sizes),
                    "squared_bucket_sum": sum(size * size for size in sizes),
                    "declared_cost": experiment.declared_cost,
                    "experiment_id": experiment.experiment_id,
                },
                "separates": len(buckets) > 1,
            }
        )
    return records


def _flat_report(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
    evidence: DiscoveryEvidence,
) -> DiscoveryReport:
    if not evidence.valid:
        return update_version_space(hypotheses, (), evidence)
    survivors = tuple(
        graph
        for graph in hypotheses
        if all(
            any(predict_trace(graph, item.experiment).bits) == any(item.trace.bits)
            for item in observations
        )
    )
    if not survivors:
        exact = update_version_space(hypotheses, observations, evidence)
        return replace(exact, verdict=DiscoveryVerdict.OUT_OF_HYPOTHESIS)
    ids = tuple(item.graph_id for item in survivors)
    signatures = tuple(sorted({relevant_signature(item) for item in survivors}))
    if observations and not any(any(item.trace.bits) for item in observations):
        verdict = DiscoveryVerdict.NO_OBSERVED_RECURRENCE
    elif len(survivors) == 1:
        verdict = DiscoveryVerdict.GRAPH_DISCOVERED
    elif len(signatures) == 1:
        verdict = DiscoveryVerdict.PATH_CLASS_DISCOVERED
    else:
        verdict = DiscoveryVerdict.EQUIVALENCE_CLASS
    return DiscoveryReport(verdict, ids, signatures, evidence, None)


def _choose(
    strategy: str,
    survivors: tuple[GraphHypothesis, ...],
    experiments: tuple[Any, ...],
    used: tuple[str, ...],
    generator: random.Random,
) -> tuple[str | None, list[dict[str, object]], bool | None]:
    if strategy == "flat-erasure-tomography":
        candidates = _flat_partitions(survivors, experiments, used)
        separating = [item for item in candidates if item["separates"]]
        selected = min(
            separating,
            key=lambda item: (
                cast(dict[str, Any], item["score"])["largest_bucket"],
                cast(dict[str, Any], item["score"])["squared_bucket_sum"],
                cast(dict[str, Any], item["score"])["declared_cost"],
                item["experiment_id"],
            ),
            default=None,
        )
        return None if selected is None else str(selected["experiment_id"]), candidates, None
    certificate = select_next_experiment(survivors, experiments, used_ids=used)
    candidates = [_candidate_record(item) for item in certificate.candidates]
    oracle_id, oracle_score = oracle_select_next(survivors, experiments, used)
    selected_id: str | None
    if strategy == "active-minimax":
        selected_id = certificate.selected_experiment_id
        score = certificate.selected_score
        production_score = None if score is None else (
            score.largest_bucket,
            score.squared_bucket_sum,
            score.declared_cost,
            score.experiment_id,
        )
        matches = selected_id == oracle_id and production_score == oracle_score
        return selected_id, candidates, matches
    separating_candidates = [item for item in certificate.candidates if item.separates]
    if strategy == "frozen-random-feasible":
        selected_id = (
            generator.choice(
                sorted(item.experiment_id for item in separating_candidates)
            )
            if separating_candidates
            else None
        )
    elif strategy == "greedy-separated-pairs":
        selected_id = (
            min(
                separating_candidates,
                key=lambda item: (
                    item.score.squared_bucket_sum,
                    item.score.declared_cost,
                    item.experiment_id,
                ),
            ).experiment_id
            if separating_candidates
            else None
        )
    else:
        raise ValueError(f"unsupported adaptive GhostGraph strategy: {strategy}")
    return selected_id, candidates, None


def _run_case(
    strategy: str,
    case: dict[str, Any],
    protocol: dict[str, Any],
    base: dict[str, Any],
    generator: random.Random,
) -> dict[str, object]:
    hypotheses, experiments = _objects(base)
    truth = _truth_graph(case, hypotheses, base)
    graph_by_id = {item.graph_id: item for item in hypotheses}
    evidence = DiscoveryEvidence.complete()
    if case.get("evidence_overrides"):
        evidence = replace(evidence, **case["evidence_overrides"])
    observations: tuple[ExecutedObservation, ...] = ()
    used: tuple[str, ...] = ()
    certificates: list[dict[str, object]] = []
    stopping_reason = ""

    if strategy == "passive-declared-lineage" or not evidence.valid:
        stopping_reason = "PASSIVE_NO_QUERY" if evidence.valid else "INVALID_EVIDENCE"
    elif strategy == "nonadaptive-exhaustive":
        for experiment in experiments:
            before = tuple(item.graph_id for item in hypotheses)
            observation = ExecutedObservation(experiment, predict_trace(truth, experiment))
            observations = (*observations, observation)
            report = update_version_space(hypotheses, observations, evidence)
            certificates.append(
                {
                    "version_space_before": before,
                    "candidates": [],
                    "selected_experiment_id": experiment.experiment_id,
                    "oracle_match": None,
                    "observed_trace_bits": observation.trace.bits,
                    "version_space_after": report.surviving_graph_ids,
                }
            )
        stopping_reason = "FROZEN_EXHAUSTIVE_COMPLETE"
    else:
        while True:
            report = (
                _flat_report(hypotheses, observations, evidence)
                if strategy == "flat-erasure-tomography"
                else update_version_space(hypotheses, observations, evidence)
            )
            if report.verdict is DiscoveryVerdict.OUT_OF_HYPOTHESIS:
                stopping_reason = "EMPTY_VERSION_SPACE"
                break
            survivors = tuple(graph_by_id[item] for item in report.surviving_graph_ids)
            selected, candidates, oracle_match = _choose(
                strategy, survivors, experiments, used, generator
            )
            certificate: dict[str, object] = {
                "version_space_before": report.surviving_graph_ids,
                "candidates": candidates,
                "selected_experiment_id": selected,
                "oracle_match": oracle_match,
            }
            if selected is None:
                certificate["observed_trace_bits"] = None
                certificate["version_space_after"] = report.surviving_graph_ids
                certificates.append(certificate)
                stopping_reason = "NO_UNUSED_SEPARATING_EXPERIMENT"
                break
            experiment = next(item for item in experiments if item.experiment_id == selected)
            observation = ExecutedObservation(experiment, predict_trace(truth, experiment))
            observations = (*observations, observation)
            used = (*used, selected)
            after = (
                _flat_report(hypotheses, observations, evidence)
                if strategy == "flat-erasure-tomography"
                else update_version_space(hypotheses, observations, evidence)
            )
            certificate["observed_trace_bits"] = observation.trace.bits
            certificate["version_space_after"] = after.surviving_graph_ids
            certificates.append(certificate)

    report = (
        _flat_report(hypotheses, observations, evidence)
        if strategy == "flat-erasure-tomography"
        else update_version_space(hypotheses, observations, evidence)
    )
    truth_known = truth.graph_id in graph_by_id
    false_confident = report.verdict in ACTIONABLE and (
        not truth_known or truth.graph_id not in report.surviving_graph_ids
    )
    control_ids: tuple[str, ...] = ()
    post_control: bool | None = None
    retained_loss: bool | None = None
    if (
        strategy == "active-minimax"
        and report.verdict in ACTIONABLE
        and truth_known
        and relevant_signature(truth).edge_paths
    ):
        envelope = build_topology_envelope(report, graph_by_id)
        plan = exact_robust_stabilization_cut(envelope, build_controls(envelope))
        control_ids = plan.control_ids
        physical = run_control_trial(truth, control_ids)
        post_control = physical.post_control_recurrence
        retained_loss = physical.retained_subject_loss
    return {
        "case_id": case["case_id"],
        "truth_graph_id": truth.graph_id,
        "truth_in_hypothesis": truth_known,
        "verdict": report.verdict.value,
        "surviving_graph_ids": report.surviving_graph_ids,
        "path_signatures": [asdict(item) for item in report.path_signatures],
        "false_confident": false_confident,
        "probe_count": len(observations),
        "certificates": certificates,
        "stopping_reason": stopping_reason,
        "control_ids": control_ids,
        "post_control_recurrence": post_control,
        "retained_subject_loss": retained_loss,
    }


def _metrics(strategy: str, trials: list[dict[str, Any]]) -> dict[str, object]:
    known = [item for item in trials if item["truth_in_hypothesis"]]
    nonsingleton = [
        item
        for item in known
        if item["verdict"]
        in {DiscoveryVerdict.PATH_CLASS_DISCOVERED.value, DiscoveryVerdict.EQUIVALENCE_CLASS.value}
    ]
    contained = sum(item["truth_graph_id"] in item["surviving_graph_ids"] for item in nonsingleton)
    return {
        "strategy_id": strategy,
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
        "true_graph_containment_rate": contained / len(nonsingleton) if nonsingleton else 1.0,
        "out_of_hypothesis_detection_count": sum(
            item["verdict"] == DiscoveryVerdict.OUT_OF_HYPOTHESIS.value for item in trials
        ),
        "unverified_negative_count": sum(
            item["verdict"] == DiscoveryVerdict.UNVERIFIED.value for item in trials
        ),
        "probe_count": sum(int(item["probe_count"]) for item in trials),
        "planner_oracle_mismatch_count": sum(
            check["oracle_match"] is False
            for item in trials
            for check in item["certificates"]
        ),
        "post_control_recurrence_count": sum(
            item["post_control_recurrence"] is True for item in trials
        ),
        "retained_subject_loss_count": sum(
            item["retained_subject_loss"] is True for item in trials
        ),
    }


def compute_result(
    protocol_path: Path, reveal_path: Path
) -> tuple[dict[str, object], list[dict[str, object]]]:
    protocol, reveal, base = _validate(protocol_path, reveal_path)
    all_trials: list[dict[str, object]] = []
    strategy_metrics = []
    for strategy_item in protocol["strategies"]:
        strategy = str(strategy_item["strategy_id"])
        generator = random.Random(int(protocol["random_seed"]))
        trials = [
            _run_case(strategy, case, protocol, base, generator)
            for case in reveal["cases"]
        ]
        all_trials.extend({"strategy_id": strategy, **item} for item in trials)
        strategy_metrics.append(_metrics(strategy, trials))
    by_id = {str(item["strategy_id"]): item for item in strategy_metrics}
    active = by_id["active-minimax"]
    exhaustive = by_id["nonadaptive-exhaustive"]
    gates = protocol["primary_gates"]
    passed = (
        active["false_confident_count"] <= gates["active_minimax_false_confident_count_max"]
        and active["exact_unique_graph_recovery_count"]
        >= gates["active_minimax_exact_unique_graph_recovery_count_min"]
        and active["path_class_recovery_count"]
        >= gates["active_minimax_path_class_recovery_count_min"]
        and active["out_of_hypothesis_detection_count"]
        >= gates["active_minimax_out_of_hypothesis_detection_count_min"]
        and active["unverified_negative_count"]
        >= gates["active_minimax_unverified_negative_count_min"]
        and active["planner_oracle_mismatch_count"]
        <= gates["active_minimax_planner_oracle_mismatch_count_max"]
        and active["post_control_recurrence_count"]
        <= gates["active_minimax_post_control_recurrence_count_max"]
        and active["retained_subject_loss_count"]
        <= gates["active_minimax_retained_subject_loss_count_max"]
        and (
            cast(int, active["probe_count"]) < cast(int, exhaustive["probe_count"])
            if gates["active_minimax_probe_count_less_than_exhaustive"]
            else True
        )
    )
    result = {
        "schema_version": "erasemap-ghostgraph-result-v2",
        "protocol_sha256": _sha_file(protocol_path),
        "reveal_sha256": canonical_sha256(reveal),
        "base_protocol_sha256": protocol["base_protocol_sha256"],
        "strategy_metrics": strategy_metrics,
        "decision": "PASS" if passed else "FAIL",
        "claim_boundary": protocol["claim_boundary"],
    }
    return result, all_trials


def run_experiment(protocol_path: Path, reveal_path: Path, output: Path) -> dict[str, object]:
    if output.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    result, trials = compute_result(protocol_path, reveal_path)
    output.mkdir(parents=True)
    result_bytes = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    trials_bytes = b"".join(canonical_bytes(item) + b"\n" for item in trials)
    (output / "result.json").write_bytes(result_bytes)
    (output / "trials.jsonl").write_bytes(trials_bytes)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    provenance = {
        "schema_version": "erasemap-ghostgraph-provenance-v2",
        "git_revision": revision,
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
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmark/ghostgraph-v2.json")
    parser.add_argument("--reveal", type=Path, default=ROOT / "benchmark/ghostgraph-v2-reveal.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/ghostgraph-v2")
    args = parser.parse_args()
    result = run_experiment(args.protocol, args.reveal, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
