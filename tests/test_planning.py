import pytest

from erasemap.domain import ArtifactState, RemediationAction
from erasemap.planning import exact_plan, greedy_plan
from tests.factories import remediation_case


def test_exact_plan_finds_minimum_cost_cover() -> None:
    required, actions = remediation_case()
    plan = exact_plan(required, actions)
    assert plan.covered_artifact_ids == frozenset(required)
    assert plan.total_cost == 5
    assert plan.action_ids == ("purge-index-and-template",)


def test_greedy_plan_never_claims_complete_with_uncovered_artifacts() -> None:
    required, actions = remediation_case(with_uncoverable=True)
    plan = greedy_plan(required, actions)
    assert not plan.complete
    assert plan.uncovered_artifact_ids == frozenset({"unknown-copy"})


def test_unpermitted_action_is_never_selected() -> None:
    action = RemediationAction(
        "forbidden",
        frozenset({"template"}),
        0,
        ArtifactState.ERASED,
        permitted=False,
    )
    plan = exact_plan(frozenset({"template"}), (action,))
    assert not plan.complete
    assert plan.action_ids == ()


def test_exact_solver_rejects_more_than_thirty_actions() -> None:
    actions = tuple(
        RemediationAction(f"a-{index}", frozenset({"x"}), 1, ArtifactState.ERASED)
        for index in range(31)
    )
    with pytest.raises(ValueError, match="greedy_plan"):
        exact_plan(frozenset({"x"}), actions)
