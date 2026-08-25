from __future__ import annotations

import math

import pytest

from erasemap.llm_unlearning import binary_auc, compute_gates, score_trial, summarize_trials


def _losses() -> dict[str, dict[str, list[float]]]:
    datasets = {
        "forget": [1.0, 1.2],
        "forget_perturbed": [1.2, 1.4],
        "holdout": [2.5, 2.7],
        "retain": [1.0, 1.1],
        "retain_perturbed": [1.2, 1.3],
        "world_facts": [1.5, 1.6],
    }
    losses = {name: {key: list(value) for key, value in datasets.items()} for name in (
        "base",
        "target",
        "exact",
        "candidate",
        "candidate_reloaded",
    )}
    losses["base"]["forget"] = [2.0, 2.2]
    losses["target"]["forget"] = [1.0, 1.2]
    losses["exact"]["forget"] = [1.8, 2.0]
    losses["candidate"]["forget"] = [1.75, 1.95]
    losses["candidate_reloaded"]["forget"] = [1.75, 1.95]
    losses["exact"]["forget_perturbed"] = [1.8, 2.0]
    losses["candidate"]["forget_perturbed"] = [1.75, 1.95]
    losses["candidate_reloaded"]["forget_perturbed"] = [1.75, 1.95]
    return losses


def _criteria() -> dict[str, float]:
    return {
        "target_memorization_gain_min": 0.1,
        "exact_forgetting_lift_min": 0.05,
        "candidate_forgetting_lift_min": 0.05,
        "candidate_exact_forget_nll_gap_max": 0.3,
        "candidate_exact_perturbed_nll_gap_max": 0.35,
        "candidate_exact_retain_nll_gap_max": 0.15,
        "candidate_exact_mia_auc_gap_max": 0.1,
        "candidate_world_utility_nll_degradation_max": 0.2,
        "retained_recurrence_after_reload_max": 0.000001,
    }


def test_binary_auc_handles_order_and_ties() -> None:
    assert binary_auc([2.0, 3.0], [0.0, 1.0]) == 1.0
    assert binary_auc([0.0], [1.0]) == 0.0
    assert binary_auc([1.0], [1.0]) == 0.5


def test_trial_metrics_and_gates_are_recomputed() -> None:
    metrics = score_trial(_losses(), recurrence_after_reload=0.0)
    trial = {"metrics": metrics, "seed": 20260825}
    gates = compute_gates([trial], _criteria())
    assert all(gates.values())
    summary = summarize_trials([trial], _criteria())
    assert summary["decision"] == "PASS"
    assert summary["aggregate"]["candidate_exact_forget_nll_gap"]["max"] == pytest.approx(
        0.05
    )


def test_gate_failure_is_preserved() -> None:
    metrics = score_trial(_losses(), recurrence_after_reload=0.0)
    metrics["candidate_exact_retain_nll_gap"] = 1.0
    summary = summarize_trials([{"metrics": metrics}], _criteria())
    assert summary["decision"] == "FAIL"
    assert summary["gates"]["candidate_preserves_retain"] is False


def test_scoring_rejects_non_finite_and_wrong_matrix() -> None:
    losses = _losses()
    losses["candidate"]["forget"][0] = math.nan
    with pytest.raises(ValueError, match="finite"):
        score_trial(losses, recurrence_after_reload=0.0)
    losses = _losses()
    del losses["base"]
    with pytest.raises(ValueError, match="model set"):
        score_trial(losses, recurrence_after_reload=0.0)
