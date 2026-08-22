import pytest

from erasemap.cdc import (
    brute_force_cdc,
    evaluate_actions,
    exact_cdc,
    greedy_cdc,
)
from erasemap.pcug_domain import CDCAction, EdgeState, PCUGVerdict, SolverStatus
from tests.pcug_factories import forked_pcug_case


def test_deleting_parent_does_not_close_materialized_child() -> None:
    graph, protocol, actions = forked_pcug_case()
    report = evaluate_actions(graph, protocol, (actions["erase-source"],))
    assert report.verdict is PCUGVerdict.INCOMPLETE
    assert any(path[0] == "embedding" for path in report.active_paths)


def test_unknown_influence_edge_prevents_complete() -> None:
    graph, protocol, actions = forked_pcug_case(model_edge_state=EdgeState.UNKNOWN)
    report = evaluate_actions(graph, protocol, (actions["purge-derived"],))
    assert report.verdict is PCUGVerdict.UNVERIFIED
    assert report.unknown_paths


def test_purge_and_unlearn_produce_complete_registered_state() -> None:
    graph, protocol, actions = forked_pcug_case()
    report = evaluate_actions(
        graph,
        protocol,
        (actions["purge-derived"], actions["unlearn-model"]),
    )
    assert report.verdict is PCUGVerdict.COMPLETE
    assert not report.active_paths
    assert not report.unknown_paths


def test_unverified_transition_cannot_close_edge() -> None:
    graph, protocol, actions = forked_pcug_case()
    action = actions["unlearn-model"]
    transition = action.transitions[0]
    unverified = CDCAction(
        action.id,
        action.cost,
        (
            type(transition)(
                transition.target_id,
                transition.result_state,
                transition.evidence_id,
                transition.target,
                verified=False,
            ),
        ),
        result_channels=action.result_channels,
    )
    report = evaluate_actions(graph, protocol, (actions["purge-derived"], unverified))
    assert report.verdict is PCUGVerdict.UNVERIFIED


def test_unpermitted_action_is_rejected() -> None:
    graph, protocol, actions = forked_pcug_case()
    forbidden = CDCAction(
        "forbidden",
        0,
        actions["purge-derived"].transitions,
        permitted=False,
    )
    with pytest.raises(ValueError, match="not permitted"):
        evaluate_actions(graph, protocol, (forbidden,))


def test_exact_cdc_matches_brute_force() -> None:
    graph, protocol, action_map = forked_pcug_case()
    actions = tuple(action_map.values())
    assert exact_cdc(graph, protocol, actions) == brute_force_cdc(graph, protocol, actions)


def test_exact_cdc_selects_lowest_cost_complete_actions() -> None:
    graph, protocol, action_map = forked_pcug_case()
    plan = exact_cdc(graph, protocol, tuple(action_map.values()))
    assert plan.action_ids == ("purge-derived", "unlearn-model")
    assert plan.total_cost == 11
    assert plan.solver_status is SolverStatus.OPTIMAL


def test_exact_solver_rejects_action_set_above_protocol_limit() -> None:
    graph, protocol, action_map = forked_pcug_case()
    action = action_map["erase-source"]
    actions = tuple(
        CDCAction(f"action-{index}", action.cost, action.transitions) for index in range(25)
    )
    with pytest.raises(ValueError, match="action limit"):
        exact_cdc(graph, protocol, actions)


def test_greedy_is_deterministic_and_fail_closed() -> None:
    graph, protocol, action_map = forked_pcug_case()
    actions = tuple(action_map.values())
    forward = greedy_cdc(graph, protocol, actions)
    reverse = greedy_cdc(graph, protocol, tuple(reversed(actions)))
    assert forward == reverse
    assert forward.verdict is PCUGVerdict.COMPLETE
    assert forward.solver_status is SolverStatus.APPROXIMATE

