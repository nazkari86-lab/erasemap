from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class PrivacyAttackResult:
    raw_auc: float
    symmetric_auc: float
    advantage: float
    tpr_at_fpr: float
    target_fpr: float


def _softmax(logits: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 2 or not len(values) or values.shape[1] < 2:
        raise ValueError("logits must be a non-empty matrix with at least two classes")
    shifted = values - np.max(values, axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    probabilities: np.ndarray[Any, Any] = exponentials / np.sum(
        exponentials, axis=1, keepdims=True
    )
    return probabilities


def score_statistics(logits: np.ndarray[Any, Any]) -> dict[str, np.ndarray[Any, Any]]:
    values = np.asarray(logits, dtype=np.float64)
    probabilities = _softmax(values)
    sorted_probabilities = np.sort(probabilities, axis=1)
    entropy = -np.sum(probabilities * np.log(np.maximum(probabilities, 1e-12)), axis=1)
    maximum = np.max(values, axis=1, keepdims=True)
    energy = np.squeeze(maximum, axis=1) + np.log(
        np.sum(np.exp(values - maximum), axis=1)
    )
    return {
        "confidence": np.max(probabilities, axis=1),
        "energy": energy,
        "margin": sorted_probabilities[:, -1] - sorted_probabilities[:, -2],
        "negative_entropy": -entropy,
    }


def evaluate_attack(
    member_scores: np.ndarray[Any, Any],
    nonmember_scores: np.ndarray[Any, Any],
    *,
    target_fpr: float,
) -> PrivacyAttackResult:
    members = np.asarray(member_scores, dtype=np.float64).reshape(-1)
    nonmembers = np.asarray(nonmember_scores, dtype=np.float64).reshape(-1)
    if not len(members) or not len(nonmembers):
        raise ValueError("attack requires members and nonmembers")
    if not 0 <= target_fpr <= 1:
        raise ValueError("target_fpr must be between zero and one")
    labels = np.concatenate((np.ones(len(members)), np.zeros(len(nonmembers))))
    scores = np.concatenate((members, nonmembers))
    raw_auc = float(roc_auc_score(labels, scores))
    if raw_auc < 0.5:
        scores = -scores
    false_positive, true_positive, _ = roc_curve(labels, scores)
    eligible = true_positive[false_positive <= target_fpr]
    symmetric_auc = max(raw_auc, 1 - raw_auc)
    return PrivacyAttackResult(
        raw_auc=raw_auc,
        symmetric_auc=symmetric_auc,
        advantage=2 * (symmetric_auc - 0.5),
        tpr_at_fpr=float(np.max(eligible)) if len(eligible) else 0.0,
        target_fpr=target_fpr,
    )


def gaussian_likelihood_ratio_scores(
    target_scores: np.ndarray[Any, Any],
    in_shadow_scores: np.ndarray[Any, Any],
    out_shadow_scores: np.ndarray[Any, Any],
    *,
    variance_floor: float = 1e-6,
) -> np.ndarray[Any, Any]:
    target = np.asarray(target_scores, dtype=np.float64).reshape(-1)
    in_scores = np.asarray(in_shadow_scores, dtype=np.float64)
    out_scores = np.asarray(out_shadow_scores, dtype=np.float64)
    if in_scores.ndim != 2 or out_scores.ndim != 2:
        raise ValueError("shadow scores must be matrices")
    if in_scores.shape[1] != len(target) or out_scores.shape[1] != len(target):
        raise ValueError("shadow and target sample counts must match")
    if not len(in_scores) or not len(out_scores) or variance_floor <= 0:
        raise ValueError("both shadow groups and a positive variance floor are required")

    def log_density(samples: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        mean = np.mean(samples, axis=0)
        variance = np.maximum(np.var(samples, axis=0), variance_floor)
        density: np.ndarray[Any, Any] = -0.5 * (
            np.log(2 * np.pi * variance) + ((target - mean) ** 2) / variance
        )
        return density

    scores: np.ndarray[Any, Any] = log_density(in_scores) - log_density(out_scores)
    return scores


def balanced_shadow_membership(
    sample_count: int,
    shadow_count: int,
    *,
    inclusions_per_sample: int,
    seed: int,
) -> np.ndarray[Any, Any]:
    if sample_count <= 0 or shadow_count < 2:
        raise ValueError("positive samples and at least two shadow models are required")
    if not 1 <= inclusions_per_sample < shadow_count:
        raise ValueError("inclusions per sample must be between one and shadow_count - 1")
    rng = np.random.default_rng(seed)
    membership = np.zeros((shadow_count, sample_count), dtype=np.bool_)
    for sample in range(sample_count):
        selected = rng.permutation(shadow_count)[:inclusions_per_sample]
        membership[selected, sample] = True
    return membership


def split_shadow_scores(
    scores: np.ndarray[Any, Any], membership: np.ndarray[Any, Any]
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    values = np.asarray(scores, dtype=np.float64)
    included = np.asarray(membership, dtype=np.bool_)
    if values.shape != included.shape or values.ndim != 2:
        raise ValueError("shadow scores and membership must be equally shaped matrices")
    inclusion_counts = np.sum(included, axis=0)
    if not np.all(inclusion_counts == inclusion_counts[0]):
        raise ValueError("every sample must have the same number of in-shadow scores")
    in_count = int(inclusion_counts[0])
    if in_count == 0 or in_count == values.shape[0]:
        raise ValueError("every sample requires both in and out shadow scores")
    in_scores = np.stack([values[included[:, index], index] for index in range(values.shape[1])])
    out_scores = np.stack(
        [values[~included[:, index], index] for index in range(values.shape[1])]
    )
    return in_scores.T, out_scores.T


def embedding_nearest_neighbor_scores(
    embeddings: np.ndarray[Any, Any],
    member_indices: np.ndarray[Any, Any],
    nonmember_indices: np.ndarray[Any, Any],
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    values = np.asarray(embeddings, dtype=np.float64)
    members = np.asarray(member_indices, dtype=np.int64).reshape(-1)
    nonmembers = np.asarray(nonmember_indices, dtype=np.int64).reshape(-1)
    if values.ndim != 2 or len(members) < 2 or not len(nonmembers):
        raise ValueError("embedding attack requires a matrix, two members, and one nonmember")
    if np.any(members < 0) or np.any(nonmembers < 0):
        raise ValueError("embedding indices cannot be negative")
    if np.any(members >= len(values)) or np.any(nonmembers >= len(values)):
        raise ValueError("embedding index is out of range")
    normalized = values / np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)
    gallery = normalized[members]
    member_similarity = normalized[members] @ gallery.T
    np.fill_diagonal(member_similarity, -np.inf)
    nonmember_similarity = normalized[nonmembers] @ gallery.T
    return np.max(member_similarity, axis=1), np.max(nonmember_similarity, axis=1)
