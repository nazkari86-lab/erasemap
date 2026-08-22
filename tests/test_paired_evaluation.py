import numpy as np
import pytest

from erasemap.paired_evaluation import (
    identity_cohesion_scores,
    paired_attack_differences,
    split_embedding_mse,
)


def test_split_embedding_mse_separates_forgotten_and_retained() -> None:
    exact = np.zeros((4, 2))
    candidate = np.array([[2.0, 0.0], [2.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    forgotten, retained = split_embedding_mse(
        candidate, exact, np.array([0, 1]), np.array([2, 3])
    )

    assert forgotten == 2.0
    assert retained == 0.5


def test_identity_cohesion_is_self_match_free() -> None:
    embeddings = np.array([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]])
    scores = identity_cohesion_scores(embeddings, np.array([0, 1]))

    assert np.all(scores < 1.0)
    assert scores[0] == pytest.approx(scores[1])


def test_paired_attack_difference_preserves_trial_pairing() -> None:
    trials = [
        {"seed": 1, "anonymous_forget_subject": 2, "method": "selective", "attack": 0.3},
        {"seed": 1, "anonymous_forget_subject": 2, "method": "exact", "attack": 0.2},
        {"seed": 2, "anonymous_forget_subject": 3, "method": "selective", "attack": 0.1},
        {"seed": 2, "anonymous_forget_subject": 3, "method": "exact", "attack": 0.2},
    ]

    result = paired_attack_differences(
        trials,
        ("attack",),
        selective_method="selective",
        exact_method="exact",
        bootstrap_seed=7,
        bootstrap_samples=100,
    )[0]

    assert result.trials == 2
    assert result.mean_difference == pytest.approx(0.0)
