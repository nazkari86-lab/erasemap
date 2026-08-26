from __future__ import annotations

import math
import random

import pytest

from erasemap.llm_unlearning_v3 import (
    NoRobustCandidateError,
    PathPoint,
    gate_margins,
    robust_intervals,
    select_robust_point,
    summarize_path_point,
)


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


def _metrics(**changes: float) -> dict[str, float]:
    result = {
        "target_memorization_gain": 0.5,
        "exact_forgetting_lift": 0.2,
        "candidate_exact_normalized_recovery": 1.0,
        "candidate_exact_paraphrase_nll_gap": 0.05,
        "candidate_exact_truth_margin_gap": 0.05,
        "candidate_exact_retain_nll_gap": 0.05,
        "candidate_world_utility_nll_degradation": 0.0,
        "candidate_real_author_nll_degradation": 0.0,
        "candidate_exact_mia_auc_gap": 0.02,
        "candidate_speedup_vs_exact": 4.0,
        "retained_recurrence_after_reload": 0.0,
    }
    result.update(changes)
    return result


def _point(
    path_id: str,
    alpha: float,
    *,
    feasible: bool = True,
    margin: float = 0.2,
    speedup: float = 5.0,
    gap: float = 0.08,
) -> PathPoint:
    return PathPoint(path_id, alpha, feasible, margin, speedup, gap)


def test_robust_intervals_require_three_contiguous_points() -> None:
    points = [
        _point("p", 0.10, feasible=False),
        _point("p", 0.20),
        _point("p", 0.30),
        _point("p", 0.40),
        _point("p", 0.50, feasible=False),
    ]
    intervals = robust_intervals(points, minimum_width=3)
    assert [[point.alpha for point in row] for row in intervals] == [[0.2, 0.3, 0.4]]


def test_two_feasible_points_are_not_selectable() -> None:
    assert robust_intervals([_point("p", 0.1), _point("p", 0.2)], minimum_width=3) == []


def test_intervals_do_not_join_different_paths() -> None:
    points = [_point("a", 0.1), _point("a", 0.2), _point("b", 0.3)]
    assert robust_intervals(points, minimum_width=3) == []


def test_selector_prefers_width_then_uses_lower_medoid() -> None:
    selected = select_robust_point(
        {
            "a": [_point("a", value, margin=0.2) for value in (0.1, 0.2, 0.3)],
            "b": [_point("b", value, margin=0.1) for value in (0.1, 0.2, 0.3, 0.4)],
        },
        minimum_width=3,
    )
    assert (selected.path_id, selected.alpha) == ("b", 0.2)


def test_selector_is_order_invariant_and_uses_declared_ties() -> None:
    rows = [
        _point("b", value, margin=0.3, gap=0.01, speedup=9.0)
        for value in (0.1, 0.2, 0.3)
    ] + [
        _point("a", value, margin=0.3, gap=0.01, speedup=9.0)
        for value in (0.1, 0.2, 0.3)
    ]
    random.Random(7).shuffle(rows)
    selected = select_robust_point(
        {
            "b": [row for row in rows if row.path_id == "b"],
            "a": [row for row in rows if row.path_id == "a"],
        },
        minimum_width=3,
    )
    assert selected.path_id == "a"


def test_selector_rejects_no_robust_candidate() -> None:
    with pytest.raises(NoRobustCandidateError, match="no contiguous"):
        select_robust_point({"a": [_point("a", 0.1)]}, minimum_width=3)


def test_gate_margins_are_positive_only_inside_every_gate() -> None:
    margins = gate_margins(_metrics(), _criteria())
    assert set(margins) == {
        "candidate_does_not_overscrub",
        "candidate_is_faster",
        "candidate_matches_exact_membership",
        "candidate_matches_exact_paraphrase",
        "candidate_matches_exact_truth_margin",
        "candidate_preserves_real_authors",
        "candidate_preserves_retain",
        "candidate_preserves_world_utility",
        "candidate_recovers_exact_effect",
        "candidate_survives_reload_without_recurrence",
        "exact_reference_forgets",
        "target_memorization",
    }
    assert min(margins.values()) >= 0
    failed = gate_margins(
        _metrics(candidate_exact_normalized_recovery=1.5), _criteria()
    )
    assert failed["candidate_does_not_overscrub"] < 0


def test_summarize_path_point_uses_worst_trial() -> None:
    point = summarize_path_point(
        "path", 0.25,
        [{"metrics": _metrics()}, {"metrics": _metrics(candidate_exact_retain_nll_gap=0.16)}],
        _criteria(),
    )
    assert point.feasible is False
    assert point.minimum_margin < 0
    assert point.minimum_speedup == 4.0
    assert point.worst_exact_gap == pytest.approx(0.16 / 0.15)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_metric_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        gate_margins(_metrics(candidate_exact_retain_nll_gap=value), _criteria())
