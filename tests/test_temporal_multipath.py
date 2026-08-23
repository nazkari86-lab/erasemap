from erasemap.pcug_domain import PCUGVerdict
from erasemap.temporal import RSEVerdict, evaluate_rse, exact_stabilization_cut
from erasemap.temporal_multipath import (
    ALL_CARRIERS,
    CARRIER_FACTS,
    brute_force_stabilization_oracle,
    multipath_controls,
    multipath_coverage,
    multipath_protocol,
    multipath_transitions,
    run_coverage_fault_trial,
    run_risk_trial,
    run_safe_trial,
    snapshot_pcug_verdict,
)


def test_snapshot_pcug_is_complete_without_future_transition_semantics() -> None:
    assert snapshot_pcug_verdict() is PCUGVerdict.COMPLETE


def test_single_path_selects_cheaper_local_filter() -> None:
    initial = frozenset({CARRIER_FACTS["retry_queue_replay"]})
    plan = exact_stabilization_cut(
        initial,
        multipath_transitions(),
        multipath_coverage(),
        multipath_protocol(),
        multipath_controls(),
    )

    assert plan.control_ids == ("retry_queue_filter",)
    assert plan.total_cost == 2


def test_mixed_paths_select_shared_tombstone_and_match_oracle() -> None:
    plan = exact_stabilization_cut(
        ALL_CARRIERS,
        multipath_transitions(),
        multipath_coverage(),
        multipath_protocol(),
        multipath_controls(),
    )
    oracle = brute_force_stabilization_oracle(ALL_CARRIERS, multipath_coverage())

    assert plan.control_ids == ("persistent_subject_tombstone",)
    assert plan.total_cost == 7
    assert oracle == (plan.control_ids, plan.total_cost)


def test_physical_risk_path_is_blocked_by_selected_control(tmp_path) -> None:
    trial = run_risk_trial(
        tmp_path / "risk",
        case_id="mixed-17",
        seed=17,
        carriers=ALL_CARRIERS,
    )

    assert trial.rse_verdict == RSEVerdict.REGENERATION_RISK.value
    assert trial.snapshot_pcug_verdict == PCUGVerdict.COMPLETE.value
    assert trial.regenerated_without_control
    assert not trial.regenerated_after_control
    assert trial.oracle_match


def test_safe_carriers_are_verified_without_blanket_false_alarm(tmp_path) -> None:
    trial = run_safe_trial(tmp_path / "safe", seed=19)

    assert trial.rse_verdict == RSEVerdict.RSE_VERIFIED.value
    assert trial.blanket_carrier_verdict == "INCOMPLETE"
    assert not trial.regenerated_after_control


def test_missing_attestation_fails_closed(tmp_path) -> None:
    trial = run_coverage_fault_trial(tmp_path / "coverage", seed=23)

    assert trial.rse_verdict == RSEVerdict.INCOMPLETE_COVERAGE.value
    assert not trial.coverage_complete


def test_all_single_carrier_families_have_regeneration_witnesses() -> None:
    for transition_id, carrier in CARRIER_FACTS.items():
        report = evaluate_rse(
            frozenset({carrier}),
            multipath_transitions(),
            multipath_coverage(),
            multipath_protocol(),
        )
        assert report.shortest_witness == (transition_id,)
