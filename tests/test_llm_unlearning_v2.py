from __future__ import annotations

import copy

import pytest

from erasemap.llm_unlearning_v2 import (
    compute_v2_gates,
    score_v2_trial,
    select_development_candidate,
    summarize_v2_trials,
    validate_evaluations,
)


def _evaluations() -> dict[str, dict[str, object]]:
    channels: dict[str, object] = {
        "forget_answer": [1.0, 1.1],
        "forget_paraphrase": [1.1, 1.2],
        "forget_perturbed": [[2.0, 2.1], [2.2, 2.3]],
        "holdout": [2.0, 2.1],
        "retain": [1.0, 1.1],
        "world_facts": [1.5, 1.6],
        "real_authors": [1.4, 1.5],
    }
    result = {
        model: copy.deepcopy(channels)
        for model in ("base", "target", "exact", "candidate", "candidate_reloaded")
    }
    result["base"]["forget_answer"] = [2.0, 2.1]
    result["exact"]["forget_answer"] = [1.8, 1.9]
    result["candidate"]["forget_answer"] = [1.72, 1.82]
    result["candidate_reloaded"]["forget_answer"] = [1.72, 1.82]
    result["exact"]["forget_paraphrase"] = [1.8, 1.9]
    result["candidate"]["forget_paraphrase"] = [1.75, 1.85]
    result["candidate_reloaded"]["forget_paraphrase"] = [1.75, 1.85]
    return result


def _criteria() -> dict[str, float]:
    return {
        "target_memorization_gain_min": 0.1,
        "exact_forgetting_lift_min": 0.05,
        "candidate_exact_normalized_recovery_min": 0.8,
        "candidate_exact_normalized_recovery_max": 1.25,
        "candidate_exact_paraphrase_nll_gap_max": 0.2,
        "candidate_exact_truth_margin_gap_max": 0.2,
        "candidate_exact_retain_nll_gap_max": 0.15,
        "candidate_world_utility_nll_degradation_max": 0.2,
        "candidate_real_author_nll_degradation_max": 0.2,
        "candidate_exact_mia_auc_gap_max": 0.1,
        "candidate_speedup_vs_exact_min": 1.5,
        "retained_recurrence_after_reload_max": 1e-6,
    }


def test_v2_scores_normalized_recovery_and_truth_margin() -> None:
    metrics = score_v2_trial(
        _evaluations(),
        recurrence_after_reload=0.0,
        candidate_runtime_seconds=10.0,
        exact_runtime_seconds=20.0,
    )
    assert metrics["candidate_exact_normalized_recovery"] == pytest.approx(0.9)
    assert metrics["candidate_speedup_vs_exact"] == 2.0
    assert metrics["candidate_exact_truth_margin_gap"] == pytest.approx(0.05)
    assert all(compute_v2_gates([{"metrics": metrics}], _criteria()).values())


def test_v2_rejects_malformed_perturbed_channel() -> None:
    values = _evaluations()
    values["candidate"]["forget_perturbed"] = [[1.0], [1.0, 2.0]]
    with pytest.raises(ValueError, match="rectangular"):
        validate_evaluations(values)


def test_v2_fails_when_candidate_recovers_only_v1_fraction() -> None:
    values = _evaluations()
    values["candidate"]["forget_answer"] = [1.3, 1.4]
    values["candidate_reloaded"]["forget_answer"] = [1.3, 1.4]
    metrics = score_v2_trial(
        values,
        recurrence_after_reload=0.0,
        candidate_runtime_seconds=10.0,
        exact_runtime_seconds=20.0,
    )
    result = summarize_v2_trials([{"metrics": metrics}], _criteria())
    assert result["decision"] == "FAIL"
    assert result["gates"]["candidate_recovers_exact_effect"] is False


def test_development_selection_is_deterministic_and_penalizes_violations() -> None:
    rows = [
        {
            "candidate_id": "fast-but-damaging",
            "aggregate": {
                "candidate_exact_normalized_recovery": {"min": 1.0},
                "candidate_world_utility_nll_degradation": {"max": 0.5},
                "candidate_real_author_nll_degradation": {"max": 0.1},
                "candidate_speedup_vs_exact": {"min": 4.0},
            },
        },
        {
            "candidate_id": "balanced",
            "aggregate": {
                "candidate_exact_normalized_recovery": {"min": 0.9},
                "candidate_world_utility_nll_degradation": {"max": 0.1},
                "candidate_real_author_nll_degradation": {"max": 0.1},
                "candidate_speedup_vs_exact": {"min": 2.0},
            },
        },
    ]
    assert select_development_candidate(rows, _criteria()) == "balanced"
