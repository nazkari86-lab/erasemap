from erasemap.metrics import TrialOutcome, aggregate_outcomes


def test_false_complete_rate_uses_only_positive_truth_cases() -> None:
    report = aggregate_outcomes(
        [
            TrialOutcome(True, True, 1.0, 1.0),
            TrialOutcome(True, False, 1.0, 1.0),
            TrialOutcome(False, True, 1.0, 1.0),
        ]
    )
    assert report.false_complete_rate == 0.5
    assert report.positive_trials == 2
    assert (report.true_positive, report.false_negative) == (1, 1)
    assert (report.true_negative, report.false_positive) == (1, 0)


def test_node_recall_and_confusion_metrics_are_explicit() -> None:
    report = aggregate_outcomes(
        [
            TrialOutcome(
                True,
                False,
                2.0,
                4.0,
                truth_artifact_ids=frozenset({"a", "b"}),
                detected_artifact_ids=frozenset({"a"}),
            ),
            TrialOutcome(False, False, 4.0, 2.0),
        ],
        bootstrap_seed=9,
        bootstrap_samples=100,
    )

    assert report.recall == 1.0
    assert report.precision == 0.5
    assert report.false_alarm_rate == 1.0
    assert report.exact_node_recall == 0.5
    assert report.mean_runtime_ms == 3.0
    assert report.mean_remediation_cost == 3.0
    assert report.intervals["recall"] is not None


def test_zero_denominators_return_none_instead_of_invented_values() -> None:
    report = aggregate_outcomes(
        [TrialOutcome(False, True, 1.0, 0.0)], bootstrap_samples=20
    )

    assert report.false_complete_rate is None
    assert report.recall is None
    assert report.precision is None
    assert report.false_alarm_rate == 0.0
    assert report.exact_node_recall is None
    assert report.intervals["false_complete_rate"] is None


def test_bootstrap_intervals_are_deterministic() -> None:
    outcomes = [
        TrialOutcome(index % 2 == 0, index % 3 == 0, float(index), 1.0)
        for index in range(1, 12)
    ]

    first = aggregate_outcomes(outcomes, bootstrap_seed=42, bootstrap_samples=200)
    second = aggregate_outcomes(outcomes, bootstrap_seed=42, bootstrap_samples=200)

    assert first.intervals == second.intervals


def test_empty_outcomes_are_rejected() -> None:
    try:
        aggregate_outcomes([])
    except ValueError as error:
        assert "at least one" in str(error)
    else:
        raise AssertionError("empty outcomes should be rejected")
