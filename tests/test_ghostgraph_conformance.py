from __future__ import annotations

import inspect
import json
from pathlib import Path

from erasemap.ghostgraph import (
    DiscoveryExperiment,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
    predict_trace,
)
from erasemap.ghostgraph_conformance import generate_conformance
from erasemap.ghostgraph_oracle import oracle_predict_bits, oracle_select_next


def _graph() -> GraphHypothesis:
    return GraphHypothesis(
        graph_id="g",
        nodes=(GraphNode("middle"), GraphNode("residual"), GraphNode("source")),
        edges=(
            GraphEdge("e1", "source", "middle", "restore"),
            GraphEdge("e2", "middle", "residual", "sync"),
        ),
        initial_node_ids=("source",),
        residual_node_ids=("residual",),
    )


def _experiment() -> DiscoveryExperiment:
    return DiscoveryExperiment(
        experiment_id="probe",
        enabled_operation_ids=("restore", "sync"),
        checkpoint_node_ids=("middle", "residual"),
        time_buckets=2,
        declared_cost=1,
    )


def test_oracle_does_not_import_production_scientific_functions() -> None:
    source = inspect.getsource(__import__("erasemap.ghostgraph_oracle", fromlist=["*"]))

    assert "predict_trace" not in source
    assert "update_version_space" not in source
    assert "select_next_experiment" not in source
    assert "relevant_signature" not in source


def test_packed_oracle_matches_known_multihop_trace() -> None:
    graph = _graph()
    experiment = _experiment()

    assert oracle_predict_bits(graph, experiment) == predict_trace(graph, experiment).bits


def test_oracle_planner_returns_expected_minimax_query() -> None:
    empty = GraphHypothesis(
        graph_id="empty",
        nodes=_graph().nodes,
        edges=(),
        initial_node_ids=("source",),
        residual_node_ids=("residual",),
    )

    selected_id, score = oracle_select_next((empty, _graph()), (_experiment(),), ())

    assert selected_id == "probe"
    assert score == (1, 2, 1, "probe")


def test_conformance_detects_deliberately_wrong_production_prediction() -> None:
    result = generate_conformance(
        production_predictor=lambda graph, experiment: tuple(
            not bit for bit in predict_trace(graph, experiment).bits
        )
    )

    assert result["mismatches"] > 0


def test_frozen_conformance_matches_production_and_oracle() -> None:
    result = generate_conformance()
    frozen = json.loads(Path("formal/ghostgraph-conformance-v1.json").read_text())

    assert result == frozen
    assert result["mismatches"] == 0
    assert result["configurations"] > 300
    assert len(str(result["records_sha256"])) == 64
