from __future__ import annotations

from dataclasses import replace

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryReport,
    DiscoveryVerdict,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
    relevant_signature,
)
from erasemap.temporal import StabilizationControl
from erasemap.unified import EraSeMapStage, EraSeMapVerdict, StageStatus, run_erasemap
from tests.pcug_factories import complete_action_set


def _hidden_graph() -> GraphHypothesis:
    return GraphHypothesis(
        graph_id="backup-restore",
        nodes=(GraphNode("backup"), GraphNode("database")),
        edges=(GraphEdge("restore", "backup", "database", "restore"),),
        initial_node_ids=("backup",),
        residual_node_ids=("database",),
    )


def _discovery(
    graph: GraphHypothesis,
    verdict: DiscoveryVerdict = DiscoveryVerdict.GRAPH_DISCOVERED,
) -> DiscoveryReport:
    return DiscoveryReport(
        verdict=verdict,
        surviving_graph_ids=(graph.graph_id,),
        path_signatures=(relevant_signature(graph),),
        evidence=DiscoveryEvidence.complete(),
        inconsistency=None,
    )


def test_one_pipeline_composes_all_mandatory_stages() -> None:
    case = complete_action_set()
    hidden = _hidden_graph()

    result = run_erasemap(
        case.graph,
        case.protocol,
        case.actions,
        _discovery(hidden),
        {hidden.graph_id: hidden},
    )

    assert result.verdict is EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE
    assert result.certificate_ready
    assert tuple(item.stage for item in result.stages) == tuple(EraSeMapStage)
    assert result.stages[-1].status is StageStatus.READY
    assert result.deletion_plan.complete
    assert result.stabilization_plan is not None
    assert result.stabilization_plan.complete


def test_unverified_discovery_blocks_temporal_certificate() -> None:
    case = complete_action_set()
    hidden = _hidden_graph()

    result = run_erasemap(
        case.graph,
        case.protocol,
        case.actions,
        _discovery(hidden, DiscoveryVerdict.NO_OBSERVED_RECURRENCE),
        {hidden.graph_id: hidden},
    )

    assert result.verdict is EraSeMapVerdict.UNVERIFIED
    assert not result.certificate_ready
    assert result.topology_envelope is None
    assert result.stabilization_plan is None
    assert result.stages[-1].status is StageStatus.BLOCKED


def test_infeasible_temporal_control_prevents_complete() -> None:
    case = complete_action_set()
    hidden = _hidden_graph()
    forbidden = (
        StabilizationControl("guard:restore", 1, frozenset({"restore"}), permitted=False),
    )

    result = run_erasemap(
        case.graph,
        case.protocol,
        case.actions,
        _discovery(hidden),
        {hidden.graph_id: hidden},
        temporal_controls=forbidden,
    )

    assert result.verdict is EraSeMapVerdict.INCOMPLETE
    assert not result.certificate_ready
    assert result.stages[-2].status is StageStatus.INCOMPLETE


def test_invalid_temporal_controls_fail_closed() -> None:
    case = complete_action_set()
    hidden = _hidden_graph()
    duplicate_controls = (
        StabilizationControl("duplicate", 1, frozenset({"restore"})),
        StabilizationControl("duplicate", 2, frozenset({"restore"})),
    )

    result = run_erasemap(
        case.graph,
        case.protocol,
        case.actions,
        _discovery(hidden),
        {hidden.graph_id: hidden},
        temporal_controls=duplicate_controls,
    )

    assert result.verdict is EraSeMapVerdict.UNVERIFIED
    assert result.stabilization_plan is None
    assert result.stages[-2].status is StageStatus.UNVERIFIED
    assert result.stages[-1].status is StageStatus.BLOCKED


def test_invalid_discovery_evidence_fails_closed() -> None:
    case = complete_action_set()
    hidden = _hidden_graph()
    discovery = replace(
        _discovery(hidden),
        evidence=replace(DiscoveryEvidence.complete(), observations_complete=False),
    )

    result = run_erasemap(
        case.graph,
        case.protocol,
        case.actions,
        discovery,
        {hidden.graph_id: hidden},
    )

    assert result.verdict is EraSeMapVerdict.UNVERIFIED
    assert result.stages[1].status is StageStatus.UNVERIFIED


def test_stale_discovery_hypothesis_fails_closed() -> None:
    case = complete_action_set()
    hidden = _hidden_graph()
    stale = replace(_discovery(hidden), surviving_graph_ids=("removed-from-catalogue",))

    result = run_erasemap(
        case.graph,
        case.protocol,
        case.actions,
        stale,
        {hidden.graph_id: hidden},
    )

    assert result.verdict is EraSeMapVerdict.UNVERIFIED
    assert result.topology_envelope is None
    assert result.stabilization_plan is None
    assert result.stages[1].status is StageStatus.UNVERIFIED
