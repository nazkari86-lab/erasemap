import pytest

from erasemap.temporal import (
    RSEProtocol,
    RSEVerdict,
    StabilizationControl,
    StabilizationStatus,
    TemporalTransition,
    TransitionCoverage,
    TransitionObservation,
    evaluate_rse,
    exact_stabilization_cut,
)


def _transitions() -> tuple[TemporalTransition, ...]:
    return (
        TemporalTransition("restore", frozenset({"backup"}), frozenset({"postgres"})),
        TemporalTransition("etl", frozenset({"postgres"}), frozenset({"qdrant"})),
        TemporalTransition("train", frozenset({"qdrant"}), frozenset({"model"})),
    )


def _coverage(*, verified: bool = True) -> TransitionCoverage:
    return TransitionCoverage(
        frozenset({"backup-sensor", "pipeline-sensor"}),
        (
            TransitionObservation("o1", "backup-sensor", "restore", verified),
            TransitionObservation("o2", "pipeline-sensor", "etl", True),
            TransitionObservation("o3", "pipeline-sensor", "train", True),
        ),
    )


def _protocol() -> RSEProtocol:
    return RSEProtocol("rse-test-v1", frozenset({"postgres", "qdrant", "model"}))


def test_rse_returns_shortest_regeneration_witness() -> None:
    report = evaluate_rse(frozenset({"backup"}), _transitions(), _coverage(), _protocol())

    assert report.verdict is RSEVerdict.REGENERATION_RISK
    assert report.snapshot_complete
    assert report.shortest_witness == ("restore",)
    assert report.witness_state == frozenset({"backup", "postgres"})


def test_snapshot_residual_takes_precedence() -> None:
    report = evaluate_rse(
        frozenset({"postgres"}), _transitions(), _coverage(), _protocol()
    )

    assert report.verdict is RSEVerdict.SNAPSHOT_INCOMPLETE
    assert not report.snapshot_complete
    assert report.shortest_witness == ()


def test_incomplete_coverage_fails_closed() -> None:
    report = evaluate_rse(
        frozenset(), _transitions(), _coverage(verified=False), _protocol()
    )

    assert report.verdict is RSEVerdict.INCOMPLETE_COVERAGE
    assert report.coverage.missing_sensor_ids == ("backup-sensor",)
    assert report.coverage.unverified_observation_ids == ("o1",)


def test_unregistered_observation_fails_closed() -> None:
    coverage = TransitionCoverage(
        frozenset({"runtime"}),
        (TransitionObservation("o1", "runtime", "rogue-export", True),),
    )
    report = evaluate_rse(frozenset(), _transitions(), coverage, _protocol())

    assert report.verdict is RSEVerdict.INCOMPLETE_COVERAGE
    assert report.coverage.unregistered_transition_ids == ("rogue-export",)


def test_unobserved_registered_transition_fails_closed() -> None:
    coverage = TransitionCoverage(
        frozenset({"backup-sensor"}),
        (TransitionObservation("o1", "backup-sensor", "restore", True),),
    )
    report = evaluate_rse(frozenset(), _transitions(), coverage, _protocol())

    assert report.verdict is RSEVerdict.INCOMPLETE_COVERAGE
    assert report.coverage.unobserved_transition_ids == ("etl", "train")


def test_exact_cut_prefers_lowest_cost_complete_control() -> None:
    controls = (
        StabilizationControl("destroy-backup", 40, frozenset({"restore"})),
        StabilizationControl("restore-exclusion", 5, frozenset({"restore"})),
        StabilizationControl("etl-exclusion", 3, frozenset({"etl"})),
    )
    plan = exact_stabilization_cut(
        frozenset({"backup"}), _transitions(), _coverage(), _protocol(), controls
    )

    assert plan.complete
    assert plan.status is StabilizationStatus.OPTIMAL
    assert plan.control_ids == ("restore-exclusion",)
    assert plan.total_cost == 5


def test_cut_cannot_certify_incomplete_coverage() -> None:
    plan = exact_stabilization_cut(
        frozenset(),
        _transitions(),
        _coverage(verified=False),
        _protocol(),
        (StabilizationControl("guard", 1, frozenset({"restore"})),),
    )

    assert not plan.complete
    assert plan.status is StabilizationStatus.UNVERIFIED


def test_cut_with_known_risk_still_reports_unverified_coverage() -> None:
    plan = exact_stabilization_cut(
        frozenset({"backup"}),
        _transitions(),
        _coverage(verified=False),
        _protocol(),
        (StabilizationControl("guard", 1, frozenset({"restore"})),),
    )

    assert not plan.complete
    assert plan.status is StabilizationStatus.UNVERIFIED


def test_rejects_invalid_and_unknown_guards() -> None:
    with pytest.raises(ValueError, match="change"):
        TemporalTransition("noop", frozenset(), frozenset())
    with pytest.raises(ValueError, match="unknown"):
        evaluate_rse(
            frozenset(),
            _transitions(),
            _coverage(),
            _protocol(),
            guarded_transition_ids=frozenset({"unknown"}),
        )
    with pytest.raises(ValueError, match="guards unknown"):
        exact_stabilization_cut(
            frozenset(),
            _transitions(),
            _coverage(),
            _protocol(),
            (StabilizationControl("bad", 1, frozenset({"unknown"})),),
        )
