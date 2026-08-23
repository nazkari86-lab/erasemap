from __future__ import annotations

from dataclasses import dataclass

from erasemap.ghostgraph import (
    MAX_EXPERIMENTS,
    MAX_HYPOTHESES,
    DiscoveryExperiment,
    GraphHypothesis,
    predict_trace,
)


@dataclass(frozen=True, slots=True, order=True)
class ExperimentPartition:
    trace_bits: tuple[bool, ...]
    graph_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, order=True)
class PlannerScore:
    largest_bucket: int
    squared_bucket_sum: int
    declared_cost: int
    experiment_id: str


@dataclass(frozen=True, slots=True)
class PlannerCandidate:
    experiment_id: str
    partitions: tuple[ExperimentPartition, ...]
    score: PlannerScore
    separates: bool


@dataclass(frozen=True, slots=True)
class PlannerCertificate:
    surviving_graph_ids: tuple[str, ...]
    used_experiment_ids: tuple[str, ...]
    candidates: tuple[PlannerCandidate, ...]
    selected_experiment_id: str | None
    selected_score: PlannerScore | None


def select_next_experiment(
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
    *,
    used_ids: tuple[str, ...],
) -> PlannerCertificate:
    if not hypotheses:
        raise ValueError("at least one hypothesis is required")
    if len(hypotheses) > MAX_HYPOTHESES:
        raise ValueError(f"at most {MAX_HYPOTHESES} hypotheses are supported")
    if len(experiments) > MAX_EXPERIMENTS:
        raise ValueError(f"at most {MAX_EXPERIMENTS} experiments are supported")
    graph_ids = tuple(graph.graph_id for graph in hypotheses)
    experiment_ids = tuple(experiment.experiment_id for experiment in experiments)
    if len(set(graph_ids)) != len(graph_ids):
        raise ValueError("graph hypothesis IDs must be unique")
    if len(set(experiment_ids)) != len(experiment_ids):
        raise ValueError("experiment IDs must be unique")
    if len(set(used_ids)) != len(used_ids):
        raise ValueError("used experiment IDs must be unique")
    unknown_used = set(used_ids) - set(experiment_ids)
    if unknown_used:
        raise ValueError(f"unknown used experiment ID: {min(unknown_used)}")

    ordered_hypotheses = tuple(sorted(hypotheses, key=lambda graph: graph.graph_id))
    ordered_experiments = tuple(sorted(experiments, key=lambda item: item.experiment_id))
    used = frozenset(used_ids)
    candidates = tuple(
        _candidate(ordered_hypotheses, experiment)
        for experiment in ordered_experiments
        if experiment.experiment_id not in used
    )
    separating = tuple(candidate for candidate in candidates if candidate.separates)
    selected = min(separating, key=lambda candidate: candidate.score) if separating else None
    return PlannerCertificate(
        surviving_graph_ids=tuple(graph.graph_id for graph in ordered_hypotheses),
        used_experiment_ids=tuple(sorted(used)),
        candidates=candidates,
        selected_experiment_id=None if selected is None else selected.experiment_id,
        selected_score=None if selected is None else selected.score,
    )


def _candidate(
    hypotheses: tuple[GraphHypothesis, ...],
    experiment: DiscoveryExperiment,
) -> PlannerCandidate:
    buckets: dict[tuple[bool, ...], list[str]] = {}
    for graph in hypotheses:
        trace = predict_trace(graph, experiment)
        buckets.setdefault(trace.bits, []).append(graph.graph_id)
    partitions = tuple(
        ExperimentPartition(trace_bits, tuple(graph_ids))
        for trace_bits, graph_ids in sorted(buckets.items())
    )
    sizes = tuple(len(partition.graph_ids) for partition in partitions)
    score = PlannerScore(
        largest_bucket=max(sizes),
        squared_bucket_sum=sum(size * size for size in sizes),
        declared_cost=experiment.declared_cost,
        experiment_id=experiment.experiment_id,
    )
    return PlannerCandidate(
        experiment_id=experiment.experiment_id,
        partitions=partitions,
        score=score,
        separates=len(partitions) > 1,
    )
