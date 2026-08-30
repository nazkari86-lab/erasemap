import pytest

from erasemap.temporal import (
    StabilizationControl,
    StabilizationStatus,
    TransitionCoverage,
)
from erasemap.temporal_multipath import multipath_controls
from erasemap.temporal_robust import (
    TopologyScenario,
    TopologyUncertaintyEnvelope,
    exact_robust_stabilization_cut,
)
from erasemap.temporal_robust_lab import (
    brute_force_robust_oracle,
    nominal_plan,
    robust_plan,
    run_robust_physical_trial,
    scenario_from_mask,
    topology_uncertainty_envelope,
)


def test_nominal_and_robust_plans_have_frozen_cost_tradeoff() -> None:
    nominal = nominal_plan()
    robust = robust_plan()

    assert nominal.control_ids == ("backup_restore_filter",)
    assert nominal.total_cost == 3
    assert robust.control_ids == ("persistent_subject_tombstone",)
    assert robust.total_cost == 7
    assert robust.complete
    assert robust.shortest_adversarial_witness is not None


def test_robust_plan_matches_separate_exhaustive_oracle() -> None:
    envelope = topology_uncertainty_envelope()
    controls = multipath_controls()
    plan = robust_plan(envelope, controls)

    assert brute_force_robust_oracle(envelope, controls) == (
        plan.control_ids,
        plan.total_cost,
        plan.status.value,
    )


def test_nominal_plan_regenerates_after_shift_but_robust_prove_does_not(tmp_path) -> None:
    trial = run_robust_physical_trial(tmp_path, scenario_mask=7, seed=71)

    assert trial.uncontrolled_regeneration
    assert trial.nominal_plan_regeneration
    assert not trial.robust_post_control_regeneration
    assert trial.adversarial_witness
    assert trial.oracle_match
    assert trial.robustness_premium == 4


def test_every_shifted_scenario_has_a_nominal_failure_and_robust_success(
    tmp_path,
) -> None:
    for mask in range(1, 8):
        trial = run_robust_physical_trial(
            tmp_path / str(mask), scenario_mask=mask, seed=100 + mask
        )
        assert trial.nominal_plan_regeneration
        assert not trial.robust_post_control_regeneration


def test_incomplete_scenario_coverage_forces_unverified() -> None:
    original = scenario_from_mask(1)
    broken = TopologyScenario(
        original.id,
        original.mutation_count,
        original.initial_state,
        original.transitions,
        TransitionCoverage(
            original.coverage.required_sensor_ids,
            tuple(
                type(item)(
                    item.id,
                    item.sensor_id,
                    item.transition_id,
                    False if index == 0 else item.verified,
                )
                for index, item in enumerate(original.coverage.observations)
            ),
        ),
        original.protocol,
    )
    nominal = scenario_from_mask(0)
    envelope = TopologyUncertaintyEnvelope(
        "broken", nominal.id, 1, (nominal, broken)
    )
    transition_ids = frozenset(
        transition.id for scenario in envelope.scenarios for transition in scenario.transitions
    )
    controls = tuple(
        StabilizationControl(
            item.id,
            item.cost,
            item.guarded_transition_ids & transition_ids,
            item.permitted,
        )
        for item in multipath_controls()
        if item.guarded_transition_ids & transition_ids
    )
    plan = exact_robust_stabilization_cut(envelope, controls)

    assert plan.status is StabilizationStatus.UNVERIFIED
    assert not plan.complete


def test_permissions_can_make_robust_problem_infeasible() -> None:
    controls = tuple(
        StabilizationControl(
            item.id, item.cost, item.guarded_transition_ids, permitted=False
        )
        for item in multipath_controls()
    )
    plan = exact_robust_stabilization_cut(topology_uncertainty_envelope(), controls)

    assert plan.status is StabilizationStatus.INFEASIBLE
    assert not plan.complete


def test_control_input_order_does_not_change_robust_selection() -> None:
    envelope = topology_uncertainty_envelope()
    forward = exact_robust_stabilization_cut(envelope, multipath_controls())
    reverse = exact_robust_stabilization_cut(
        envelope, tuple(reversed(multipath_controls()))
    )

    assert (forward.control_ids, forward.total_cost, forward.status) == (
        reverse.control_ids,
        reverse.total_cost,
        reverse.status,
    )


def test_envelope_validation_rejects_invalid_nominal_and_budget() -> None:
    nominal = scenario_from_mask(0)
    shifted = scenario_from_mask(1)
    with pytest.raises(ValueError, match="nominal"):
        TopologyUncertaintyEnvelope("bad", shifted.id, 1, (shifted,))
    with pytest.raises(ValueError, match="budget"):
        TopologyUncertaintyEnvelope("bad", nominal.id, 0, (nominal, shifted))


def test_control_cannot_reference_transition_outside_envelope() -> None:
    control = StabilizationControl("rogue", 1, frozenset({"unknown-transition"}))
    with pytest.raises(ValueError, match="outside envelope"):
        exact_robust_stabilization_cut(topology_uncertainty_envelope(), (control,))
