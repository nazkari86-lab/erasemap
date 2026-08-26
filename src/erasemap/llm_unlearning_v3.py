from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter

from erasemap.llm_unlearning import finite_float


class NoRobustCandidateError(ValueError):
    """Raised when development contains no preregistered robust interval."""


@dataclass(frozen=True, slots=True)
class PathPoint:
    path_id: str
    alpha: float
    feasible: bool
    minimum_margin: float
    minimum_speedup: float
    worst_exact_gap: float

    def __post_init__(self) -> None:
        if not self.path_id:
            raise ValueError("path_id must be non-empty")
        for name in ("alpha", "minimum_margin", "minimum_speedup", "worst_exact_gap"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        if self.minimum_speedup <= 0:
            raise ValueError("minimum_speedup must be positive")
        if self.worst_exact_gap < 0:
            raise ValueError("worst_exact_gap must be non-negative")


_LOWER_GATES = {
    "target_memorization": ("target_memorization_gain", "target_memorization_gain_min"),
    "exact_reference_forgets": ("exact_forgetting_lift", "exact_forgetting_lift_min"),
    "candidate_recovers_exact_effect": (
        "candidate_exact_normalized_recovery",
        "candidate_exact_normalized_recovery_min",
    ),
    "candidate_is_faster": ("candidate_speedup_vs_exact", "candidate_speedup_vs_exact_min"),
}

_UPPER_GATES = {
    "candidate_does_not_overscrub": (
        "candidate_exact_normalized_recovery",
        "candidate_exact_normalized_recovery_max",
    ),
    "candidate_matches_exact_paraphrase": (
        "candidate_exact_paraphrase_nll_gap",
        "candidate_exact_paraphrase_nll_gap_max",
    ),
    "candidate_matches_exact_truth_margin": (
        "candidate_exact_truth_margin_gap",
        "candidate_exact_truth_margin_gap_max",
    ),
    "candidate_preserves_retain": (
        "candidate_exact_retain_nll_gap",
        "candidate_exact_retain_nll_gap_max",
    ),
    "candidate_preserves_world_utility": (
        "candidate_world_utility_nll_degradation",
        "candidate_world_utility_nll_degradation_max",
    ),
    "candidate_preserves_real_authors": (
        "candidate_real_author_nll_degradation",
        "candidate_real_author_nll_degradation_max",
    ),
    "candidate_matches_exact_membership": (
        "candidate_exact_mia_auc_gap",
        "candidate_exact_mia_auc_gap_max",
    ),
    "candidate_survives_reload_without_recurrence": (
        "retained_recurrence_after_reload",
        "retained_recurrence_after_reload_max",
    ),
}

_EXACT_GAPS = (
    ("candidate_exact_paraphrase_nll_gap", "candidate_exact_paraphrase_nll_gap_max"),
    ("candidate_exact_truth_margin_gap", "candidate_exact_truth_margin_gap_max"),
    ("candidate_exact_retain_nll_gap", "candidate_exact_retain_nll_gap_max"),
    ("candidate_exact_mia_auc_gap", "candidate_exact_mia_auc_gap_max"),
)


def _scale(threshold: float) -> float:
    return max(abs(threshold), 1e-12)


def gate_margins(
    metrics: Mapping[str, object], criteria: Mapping[str, object]
) -> dict[str, float]:
    """Return normalized signed margins; non-negative means the gate passes."""
    margins: dict[str, float] = {}
    for gate, (metric_name, criterion_name) in _LOWER_GATES.items():
        value = finite_float(metrics[metric_name], name=metric_name)
        threshold = finite_float(criteria[criterion_name], name=criterion_name)
        margins[gate] = (value - threshold) / _scale(threshold)
    for gate, (metric_name, criterion_name) in _UPPER_GATES.items():
        value = finite_float(metrics[metric_name], name=metric_name)
        threshold = finite_float(criteria[criterion_name], name=criterion_name)
        margins[gate] = (threshold - value) / _scale(threshold)
    return dict(sorted(margins.items()))


def _normalized_exact_gap(
    metrics: Mapping[str, object], criteria: Mapping[str, object]
) -> float:
    return max(
        finite_float(metrics[metric_name], name=metric_name)
        / _scale(finite_float(criteria[criterion_name], name=criterion_name))
        for metric_name, criterion_name in _EXACT_GAPS
    )


def summarize_path_point(
    path_id: str,
    alpha: float,
    trials: Sequence[Mapping[str, object]],
    criteria: Mapping[str, object],
) -> PathPoint:
    if not trials:
        raise ValueError("at least one development trial is required")
    trial_margins: list[dict[str, float]] = []
    speedups: list[float] = []
    exact_gaps: list[float] = []
    for trial in trials:
        raw_metrics = trial.get("metrics")
        if not isinstance(raw_metrics, Mapping):
            raise ValueError("trial metrics must be a mapping")
        trial_margins.append(gate_margins(raw_metrics, criteria))
        speedups.append(
            finite_float(raw_metrics["candidate_speedup_vs_exact"], name="speedup")
        )
        exact_gaps.append(_normalized_exact_gap(raw_metrics, criteria))
    minimum_margin = min(value for row in trial_margins for value in row.values())
    return PathPoint(
        path_id=path_id,
        alpha=alpha,
        feasible=minimum_margin >= 0.0,
        minimum_margin=minimum_margin,
        minimum_speedup=min(speedups),
        worst_exact_gap=max(exact_gaps),
    )


def robust_intervals(
    points: Sequence[PathPoint], *, minimum_width: int
) -> list[list[PathPoint]]:
    if minimum_width < 1:
        raise ValueError("minimum_width must be positive")
    seen: set[tuple[str, float]] = set()
    for point in points:
        identity = (point.path_id, point.alpha)
        if identity in seen:
            raise ValueError("duplicate path point")
        seen.add(identity)
    ordered = sorted(points, key=attrgetter("path_id", "alpha"))
    intervals: list[list[PathPoint]] = []
    for _, path_rows_iter in groupby(ordered, key=attrgetter("path_id")):
        current: list[PathPoint] = []
        for point in path_rows_iter:
            if point.feasible:
                current.append(point)
            else:
                if len(current) >= minimum_width:
                    intervals.append(current)
                current = []
        if len(current) >= minimum_width:
            intervals.append(current)
    return intervals


def select_robust_point(
    points_by_path: Mapping[str, Sequence[PathPoint]], *, minimum_width: int
) -> PathPoint:
    points: list[PathPoint] = []
    for path_id, rows in points_by_path.items():
        if any(point.path_id != path_id for point in rows):
            raise ValueError("path point is stored under a different path id")
        points.extend(rows)
    intervals = robust_intervals(points, minimum_width=minimum_width)
    if not intervals:
        raise NoRobustCandidateError("no contiguous feasible alpha interval")
    ranked = sorted(
        intervals,
        key=lambda row: (
            -len(row),
            -min(point.minimum_margin for point in row),
            max(point.worst_exact_gap for point in row),
            -min(point.minimum_speedup for point in row),
            row[0].path_id,
        ),
    )
    winner = ranked[0]
    return winner[(len(winner) - 1) // 2]
