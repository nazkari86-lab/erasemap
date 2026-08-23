from __future__ import annotations

from dataclasses import replace

import pytest

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryReport,
    DiscoveryVerdict,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
    relevant_signature,
)
from erasemap.ghostgraph_bridge import build_controls, build_topology_envelope
from erasemap.temporal import StabilizationStatus, evaluate_coverage
from erasemap.temporal_robust import exact_robust_stabilization_cut


def _graph(graph_id: str, *, direct: bool = False) -> GraphHypothesis:
    nodes = (
        GraphNode("backup"),
        GraphNode("database"),
        GraphNode("vector"),
        GraphNode("worker"),
    )
    edges = (
        (GraphEdge("direct", "backup", "vector", "direct_restore"),)
        if direct
        else (
            GraphEdge("restore", "backup", "database", "restore"),
            GraphEdge("sync", "database", "worker", "sync"),
            GraphEdge("index", "worker", "vector", "index"),
        )
    )
    return GraphHypothesis(
        graph_id=graph_id,
        nodes=nodes,
        edges=tuple(sorted(edges, key=lambda item: item.edge_id)),
        initial_node_ids=("backup",),
        residual_node_ids=("vector",),
    )


def _report(graphs: tuple[GraphHypothesis, ...], verdict: DiscoveryVerdict) -> DiscoveryReport:
    return DiscoveryReport(
        verdict=verdict,
        surviving_graph_ids=tuple(graph.graph_id for graph in graphs),
        path_signatures=tuple(sorted({relevant_signature(graph) for graph in graphs})),
        evidence=DiscoveryEvidence.complete(),
        inconsistency=None,
    )


def test_unique_multihop_path_becomes_typed_temporal_transitions() -> None:
    graph = _graph("multihop")

    envelope = build_topology_envelope(
        _report((graph,), DiscoveryVerdict.GRAPH_DISCOVERED),
        {graph.graph_id: graph},
    )

    scenario = envelope.nominal
    assert tuple(item.id for item in scenario.transitions) == ("index", "restore", "sync")
    restore = next(item for item in scenario.transitions if item.id == "restore")
    assert restore.requires == frozenset(("present:backup",))
    assert restore.adds == frozenset(("present:database",))
    assert scenario.protocol.residual_facts == frozenset(("present:vector",))
    assert evaluate_coverage(scenario.transitions, scenario.coverage).complete is True


def test_equivalence_class_remains_multiple_robust_scenarios() -> None:
    direct = _graph("direct", direct=True)
    multihop = _graph("multihop")
    graphs = (direct, multihop)
    report = _report(graphs, DiscoveryVerdict.EQUIVALENCE_CLASS)

    envelope = build_topology_envelope(report, {graph.graph_id: graph for graph in graphs})
    controls = build_controls(envelope)
    plan = exact_robust_stabilization_cut(envelope, controls)

    assert tuple(item.id for item in envelope.scenarios) == ("direct", "multihop")
    assert plan.status is StabilizationStatus.OPTIMAL
    assert plan.complete
    assert plan.shortest_adversarial_witness is not None


@pytest.mark.parametrize(
    "verdict",
    (
        DiscoveryVerdict.UNVERIFIED,
        DiscoveryVerdict.OUT_OF_HYPOTHESIS,
        DiscoveryVerdict.NO_OBSERVED_RECURRENCE,
    ),
)
def test_non_actionable_report_cannot_create_topology(verdict: DiscoveryVerdict) -> None:
    graph = _graph("multihop")
    report = _report((graph,), verdict)

    with pytest.raises(ValueError, match="not actionable"):
        build_topology_envelope(report, {graph.graph_id: graph})


def test_invalid_evidence_cannot_be_bridged() -> None:
    graph = _graph("multihop")
    report = replace(
        _report((graph,), DiscoveryVerdict.GRAPH_DISCOVERED),
        evidence=replace(DiscoveryEvidence.complete(), observations_complete=False),
    )

    with pytest.raises(ValueError, match="evidence is incomplete"):
        build_topology_envelope(report, {graph.graph_id: graph})


def test_missing_survivor_graph_is_rejected() -> None:
    graph = _graph("multihop")

    with pytest.raises(ValueError, match="missing graph hypothesis"):
        build_topology_envelope(
            _report((graph,), DiscoveryVerdict.GRAPH_DISCOVERED),
            {},
        )
