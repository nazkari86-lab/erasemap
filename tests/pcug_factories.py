from __future__ import annotations

from dataclasses import dataclass

from erasemap.multiview_verifier import unknown_channel, upper_bound_channel
from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    Transition,
    TransitionTarget,
)


@dataclass(frozen=True, slots=True)
class PCUGCase:
    graph: PCUGGraph
    protocol: CDCProtocol
    actions: tuple[CDCAction, ...]


def _edge(
    source: str,
    target: str,
    kind: EdgeKind = EdgeKind.MATERIAL,
    state: EdgeState = EdgeState.ACTIVE,
    *,
    request_scoped: bool = False,
) -> PCUGEdge:
    return PCUGEdge(
        source,
        target,
        kind,
        state,
        request_scoped=request_scoped,
        subject_id="person-1" if request_scoped or kind is EdgeKind.INFLUENCE else "",
    )


def forked_pcug_case(
    *,
    model_edge_state: EdgeState = EdgeState.ACTIVE,
) -> tuple[PCUGGraph, CDCProtocol, dict[str, CDCAction]]:
    nodes = (
        PCUGNode("subject", "SUBJECT_CLAIM", "person-1"),
        PCUGNode("source", "SOURCE", "person-1"),
        PCUGNode("embedding", "EMBEDDING", "person-1"),
        PCUGNode("index", "INDEX", "person-1"),
        PCUGNode("cache", "CACHE", "person-1"),
        PCUGNode("backup", "BACKUP", "person-1", active_sink=True),
        PCUGNode("model", "SHARED_MODEL", "shared"),
        PCUGNode("api", "API", "shared", active_sink=True),
    )
    edges = (
        _edge("subject", "source", request_scoped=True),
        _edge("source", "embedding", request_scoped=True),
        _edge("embedding", "index", EdgeKind.PROCESSING, request_scoped=True),
        _edge("index", "api", EdgeKind.PROCESSING, request_scoped=True),
        _edge("embedding", "cache", EdgeKind.PROCESSING, request_scoped=True),
        _edge("cache", "api", EdgeKind.PROCESSING, request_scoped=True),
        _edge("source", "backup", request_scoped=True),
        _edge(
            "subject",
            "model",
            EdgeKind.INFLUENCE,
            model_edge_state,
            request_scoped=True,
        ),
        _edge("model", "api", EdgeKind.PROCESSING),
    )
    channels = (
        upper_bound_channel("storage", value=0.0, upper_bound=0.0, threshold=0.0),
        unknown_channel("identity_lira", threshold=0.10),
    )
    graph = PCUGGraph(nodes, edges, channels)
    protocol = CDCProtocol(
        "delete-1",
        "person-1",
        frozenset({"subject"}),
        frozenset({"backup", "api"}),
        frozenset({"storage", "identity_lira"}),
    )

    edge_ids = {(edge.source_id, edge.target_id): edge.id for edge in edges}
    actions = {
        "erase-source": CDCAction(
            "erase-source",
            1,
            (
                Transition(
                    "source", EdgeState.CLOSED, "absence-source", TransitionTarget.NODE
                ),
            ),
        ),
        "purge-derived": CDCAction(
            "purge-derived",
            4,
            tuple(
                Transition(node, EdgeState.CLOSED, f"absence-{node}", TransitionTarget.NODE)
                for node in ("embedding", "index", "cache", "backup")
            ),
        ),
        "unlearn-model": CDCAction(
            "unlearn-model",
            7,
            (
                Transition(
                    edge_ids[("subject", "model")],
                    EdgeState.CLOSED,
                    "model-audit-v1",
                ),
            ),
            result_channels=(
                upper_bound_channel(
                    "identity_lira",
                    value=0.03,
                    upper_bound=0.08,
                    threshold=0.10,
                    evidence_id="model-audit-v1",
                ),
            ),
        ),
        "block-api": CDCAction(
            "block-api",
            20,
            tuple(
                Transition(edge.id, EdgeState.CLOSED, "enforced-subject-block")
                for edge in edges
                if edge.target_id == "api" and edge.request_scoped
            ),
        ),
    }
    return graph, protocol, actions


def complete_action_set() -> PCUGCase:
    graph, protocol, action_map = forked_pcug_case()
    actions = tuple(action_map[name] for name in ("purge-derived", "unlearn-model"))
    return PCUGCase(graph, protocol, actions)

