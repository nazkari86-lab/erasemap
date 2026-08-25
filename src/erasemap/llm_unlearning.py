from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def mean(values: Sequence[float], *, name: str) -> float:
    if not values:
        raise ValueError(f"{name} must not be empty")
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{name} contains non-finite values")
    return math.fsum(values) / len(values)


def binary_auc(positive_scores: Sequence[float], negative_scores: Sequence[float]) -> float:
    """Exact Mann-Whitney AUC with half credit for tied scores."""
    if not positive_scores or not negative_scores:
        raise ValueError("AUC requires both positive and negative scores")
    wins = 0.0
    for positive in positive_scores:
        if not math.isfinite(positive):
            raise ValueError("positive AUC score must be finite")
        for negative in negative_scores:
            if not math.isfinite(negative):
                raise ValueError("negative AUC score must be finite")
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positive_scores) * len(negative_scores))


def score_trial(
    losses: Mapping[str, Mapping[str, Sequence[float]]],
    *,
    recurrence_after_reload: float,
) -> dict[str, float]:
    required_models = {"base", "target", "exact", "candidate", "candidate_reloaded"}
    required_sets = {
        "forget",
        "forget_perturbed",
        "holdout",
        "retain",
        "retain_perturbed",
        "world_facts",
    }
    if set(losses) != required_models:
        raise ValueError("loss matrix has an unexpected model set")
    for model_id, model_losses in losses.items():
        if set(model_losses) != required_sets:
            raise ValueError(f"loss matrix has an unexpected dataset set: {model_id}")

    averages = {
        f"{model_id}_{dataset_id}_nll": mean(
            [finite_float(value, name=f"{model_id}.{dataset_id}") for value in values],
            name=f"{model_id}.{dataset_id}",
        )
        for model_id, model_losses in losses.items()
        for dataset_id, values in model_losses.items()
    }
    exact_auc = binary_auc(
        [-finite_float(value, name="exact.forget") for value in losses["exact"]["forget"]],
        [-finite_float(value, name="exact.holdout") for value in losses["exact"]["holdout"]],
    )
    candidate_auc = binary_auc(
        [
            -finite_float(value, name="candidate.forget")
            for value in losses["candidate"]["forget"]
        ],
        [
            -finite_float(value, name="candidate.holdout")
            for value in losses["candidate"]["holdout"]
        ],
    )
    metrics = {
        **averages,
        "target_memorization_gain": averages["base_forget_nll"]
        - averages["target_forget_nll"],
        "exact_forgetting_lift": averages["exact_forget_nll"]
        - averages["target_forget_nll"],
        "candidate_forgetting_lift": averages["candidate_forget_nll"]
        - averages["target_forget_nll"],
        "candidate_exact_forget_nll_gap": abs(
            averages["candidate_forget_nll"] - averages["exact_forget_nll"]
        ),
        "candidate_exact_perturbed_nll_gap": abs(
            averages["candidate_forget_perturbed_nll"]
            - averages["exact_forget_perturbed_nll"]
        ),
        "candidate_exact_retain_nll_gap": abs(
            averages["candidate_retain_nll"] - averages["exact_retain_nll"]
        ),
        "exact_mia_auc": exact_auc,
        "candidate_mia_auc": candidate_auc,
        "candidate_exact_mia_auc_gap": abs(candidate_auc - exact_auc),
        "candidate_world_utility_nll_degradation": averages["candidate_world_facts_nll"]
        - averages["target_world_facts_nll"],
        "retained_recurrence_after_reload": finite_float(
            recurrence_after_reload, name="recurrence_after_reload"
        ),
    }
    return metrics


def compute_gates(
    trials: Sequence[Mapping[str, Any]], criteria: Mapping[str, object]
) -> dict[str, bool]:
    if not trials:
        raise ValueError("at least one trial is required")

    def values(name: str) -> list[float]:
        return [finite_float(trial["metrics"][name], name=name) for trial in trials]

    gates = {
        "target_memorization": min(values("target_memorization_gain"))
        >= finite_float(criteria["target_memorization_gain_min"], name="criterion"),
        "exact_reference_forgets": min(values("exact_forgetting_lift"))
        >= finite_float(criteria["exact_forgetting_lift_min"], name="criterion"),
        "candidate_forgets": min(values("candidate_forgetting_lift"))
        >= finite_float(criteria["candidate_forgetting_lift_min"], name="criterion"),
        "candidate_matches_exact_forget": max(values("candidate_exact_forget_nll_gap"))
        <= finite_float(criteria["candidate_exact_forget_nll_gap_max"], name="criterion"),
        "candidate_matches_exact_perturbed": max(
            values("candidate_exact_perturbed_nll_gap")
        )
        <= finite_float(
            criteria["candidate_exact_perturbed_nll_gap_max"], name="criterion"
        ),
        "candidate_preserves_retain": max(values("candidate_exact_retain_nll_gap"))
        <= finite_float(criteria["candidate_exact_retain_nll_gap_max"], name="criterion"),
        "candidate_matches_exact_membership": max(values("candidate_exact_mia_auc_gap"))
        <= finite_float(criteria["candidate_exact_mia_auc_gap_max"], name="criterion"),
        "candidate_preserves_world_utility": max(
            values("candidate_world_utility_nll_degradation")
        )
        <= finite_float(
            criteria["candidate_world_utility_nll_degradation_max"], name="criterion"
        ),
        "candidate_survives_reload_without_recurrence": max(
            values("retained_recurrence_after_reload")
        )
        <= finite_float(criteria["retained_recurrence_after_reload_max"], name="criterion"),
    }
    return gates


def summarize_trials(
    trials: Sequence[Mapping[str, Any]], criteria: Mapping[str, object]
) -> dict[str, object]:
    gates = compute_gates(trials, criteria)
    metric_names = tuple(str(name) for name in trials[0]["metrics"])
    aggregate = {
        name: {
            "mean": mean(
                [finite_float(trial["metrics"][name], name=name) for trial in trials],
                name=name,
            ),
            "min": min(finite_float(trial["metrics"][name], name=name) for trial in trials),
            "max": max(finite_float(trial["metrics"][name], name=name) for trial in trials),
        }
        for name in metric_names
    }
    return {
        "aggregate": aggregate,
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "gates": gates,
    }
