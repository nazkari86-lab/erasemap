import math

import pytest

from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    ChannelDecision,
    ChannelResult,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    Transition,
)


def test_unknown_influence_edge_is_not_closed() -> None:
    edge = PCUGEdge(
        "source",
        "model",
        EdgeKind.INFLUENCE,
        EdgeState.UNKNOWN,
        subject_id="person-1",
    )
    assert edge.state is EdgeState.UNKNOWN


@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_channel_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        ChannelResult("mia", value, 0.2, 0.1, ChannelDecision.FAIL, True)


def test_influence_edge_requires_subject() -> None:
    with pytest.raises(ValueError, match="subject"):
        PCUGEdge("source", "model", EdgeKind.INFLUENCE, EdgeState.ACTIVE)


def test_graph_rejects_unknown_edge_endpoint() -> None:
    source = PCUGNode("source", "SOURCE", "person-1")
    with pytest.raises(ValueError, match="unknown target"):
        PCUGGraph(
            nodes=(source,),
            edges=(PCUGEdge("source", "missing", EdgeKind.MATERIAL, EdgeState.ACTIVE),),
            channel_results=(),
        )


def test_protocol_rejects_unknown_source() -> None:
    graph = PCUGGraph(
        nodes=(PCUGNode("source", "SOURCE", "person-1"),),
        edges=(),
        channel_results=(),
    )
    with pytest.raises(ValueError, match="source"):
        CDCProtocol(
            request_id="delete-1",
            subject_id="person-1",
            source_ids=frozenset({"missing"}),
            sink_ids=frozenset({"source"}),
        ).validate_graph(graph)


def test_action_rejects_duplicate_transition_target() -> None:
    transition = Transition("edge-1", EdgeState.CLOSED, "evidence-1")
    with pytest.raises(ValueError, match="duplicate transition"):
        CDCAction("erase", 1, (transition, transition))

