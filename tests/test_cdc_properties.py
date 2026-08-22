from hypothesis import given
from hypothesis import strategies as st

from erasemap.cdc import brute_force_cdc, evaluate_actions, exact_cdc
from erasemap.multiview_verifier import upper_bound_channel
from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    PCUGVerdict,
    Transition,
    TransitionTarget,
)


def _small_case(
    cost_a: int, cost_b: int, cost_both: int
) -> tuple[PCUGGraph, CDCProtocol, tuple[CDCAction, ...]]:
    nodes = (
        PCUGNode("subject", "SUBJECT", "person-1"),
        PCUGNode("a", "COPY", "person-1"),
        PCUGNode("b", "COPY", "person-1"),
        PCUGNode("sink", "API", "shared", active_sink=True),
    )
    edges = tuple(
        PCUGEdge(
            source,
            target,
            EdgeKind.PROCESSING,
            EdgeState.ACTIVE,
            request_scoped=True,
            subject_id="person-1",
        )
        for source, target in (
            ("subject", "a"),
            ("subject", "b"),
            ("a", "sink"),
            ("b", "sink"),
        )
    )
    graph = PCUGGraph(
        nodes,
        edges,
        (upper_bound_channel("storage", value=0, upper_bound=0, threshold=0),),
    )
    protocol = CDCProtocol(
        "delete-small",
        "person-1",
        frozenset({"subject"}),
        frozenset({"sink"}),
        frozenset({"storage"}),
    )
    actions = (
        CDCAction(
            "close-a",
            cost_a,
            (Transition("a", EdgeState.CLOSED, "e-a", TransitionTarget.NODE),),
        ),
        CDCAction(
            "close-b",
            cost_b,
            (Transition("b", EdgeState.CLOSED, "e-b", TransitionTarget.NODE),),
        ),
        CDCAction(
            "close-both",
            cost_both,
            (
                Transition("a", EdgeState.CLOSED, "e-ab-a", TransitionTarget.NODE),
                Transition("b", EdgeState.CLOSED, "e-ab-b", TransitionTarget.NODE),
            ),
        ),
    )
    return graph, protocol, actions


@given(
    cost_a=st.integers(min_value=0, max_value=20),
    cost_b=st.integers(min_value=0, max_value=20),
    cost_both=st.integers(min_value=0, max_value=20),
)
def test_exact_equals_brute_force_for_small_cost_space(
    cost_a: int, cost_b: int, cost_both: int
) -> None:
    graph, protocol, actions = _small_case(cost_a, cost_b, cost_both)
    assert exact_cdc(graph, protocol, actions) == brute_force_cdc(graph, protocol, actions)


@given(
    cost_a=st.integers(min_value=0, max_value=20),
    cost_b=st.integers(min_value=0, max_value=20),
    cost_both=st.integers(min_value=0, max_value=20),
)
def test_exact_complete_plan_replays_as_complete(cost_a: int, cost_b: int, cost_both: int) -> None:
    graph, protocol, actions = _small_case(cost_a, cost_b, cost_both)
    plan = exact_cdc(graph, protocol, actions)
    chosen = tuple(action for action in actions if action.id in plan.action_ids)
    assert plan.verdict is PCUGVerdict.COMPLETE
    assert evaluate_actions(graph, protocol, chosen).verdict is PCUGVerdict.COMPLETE
