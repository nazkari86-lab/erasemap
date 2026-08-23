from __future__ import annotations

import pytest

from erasemap.ghostgraph import (
    DiscoveryExperiment,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
)
from erasemap.ghostgraph_planner import PlannerScore, select_next_experiment


def _graph(graph_id: str, operations: tuple[str, ...]) -> GraphHypothesis:
    nodes = (GraphNode("backup"), GraphNode("vector"))
    edges = tuple(
        GraphEdge(
            edge_id=f"edge-{operation}",
            source_id="backup",
            target_id="vector",
            operation_id=operation,
        )
        for operation in operations
    )
    return GraphHypothesis(
        graph_id=graph_id,
        nodes=nodes,
        edges=edges,
        initial_node_ids=("backup",),
        residual_node_ids=("vector",),
    )


def _experiment(experiment_id: str, operations: tuple[str, ...], cost: int) -> DiscoveryExperiment:
    return DiscoveryExperiment(
        experiment_id=experiment_id,
        enabled_operation_ids=operations,
        checkpoint_node_ids=("vector",),
        time_buckets=1,
        declared_cost=cost,
    )


def _hypotheses() -> tuple[GraphHypothesis, ...]:
    return (
        _graph("g0", ()),
        _graph("g1", ("a",)),
        _graph("g2", ("b",)),
        _graph("g3", ("a", "b")),
    )


def test_selects_smallest_worst_case_partition() -> None:
    experiments = (
        _experiment("balanced", ("a",), 3),
        _experiment("broad", ("a", "b"), 1),
    )

    certificate = select_next_experiment(_hypotheses(), experiments, used_ids=())

    assert certificate.selected_experiment_id == "balanced"
    assert certificate.selected_score == PlannerScore(2, 8, 3, "balanced")
    balanced = certificate.candidates[0]
    assert balanced.experiment_id == "balanced"
    assert tuple(partition.graph_ids for partition in balanced.partitions) == (
        ("g0", "g2"),
        ("g1", "g3"),
    )


def test_cost_and_id_break_exact_partition_ties() -> None:
    experiments = (
        _experiment("expensive", ("a",), 4),
        _experiment("z-cheap", ("a",), 2),
        _experiment("a-cheap", ("a",), 2),
    )

    certificate = select_next_experiment(_hypotheses(), experiments, used_ids=())

    assert certificate.selected_experiment_id == "a-cheap"
    assert certificate.selected_score == PlannerScore(2, 8, 2, "a-cheap")


def test_returns_no_selection_when_graphs_are_not_separable() -> None:
    equivalent = (_graph("g0", ()), _graph("g1", ()))
    experiments = (_experiment("probe", ("a",), 1),)

    certificate = select_next_experiment(equivalent, experiments, used_ids=())

    assert certificate.selected_experiment_id is None
    assert certificate.selected_score is None
    assert certificate.candidates[0].separates is False


def test_used_experiment_is_excluded_from_candidates() -> None:
    experiments = (
        _experiment("a-probe", ("a",), 1),
        _experiment("b-probe", ("b",), 1),
    )

    certificate = select_next_experiment(
        _hypotheses(),
        experiments,
        used_ids=("a-probe",),
    )

    assert tuple(candidate.experiment_id for candidate in certificate.candidates) == ("b-probe",)
    assert certificate.selected_experiment_id == "b-probe"


def test_certificate_is_invariant_to_input_order() -> None:
    hypotheses = _hypotheses()
    experiments = (
        _experiment("balanced", ("a",), 3),
        _experiment("broad", ("a", "b"), 1),
    )

    forward = select_next_experiment(hypotheses, experiments, used_ids=())
    reverse = select_next_experiment(
        tuple(reversed(hypotheses)),
        tuple(reversed(experiments)),
        used_ids=(),
    )

    assert forward == reverse


def test_rejects_duplicate_ids_unknown_used_ids_and_experiment_overflow() -> None:
    probe = _experiment("probe", ("a",), 1)
    with pytest.raises(ValueError, match="experiment IDs must be unique"):
        select_next_experiment(_hypotheses(), (probe, probe), used_ids=())
    with pytest.raises(ValueError, match="unknown used experiment"):
        select_next_experiment(_hypotheses(), (probe,), used_ids=("missing",))
    too_many = tuple(
        _experiment(f"probe-{index:02d}", (), 1)
        for index in range(33)
    )
    with pytest.raises(ValueError, match="at most 32 experiments"):
        select_next_experiment(_hypotheses(), too_many, used_ids=())


def test_partition_contains_every_graph_exactly_once() -> None:
    experiment = _experiment("probe", ("a",), 1)

    certificate = select_next_experiment(_hypotheses(), (experiment,), used_ids=())

    flattened = tuple(
        graph_id
        for partition in certificate.candidates[0].partitions
        for graph_id in partition.graph_ids
    )
    assert sorted(flattened) == ["g0", "g1", "g2", "g3"]
