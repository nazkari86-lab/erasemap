from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class VerificationMetrics:
    auc: float
    tar_at_far: float
    far_target: float
    positive_pairs: int
    negative_pairs: int


def normalize_rows(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or not len(matrix):
        raise ValueError("values must be a non-empty matrix")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized: np.ndarray[Any, Any] = matrix / np.maximum(norms, 1e-12)
    return normalized


def verification_metrics(
    positive_scores: np.ndarray[Any, Any],
    negative_scores: np.ndarray[Any, Any],
    *,
    far_target: float,
) -> VerificationMetrics:
    positive = np.asarray(positive_scores, dtype=np.float64).reshape(-1)
    negative = np.asarray(negative_scores, dtype=np.float64).reshape(-1)
    if not len(positive) or not len(negative):
        raise ValueError("verification requires positive and negative pairs")
    if not 0 <= far_target <= 1:
        raise ValueError("far_target must be between zero and one")
    labels = np.concatenate((np.ones(len(positive)), np.zeros(len(negative))))
    scores = np.concatenate((positive, negative))
    auc = float(roc_auc_score(labels, scores))
    false_accept, true_accept, _ = roc_curve(labels, scores)
    eligible = true_accept[false_accept <= far_target]
    return VerificationMetrics(
        auc=auc,
        tar_at_far=float(np.max(eligible)) if len(eligible) else 0.0,
        far_target=far_target,
        positive_pairs=len(positive),
        negative_pairs=len(negative),
    )


def linear_cka(left: np.ndarray[Any, Any], right: np.ndarray[Any, Any]) -> float:
    x = np.asarray(left, dtype=np.float64)
    y = np.asarray(right, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or not len(x):
        raise ValueError("representations must be non-empty matrices with equal rows")
    x = x - np.mean(x, axis=0, keepdims=True)
    y = y - np.mean(y, axis=0, keepdims=True)
    cross = np.linalg.norm(x.T @ y, ord="fro") ** 2
    denominator = np.linalg.norm(x.T @ x, ord="fro") * np.linalg.norm(
        y.T @ y, ord="fro"
    )
    return float(cross / denominator) if denominator else 0.0


def bootstrap_mean_interval(
    values: np.ndarray[Any, Any], *, seed: int, samples: int, confidence: float = 0.95
) -> tuple[float, float]:
    observations = np.asarray(values, dtype=np.float64).reshape(-1)
    if not len(observations) or samples <= 0 or not 0 < confidence < 1:
        raise ValueError("invalid bootstrap input")
    rng = np.random.default_rng(seed)
    means = np.mean(
        rng.choice(observations, size=(samples, len(observations)), replace=True), axis=1
    )
    tail = (1 - confidence) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))
