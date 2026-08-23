from __future__ import annotations

from dataclasses import replace

import pytest

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryExperiment,
    DiscoveryVerdict,
    ExecutedObservation,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
    ObservationTrace,
    predict_trace,
    relevant_signature,
    update_version_space,
)


def _node(node_id: str) -> GraphNode:
    return GraphNode(node_id=node_id)


def _graph(
    graph_id: str,
    edges: tuple[GraphEdge, ...],
    *,
    extra_nodes: tuple[str, ...] = (),
) -> GraphHypothesis:
    node_ids = tuple(sorted({"backup", "database", "vector", "worker", *extra_nodes}))
    return GraphHypothesis(
        graph_id=graph_id,
        nodes=tuple(_node(node_id) for node_id in node_ids),
        edges=tuple(sorted(edges, key=lambda edge: edge.edge_id)),
        initial_node_ids=("backup",),
        residual_node_ids=("vector",),
    )


def _edge(edge_id: str, source: str, target: str, operation: str) -> GraphEdge:
    return GraphEdge(
        edge_id=edge_id,
        source_id=source,
        target_id=target,
        operation_id=operation,
    )


def _experiment(*operations: str) -> DiscoveryExperiment:
    return DiscoveryExperiment(
        experiment_id="probe",
        enabled_operation_ids=tuple(sorted(operations)),
        checkpoint_node_ids=("database", "vector"),
        time_buckets=3,
        declared_cost=2,
    )


def _multihop(graph_id: str = "multihop") -> GraphHypothesis:
    return _graph(
        graph_id,
        (
            _edge("e1", "backup", "database", "restore"),
            _edge("e2", "database", "worker", "sync"),
            _edge("e3", "worker", "vector", "index"),
        ),
    )


def test_predicts_multihop_recurrence_trace() -> None:
    trace = predict_trace(_multihop(), _experiment("restore", "sync", "index"))

    assert trace.bits == (True, False, True, False, True, True)


def test_disabled_operation_blocks_downstream_recurrence() -> None:
    trace = predict_trace(_multihop(), _experiment("restore", "index"))

    assert trace.bits == (True, False, True, False, True, False)


def test_rejects_noncanonical_nodes_edges_and_unknown_endpoints() -> None:
    with pytest.raises(ValueError, match="nodes must be sorted"):
        GraphHypothesis(
            graph_id="bad",
            nodes=(_node("worker"), _node("backup")),
            edges=(),
            initial_node_ids=("backup",),
            residual_node_ids=("worker",),
        )

    with pytest.raises(ValueError, match="edges must be sorted"):
        GraphHypothesis(
            graph_id="bad-edges",
            nodes=tuple(_node(node_id) for node_id in ("backup", "database", "vector", "worker")),
            edges=(
                _edge("z", "backup", "database", "restore"),
                _edge("a", "database", "vector", "index"),
            ),
            initial_node_ids=("backup",),
            residual_node_ids=("vector",),
        )

    with pytest.raises(ValueError, match="unknown endpoint"):
        _graph("bad-endpoint", (_edge("e", "missing", "vector", "restore"),))


def test_rejects_domain_and_trace_shape_overflow() -> None:
    with pytest.raises(ValueError, match="at most 8 nodes"):
        GraphHypothesis(
            graph_id="too-large",
            nodes=tuple(_node(f"n{index}") for index in range(9)),
            edges=(),
            initial_node_ids=("n0",),
            residual_node_ids=("n8",),
        )

    with pytest.raises(ValueError, match="trace bit count"):
        ObservationTrace(
            checkpoint_node_ids=("database", "vector"),
            time_buckets=2,
            bits=(False,),
        )


def test_singleton_graph_is_discovered() -> None:
    graph = _multihop()
    experiment = _experiment("restore", "sync", "index")
    observation = ExecutedObservation(experiment, predict_trace(graph, experiment))

    report = update_version_space((graph,), (observation,), DiscoveryEvidence.complete())

    assert report.verdict is DiscoveryVerdict.GRAPH_DISCOVERED
    assert report.surviving_graph_ids == ("multihop",)
    assert report.inconsistency is None


