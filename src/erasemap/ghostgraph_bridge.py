from __future__ import annotations

from collections.abc import Mapping

from erasemap.ghostgraph import DiscoveryReport, DiscoveryVerdict, GraphHypothesis
from erasemap.temporal import (
    RSEProtocol,
    StabilizationControl,
    TemporalTransition,
    TransitionCoverage,
    TransitionObservation,
)
from erasemap.temporal_robust import TopologyScenario, TopologyUncertaintyEnvelope

_ACTIONABLE = frozenset(
    (
        DiscoveryVerdict.GRAPH_DISCOVERED,
        DiscoveryVerdict.PATH_CLASS_DISCOVERED,
        DiscoveryVerdict.EQUIVALENCE_CLASS,
    )
)


def build_topology_envelope(
    report: DiscoveryReport,
    graph_by_id: Mapping[str, GraphHypothesis],
) -> TopologyUncertaintyEnvelope:
    if report.verdict not in _ACTIONABLE:
        raise ValueError(f"GhostGraph verdict {report.verdict.value} is not actionable")
    if not report.evidence.valid:
        raise ValueError("GhostGraph evidence is incomplete")
    if not report.surviving_graph_ids:
        raise ValueError("actionable GhostGraph report has no surviving graph")
    missing = tuple(
        graph_id for graph_id in report.surviving_graph_ids if graph_id not in graph_by_id
    )
    if missing:
        raise ValueError(f"missing graph hypothesis: {missing[0]}")
    selected = tuple(graph_by_id[graph_id] for graph_id in report.surviving_graph_ids)
    residual_sets = {graph.residual_node_ids for graph in selected}
    if len(residual_sets) != 1:
        raise ValueError("surviving graphs use different residual semantics")
    nominal = selected[0]
    nominal_edges = _relevant_edge_ids(nominal)
    scenarios: list[TopologyScenario] = []
    for graph in selected:
        relevant_ids = _relevant_edge_ids(graph)
        if not relevant_ids:
            raise ValueError(f"graph {graph.graph_id!r} has no recurrence path")
        edge_by_id = {edge.edge_id: edge for edge in graph.edges}
        transitions = tuple(
            TemporalTransition(
                id=edge_id,
                requires=frozenset((f"present:{edge_by_id[edge_id].source_id}",)),
                adds=frozenset((f"present:{edge_by_id[edge_id].target_id}",)),
            )
            for edge_id in sorted(relevant_ids)
        )
        observations = tuple(
            TransitionObservation(
                id=f"obs:{graph.graph_id}:{transition.id}",
                sensor_id=f"sensor:{transition.id}",
                transition_id=transition.id,
                verified=True,
            )
            for transition in transitions
        )
        scenarios.append(
            TopologyScenario(
                id=graph.graph_id,
                mutation_count=len(nominal_edges.symmetric_difference(relevant_ids)),
                initial_state=frozenset(
                    f"present:{node_id}" for node_id in graph.initial_node_ids
                ),
                transitions=transitions,
                coverage=TransitionCoverage(
                    required_sensor_ids=frozenset(item.sensor_id for item in observations),
                    observations=observations,
                ),
                protocol=RSEProtocol(
                    protocol_id=f"ghostgraph:{graph.graph_id}",
                    residual_facts=frozenset(
                        f"present:{node_id}" for node_id in graph.residual_node_ids
                    ),
                ),
            )
        )
    return TopologyUncertaintyEnvelope(
        id="ghostgraph-discovered-envelope",
        nominal_scenario_id=nominal.graph_id,
        max_mutations=max(item.mutation_count for item in scenarios),
        scenarios=tuple(scenarios),
    )


def build_controls(
    envelope: TopologyUncertaintyEnvelope,
) -> tuple[StabilizationControl, ...]:
    transition_ids = tuple(
        sorted(
            {
                transition.id
                for scenario in envelope.scenarios
                for transition in scenario.transitions
            }
        )
    )
    return tuple(
        StabilizationControl(
            id=f"guard:{transition_id}",
            cost=1,
            guarded_transition_ids=frozenset((transition_id,)),
        )
        for transition_id in transition_ids
    )


def _relevant_edge_ids(graph: GraphHypothesis) -> frozenset[str]:
    outgoing = {
        node.node_id: tuple(edge for edge in graph.edges if edge.source_id == node.node_id)
        for node in graph.nodes
    }
    residual = frozenset(graph.residual_node_ids)
    found: set[str] = set()

    def visit(node_id: str, visited: frozenset[str], path: tuple[str, ...]) -> None:
        if node_id in residual:
            found.update(path)
            return
        for edge in outgoing[node_id]:
            if edge.target_id not in visited:
                visit(edge.target_id, visited | {edge.target_id}, (*path, edge.edge_id))

    for initial_id in graph.initial_node_ids:
        visit(initial_id, frozenset((initial_id,)), ())
    return frozenset(found)
