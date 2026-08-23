from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from itertools import combinations

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryExperiment,
    ExecutedObservation,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
    ObservationTrace,
    predict_trace,
    update_version_space,
)
from erasemap.ghostgraph_oracle import (
    oracle_predict_bits,
    oracle_select_next,
    oracle_surviving_ids,
    oracle_verdict,
)
from erasemap.ghostgraph_planner import select_next_experiment

Prediction = Callable[[GraphHypothesis, DiscoveryExperiment], tuple[bool, ...]]


def _graphs() -> tuple[GraphHypothesis, ...]:
    nodes = (GraphNode("middle"), GraphNode("residual"), GraphNode("source"))
    optional = (
        GraphEdge("e0", "source", "middle", "a"),
        GraphEdge("e1", "middle", "residual", "b"),
        GraphEdge("e2", "source", "residual", "c"),
    )
    return tuple(
        GraphHypothesis(
            graph_id=f"g{mask:03b}",
            nodes=nodes,
            edges=tuple(edge for index, edge in enumerate(optional) if mask & (1 << index)),
            initial_node_ids=("source",),
            residual_node_ids=("residual",),
        )
        for mask in range(8)
    )


def _experiments() -> tuple[DiscoveryExperiment, ...]:
    operations = ("a", "b", "c")
    return tuple(
        DiscoveryExperiment(
            experiment_id=f"q{mask:03b}",
            enabled_operation_ids=tuple(
                operation for index, operation in enumerate(operations) if mask & (1 << index)
            ),
            checkpoint_node_ids=("middle", "residual"),
            time_buckets=2,
            declared_cost=mask.bit_count(),
        )
        for mask in range(1, 8)
    )


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def generate_conformance(
    production_predictor: Prediction | None = None,
) -> dict[str, object]:
    graphs = _graphs()
    experiments = _experiments()
    selected_predictor = production_predictor or (
        lambda graph, experiment: predict_trace(graph, experiment).bits
    )
    records: list[dict[str, object]] = []
    mismatch_count = 0
    verdict_counts: dict[str, int] = {}

    for graph in graphs:
        for experiment in experiments:
            production_bits = selected_predictor(graph, experiment)
            oracle = oracle_predict_bits(graph, experiment)
            mismatch = production_bits != oracle
            mismatch_count += int(mismatch)
            records.append(
                {
                    "kind": "prediction",
                    "graph": graph.graph_id,
                    "experiment": experiment.experiment_id,
                    "production": production_bits,
                    "oracle": oracle,
                    "mismatch": mismatch,
                }
            )

            observation = ExecutedObservation(
                experiment,
                ObservationTrace(
                    experiment.checkpoint_node_ids,
                    experiment.time_buckets,
                    oracle,
                ),
            )
            production_report = update_version_space(
                graphs,
                (observation,),
                DiscoveryEvidence.complete(),
            )
            oracle_ids = oracle_surviving_ids(graphs, (observation,), 0)
            expected_verdict = oracle_verdict(graphs, (observation,), 0)
            decode_mismatch = (
                production_report.surviving_graph_ids != oracle_ids
                or production_report.verdict.value != expected_verdict
            )
            mismatch_count += int(decode_mismatch)
            verdict_counts[expected_verdict] = verdict_counts.get(expected_verdict, 0) + 1
            records.append(
                {
                    "kind": "decode",
                    "truth": graph.graph_id,
                    "experiment": experiment.experiment_id,
                    "production_ids": production_report.surviving_graph_ids,
                    "oracle_ids": oracle_ids,
                    "production_verdict": production_report.verdict.value,
                    "oracle_verdict": expected_verdict,
                    "mismatch": decode_mismatch,
                }
            )

    for size in range(1, len(graphs) + 1):
        for subset in combinations(graphs, size):
            production_certificate = select_next_experiment(subset, experiments, used_ids=())
            oracle_id, oracle_score = oracle_select_next(subset, experiments, ())
            production_score = (
                None
                if production_certificate.selected_score is None
                else (
                    production_certificate.selected_score.largest_bucket,
                    production_certificate.selected_score.squared_bucket_sum,
                    production_certificate.selected_score.declared_cost,
                    production_certificate.selected_score.experiment_id,
                )
            )
            mismatch = (
                production_certificate.selected_experiment_id != oracle_id
                or production_score != oracle_score
            )
            mismatch_count += int(mismatch)
            records.append(
                {
                    "kind": "planner",
                    "graphs": tuple(graph.graph_id for graph in subset),
                    "production_id": production_certificate.selected_experiment_id,
                    "oracle_id": oracle_id,
                    "production_score": production_score,
                    "oracle_score": oracle_score,
                    "mismatch": mismatch,
                }
            )

    digest = hashlib.sha256()
    for record in records:
        digest.update(_canonical(record))
        digest.update(b"\n")
    return {
        "schema": "erasemap-ghostgraph-conformance-v1",
        "claim": (
            "production temporal prediction, version filtering, verdicts, and one-step minimax "
            "selection equal an independently structured packed-bit oracle on every listed case"
        ),
        "graphs": len(graphs),
        "experiments": len(experiments),
        "configurations": len(records),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "mismatches": mismatch_count,
        "records_sha256": digest.hexdigest(),
    }
