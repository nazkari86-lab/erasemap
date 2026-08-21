from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class TrialOutcome:
    truth_positive: bool
    declared_complete: bool
    runtime_ms: float
    remediation_cost: float
    truth_artifact_ids: frozenset[str] = frozenset()
    detected_artifact_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.runtime_ms < 0 or self.remediation_cost < 0:
            raise ValueError("runtime and remediation cost cannot be negative")


Interval = tuple[float, float]


@dataclass(frozen=True, slots=True)
class AggregateReport:
    trials: int
    positive_trials: int
    true_positive: int
    false_negative: int
    true_negative: int
    false_positive: int
    false_complete_rate: float | None
    recall: float | None
    precision: float | None
    false_alarm_rate: float | None
    exact_node_recall: float | None
    mean_runtime_ms: float
    mean_remediation_cost: float
    intervals: Mapping[str, Interval | None]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _values(outcomes: Sequence[TrialOutcome]) -> dict[str, float | None]:
    true_positive = sum(item.truth_positive and not item.declared_complete for item in outcomes)
    false_negative = sum(item.truth_positive and item.declared_complete for item in outcomes)
    true_negative = sum(not item.truth_positive and item.declared_complete for item in outcomes)
    false_positive = sum(
        not item.truth_positive and not item.declared_complete for item in outcomes
    )
    truth_nodes = sum(len(item.truth_artifact_ids) for item in outcomes)
    found_nodes = sum(
        len(item.truth_artifact_ids & item.detected_artifact_ids) for item in outcomes
    )
    return {
        "false_complete_rate": _ratio(false_negative, true_positive + false_negative),
        "recall": _ratio(true_positive, true_positive + false_negative),
        "precision": _ratio(true_positive, true_positive + false_positive),
        "false_alarm_rate": _ratio(false_positive, false_positive + true_negative),
        "exact_node_recall": _ratio(found_nodes, truth_nodes),
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * probability)
    return ordered[index]


def _bootstrap_interval(
    outcomes: Sequence[TrialOutcome],
    metric: Callable[[Sequence[TrialOutcome]], float | None],
    *,
    rng: random.Random,
    samples: int,
) -> Interval | None:
    if metric(outcomes) is None:
        return None
    estimates: list[float] = []
    for _ in range(samples):
        sample = [outcomes[rng.randrange(len(outcomes))] for _ in outcomes]
        estimate = metric(sample)
        if estimate is not None:
            estimates.append(estimate)
    if not estimates:
        return None
    return (_percentile(estimates, 0.025), _percentile(estimates, 0.975))


def _metric_value(
    outcomes: Sequence[TrialOutcome], *, name: str
) -> float | None:
    return _values(outcomes)[name]


def aggregate_outcomes(
    outcomes: Sequence[TrialOutcome],
    *,
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 1_000,
) -> AggregateReport:
    if not outcomes:
        raise ValueError("at least one trial outcome is required")
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")

    values = _values(outcomes)
    metric_names = tuple(values)
    rng = random.Random(bootstrap_seed)
    intervals = {
        name: _bootstrap_interval(
            outcomes,
            partial(_metric_value, name=name),
            rng=rng,
            samples=bootstrap_samples,
        )
        for name in metric_names
    }
    true_positive = sum(item.truth_positive and not item.declared_complete for item in outcomes)
    false_negative = sum(item.truth_positive and item.declared_complete for item in outcomes)
    true_negative = sum(not item.truth_positive and item.declared_complete for item in outcomes)
    false_positive = sum(
        not item.truth_positive and not item.declared_complete for item in outcomes
    )
    count = len(outcomes)
    return AggregateReport(
        trials=count,
        positive_trials=true_positive + false_negative,
        true_positive=true_positive,
        false_negative=false_negative,
        true_negative=true_negative,
        false_positive=false_positive,
        false_complete_rate=values["false_complete_rate"],
        recall=values["recall"],
        precision=values["precision"],
        false_alarm_rate=values["false_alarm_rate"],
        exact_node_recall=values["exact_node_recall"],
        mean_runtime_ms=sum(item.runtime_ms for item in outcomes) / count,
        mean_remediation_cost=sum(item.remediation_cost for item in outcomes) / count,
        intervals=MappingProxyType(intervals),
    )
