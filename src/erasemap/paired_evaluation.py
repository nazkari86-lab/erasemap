from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from erasemap.verification_metrics import bootstrap_mean_interval, normalize_rows


@dataclass(frozen=True, slots=True)
class PairedMetricResult:
    attack: str
    ci95: tuple[float, float]
    mean_difference: float
    trials: int


def split_embedding_mse(
    candidate: np.ndarray[Any, Any],
    exact: np.ndarray[Any, Any],
    forgotten_indices: np.ndarray[Any, Any],
    retained_indices: np.ndarray[Any, Any],
) -> tuple[float, float]:
    candidate_values = np.asarray(candidate, dtype=np.float64)
    exact_values = np.asarray(exact, dtype=np.float64)
    forgotten = np.asarray(forgotten_indices, dtype=np.int64).reshape(-1)
    retained = np.asarray(retained_indices, dtype=np.int64).reshape(-1)
    if candidate_values.shape != exact_values.shape or candidate_values.ndim != 2:
        raise ValueError("candidate and exact embeddings must be equally shaped matrices")
    if not len(forgotten) or not len(retained):
        raise ValueError("forgotten and retained index sets must be non-empty")
    forgotten_mse = float(np.mean((candidate_values[forgotten] - exact_values[forgotten]) ** 2))
    retained_mse = float(np.mean((candidate_values[retained] - exact_values[retained]) ** 2))
    return forgotten_mse, retained_mse


def identity_cohesion_scores(
    embeddings: np.ndarray[Any, Any], indices: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    values = normalize_rows(np.asarray(embeddings, dtype=np.float64))
    selected = np.asarray(indices, dtype=np.int64).reshape(-1)
    if len(selected) < 2:
        raise ValueError("identity cohesion requires at least two samples")
    if np.any(selected < 0) or np.any(selected >= len(values)):
        raise ValueError("identity cohesion index is out of range")
    similarities = values[selected] @ values[selected].T
    np.fill_diagonal(similarities, 0.0)
    scores: np.ndarray[Any, Any] = np.sum(similarities, axis=1) / (len(selected) - 1)
    return scores


def paired_attack_differences(
    trials: list[dict[str, Any]],
    attacks: tuple[str, ...],
    *,
    selective_method: str,
    exact_method: str,
    bootstrap_seed: int,
    bootstrap_samples: int,
) -> tuple[PairedMetricResult, ...]:
    indexed = {
        (int(row["seed"]), int(row["anonymous_forget_subject"]), str(row["method"])): row
        for row in trials
    }
    results: list[PairedMetricResult] = []
    trial_keys = sorted(
        (seed, subject)
        for seed, subject, method in indexed
        if method == selective_method
    )
    for attack in attacks:
        differences = np.asarray(
            [
                float(indexed[(seed, subject, selective_method)][attack])
                - float(indexed[(seed, subject, exact_method)][attack])
                for seed, subject in trial_keys
            ],
            dtype=np.float64,
        )
        interval = bootstrap_mean_interval(
            differences, seed=bootstrap_seed, samples=bootstrap_samples
        )
        results.append(
            PairedMetricResult(
                attack,
                interval,
                float(np.mean(differences)),
                len(differences),
            )
        )
    return tuple(results)
