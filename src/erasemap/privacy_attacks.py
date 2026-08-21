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
