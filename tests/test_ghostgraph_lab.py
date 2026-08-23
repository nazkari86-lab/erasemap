from __future__ import annotations

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
from erasemap.ghostgraph_lab import GhostGraphStateLab, run_control_trial
from erasemap.temporal_robust import exact_robust_stabilization_cut


def _graph() -> GraphHypothesis:
    return GraphHypothesis(
        graph_id="multihop",
        nodes=(
            GraphNode("backup"),
            GraphNode("database"),
            GraphNode("vector"),
            GraphNode("worker"),
        ),
        edges=(
            GraphEdge("index", "worker", "vector", "index"),
            GraphEdge("restore", "backup", "database", "restore"),
            GraphEdge("sync", "database", "worker", "sync"),
        ),
        initial_node_ids=("backup",),
        residual_node_ids=("vector",),
    )


def test_mutable_lab_physically_replays_subject_state() -> None:
    graph = _graph()
    lab = GhostGraphStateLab(graph, target_subject="target", retained_subject="retained")

    assert lab.target_in_residual is False
    assert lab.replay(frozenset()) is True
    assert lab.target_in_residual is True
    assert lab.snapshot()["vector"] == ("retained", "target")


def test_target_scoped_control_stops_recurrence_without_retained_loss() -> None:
    graph = _graph()
    report = DiscoveryReport(
        DiscoveryVerdict.GRAPH_DISCOVERED,
        (graph.graph_id,),
        (relevant_signature(graph),),
        DiscoveryEvidence.complete(),
        None,
    )
    envelope = build_topology_envelope(report, {graph.graph_id: graph})
    plan = exact_robust_stabilization_cut(envelope, build_controls(envelope))

    trial = run_control_trial(graph, plan.control_ids)

    assert trial.uncontrolled_recurrence is True
    assert trial.post_control_recurrence is False
    assert trial.retained_subject_loss is False
    assert trial.control_ids == plan.control_ids


def test_nominal_single_edge_control_fails_on_uncontrolled_multihop_edge() -> None:
    graph = _graph()
    lab = GhostGraphStateLab(graph, target_subject="target", retained_subject="retained")

    recurrence = lab.replay(frozenset(("restore",)))

    assert recurrence is False
    lab.reset()
    recurrence = lab.replay(frozenset(("index",)))
    assert recurrence is False
    lab.reset()
    recurrence = lab.replay(frozenset(("missing",)))
    assert recurrence is True