def test_missing_evidence_forces_unverified() -> None:
    graph = _multihop()
    experiment = _experiment("restore", "sync", "index")
    evidence = replace(DiscoveryEvidence.complete(), observations_complete=False)

    report = update_version_space(
        (graph,),
        (ExecutedObservation(experiment, predict_trace(graph, experiment)),),
        evidence,
    )

    assert report.verdict is DiscoveryVerdict.UNVERIFIED
    assert report.surviving_graph_ids == ("multihop",)


def test_empty_version_space_is_out_of_hypothesis_with_shortest_inconsistency() -> None:
    graph = _multihop()
    experiment = _experiment("restore", "sync", "index")
    impossible = ObservationTrace(
        checkpoint_node_ids=experiment.checkpoint_node_ids,
        time_buckets=experiment.time_buckets,
        bits=(False, True, False, True, False, True),
    )

    report = update_version_space(
        (graph,),
        (ExecutedObservation(experiment, impossible),),
        DiscoveryEvidence.complete(),
    )

    assert report.verdict is DiscoveryVerdict.OUT_OF_HYPOTHESIS
    assert report.surviving_graph_ids == ()
    assert report.inconsistency is not None
    assert report.inconsistency.graph_id == "multihop"
    assert report.inconsistency.distance > 0


def test_materially_different_survivors_return_complete_equivalence_class() -> None:
    direct = _graph(
        "direct",
        (_edge("d1", "backup", "vector", "direct"),),
    )
    multihop = _multihop()
    experiment = _experiment()
    negative = predict_trace(direct, experiment)

    report = update_version_space(
        (direct, multihop),
        (ExecutedObservation(experiment, negative),),
        DiscoveryEvidence.complete(),
    )

    assert report.verdict is DiscoveryVerdict.NO_OBSERVED_RECURRENCE
    assert report.surviving_graph_ids == ("direct", "multihop")

    positive_experiment = _experiment("direct", "restore", "sync", "index")
    # A deliberately broad error budget keeps both materially different graphs alive.
    evidence = replace(DiscoveryEvidence.complete(), trace_error_budget=6)
    report = update_version_space(
        (direct, multihop),
        (
            ExecutedObservation(
                positive_experiment,
                predict_trace(multihop, positive_experiment),
            ),
        ),
        evidence,
    )
    assert report.verdict is DiscoveryVerdict.EQUIVALENCE_CLASS
    assert report.surviving_graph_ids == ("direct", "multihop")


def test_irrelevant_subgraph_difference_returns_path_class() -> None:
    base = _multihop("base")
    with_irrelevant = _graph(
        "with-irrelevant",
        (
            *base.edges,
            _edge("e4", "database", "telemetry", "log"),
        ),
        extra_nodes=("telemetry",),
    )
    experiment = _experiment("restore", "sync", "index")

    assert relevant_signature(base) == relevant_signature(with_irrelevant)
    report = update_version_space(
        (base, with_irrelevant),
        (ExecutedObservation(experiment, predict_trace(base, experiment)),),
        DiscoveryEvidence.complete(),
    )

    assert report.verdict is DiscoveryVerdict.PATH_CLASS_DISCOVERED
    assert report.surviving_graph_ids == ("base", "with-irrelevant")
    assert len(report.path_signatures) == 1


def test_input_order_is_rejected_instead_of_silently_normalized() -> None:
    graph_a = _multihop("a")
    graph_b = _multihop("b")

    with pytest.raises(ValueError, match="hypotheses must be sorted"):
        update_version_space((graph_b, graph_a), (), DiscoveryEvidence.complete())


def test_duplicate_observation_experiment_is_rejected() -> None:
    graph = _multihop()
    experiment = _experiment("restore", "sync", "index")
    observation = ExecutedObservation(experiment, predict_trace(graph, experiment))

    with pytest.raises(ValueError, match="experiment IDs must be unique"):
        update_version_space(
            (graph,),
            (observation, observation),
            DiscoveryEvidence.complete(),
        )
