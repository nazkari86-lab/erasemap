import numpy as np
import pytest

from erasemap.privacy_attacks import (
    balanced_shadow_membership,
    embedding_nearest_neighbor_scores,
    evaluate_attack,
    gaussian_likelihood_ratio_scores,
    score_statistics,
    split_shadow_scores,
)


def test_score_statistics_are_finite_and_named() -> None:
    statistics = score_statistics(np.array([[3.0, 1.0], [0.0, 0.0]]))
    assert set(statistics) == {"confidence", "energy", "margin", "negative_entropy"}
    assert all(np.all(np.isfinite(values)) for values in statistics.values())
    assert statistics["confidence"][0] > statistics["confidence"][1]


def test_attack_is_orientation_invariant() -> None:
    members = np.array([0.9, 0.8, 0.7])
    nonmembers = np.array([0.3, 0.2, 0.1])
    forward = evaluate_attack(members, nonmembers, target_fpr=0.01)
    reverse = evaluate_attack(-members, -nonmembers, target_fpr=0.01)
    assert forward.symmetric_auc == reverse.symmetric_auc == 1.0
    assert forward.advantage == reverse.advantage == 1.0


def test_gaussian_likelihood_ratio_prefers_in_distribution() -> None:
    target = np.array([0.9, 0.85])
    in_shadows = np.array([[0.8, 0.2], [1.0, 0.0]])
    out_shadows = np.array([[0.1, 0.8], [0.2, 0.9]])
    scores = gaussian_likelihood_ratio_scores(target, in_shadows, out_shadows)
    assert scores[0] > 0
    assert scores[1] < 0


def test_balanced_shadow_membership_and_score_split() -> None:
    membership = balanced_shadow_membership(7, 6, inclusions_per_sample=3, seed=42)
    scores = np.arange(42, dtype=np.float64).reshape(6, 7)
    in_scores, out_scores = split_shadow_scores(scores, membership)

    assert membership.shape == (6, 7)
    assert np.all(np.sum(membership, axis=0) == 3)
    assert in_scores.shape == out_scores.shape == (3, 7)
    assert set(in_scores[:, 0]) == set(scores[membership[:, 0], 0])


def test_embedding_attack_excludes_exact_self_match() -> None:
    embeddings = np.array(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [-1.0, 0.0]], dtype=np.float64
    )
    member_scores, nonmember_scores = embedding_nearest_neighbor_scores(
        embeddings, np.array([0, 1]), np.array([2, 3])
    )

    assert np.all(member_scores < 1.0)
    assert member_scores.mean() > nonmember_scores.mean()


@pytest.mark.parametrize(
    "call",
    [
        lambda: score_statistics(np.ones((2, 1))),
        lambda: evaluate_attack(np.array([]), np.array([1.0]), target_fpr=0.1),
        lambda: gaussian_likelihood_ratio_scores(
            np.array([1.0]), np.ones((1, 2)), np.ones((1, 1))
        ),
        lambda: balanced_shadow_membership(1, 2, inclusions_per_sample=2, seed=1),
        lambda: split_shadow_scores(np.ones((2, 2)), np.ones((2, 3), dtype=bool)),
        lambda: embedding_nearest_neighbor_scores(
            np.ones((2, 2)), np.array([0]), np.array([1])
        ),
    ],
)
def test_invalid_inputs(call: object) -> None:
    with pytest.raises(ValueError):
        call()  # type: ignore[operator]
