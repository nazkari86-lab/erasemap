from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class MembershipAttackMetrics:
    auc: float
    tpr_at_target_fpr: float
    target_fpr: float
    member_count: int
    nonmember_count: int


def align_probabilities(
    probabilities: np.ndarray[Any, Any],
    *,
    model_classes: np.ndarray[Any, Any],
    all_classes: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    if probabilities.ndim != 2:
        raise ValueError("probabilities must be a matrix")
    if probabilities.shape[1] != len(model_classes):
        raise ValueError("probability columns do not match model classes")
    if len(np.unique(model_classes)) != len(model_classes):
        raise ValueError("model classes must be unique")
    locations = {int(label): index for index, label in enumerate(all_classes)}
    aligned = np.zeros((len(probabilities), len(all_classes)), dtype=np.float64)
    for source, label in enumerate(model_classes):
        target = locations.get(int(label))
        if target is None:
            raise ValueError(f"model class {label} is absent from all_classes")
        aligned[:, target] = probabilities[:, source]
    return aligned


def membership_attack_metrics(
    *,
    member_scores: np.ndarray[Any, Any],
    nonmember_scores: np.ndarray[Any, Any],
    target_fpr: float,
) -> MembershipAttackMetrics:
    members = np.asarray(member_scores, dtype=np.float64).reshape(-1)
    nonmembers = np.asarray(nonmember_scores, dtype=np.float64).reshape(-1)
    if not len(members) or not len(nonmembers):
        raise ValueError("membership attack requires both groups")
    if not 0 <= target_fpr <= 1:
        raise ValueError("target_fpr must be between zero and one")
    labels = np.concatenate((np.ones(len(members)), np.zeros(len(nonmembers))))
    scores = np.concatenate((members, nonmembers))
    auc = float(roc_auc_score(labels, scores))
    false_positive_rates, true_positive_rates, _ = roc_curve(labels, scores)
    eligible = true_positive_rates[false_positive_rates <= target_fpr]
    tpr = float(np.max(eligible)) if len(eligible) else 0.0
    return MembershipAttackMetrics(
        auc=auc,
        tpr_at_target_fpr=tpr,
        target_fpr=target_fpr,
        member_count=len(members),
        nonmember_count=len(nonmembers),
    )


def mean_total_variation(
    left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]
) -> float:
    if left.shape != right.shape or left.ndim != 2:
        raise ValueError("probability matrices must have equal two-dimensional shapes")
    return float(np.mean(0.5 * np.sum(np.abs(left - right), axis=1)))
