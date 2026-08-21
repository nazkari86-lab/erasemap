import numpy as np

from erasemap.unlearning_metrics import (
    align_probabilities,
    mean_total_variation,
    membership_attack_metrics,
)


def test_probability_alignment_inserts_missing_class_as_zero() -> None:
    probabilities = np.array([[0.7, 0.3], [0.2, 0.8]])

    aligned = align_probabilities(
        probabilities, model_classes=np.array([0, 2]), all_classes=np.array([0, 1, 2])
    )

    np.testing.assert_allclose(aligned, [[0.7, 0.0, 0.3], [0.2, 0.0, 0.8]])


def test_membership_attack_reports_auc_and_low_fpr_tpr() -> None:
    metrics = membership_attack_metrics(
        member_scores=np.array([0.9, 0.8, 0.7, 0.6]),
        nonmember_scores=np.array([0.4, 0.3, 0.2, 0.1]),
        target_fpr=0.1,
    )

    assert metrics.auc == 1.0
    assert metrics.tpr_at_target_fpr == 1.0
    assert metrics.member_count == metrics.nonmember_count == 4


def test_membership_attack_ties_are_random_guessing() -> None:
    metrics = membership_attack_metrics(
        member_scores=np.zeros(4), nonmember_scores=np.zeros(4), target_fpr=0.1
    )

    assert metrics.auc == 0.5
    assert metrics.tpr_at_target_fpr == 0.0


def test_total_variation_is_bounded() -> None:
    left = np.array([[1.0, 0.0], [0.5, 0.5]])
    right = np.array([[0.0, 1.0], [0.5, 0.5]])

    assert mean_total_variation(left, right) == 0.5
