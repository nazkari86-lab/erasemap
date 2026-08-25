from __future__ import annotations

import random
from dataclasses import dataclass

from erasemap.ghostgraph import DiscoveryExperiment, GraphHypothesis, predict_trace
from erasemap.ghostgraph_action import (
    ActionSignature,
    GlobalPolicyCertificate,
    action_signature,
)
from erasemap.ghostgraph_planner import select_next_experiment


@dataclass(frozen=True, slots=True)
class StrategyOutcome:
    verdict: str
    predicted_action: ActionSignature | None
    executed_experiment_ids: tuple[str, ...]
    probe_cost: int


def evaluate_strategy(
    strategy: str,
    truth: GraphHypothesis,
    catalogue: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
    *,
    global_policy: GlobalPolicyCertificate,
    random_seed: int,
) -> StrategyOutcome:
    if strategy == "global-action-policy":
        return _global_policy(truth, experiments, global_policy)
    if strategy == "one-step-minimax":
        return _adaptive(
            truth,
            catalogue,
            experiments,
            strategy="minimax",
            random_seed=random_seed,
            terminal_exact=False,
        )
    if strategy == "exact-graph-minimax-ablation":
        return _adaptive(
            truth,
            catalogue,
            experiments,
            strategy="minimax",
            random_seed=random_seed,
            terminal_exact=True,
        )
    if strategy == "greedy-separated-pairs":
        return _adaptive(
            truth,
            catalogue,
            experiments,
            strategy="greedy",
            random_seed=random_seed,
            terminal_exact=False,
        )
    if strategy == "frozen-random":
        return _adaptive(
            truth,
            catalogue,
            experiments,
            strategy="random",
            random_seed=random_seed,
            terminal_exact=False,
        )
    if strategy == "nonadaptive-exhaustive":
        return _exhaustive(truth, catalogue, experiments, sink_only=False)
    if strategy == "sink-only-ablation":
        return _exhaustive(truth, catalogue, experiments, sink_only=True)
    if strategy == "passive-lineage-ablation":
        predicted = action_signature(sorted(catalogue, key=lambda item: item.graph_id)[0])
        return StrategyOutcome(
            "ACTION_IDENTIFIED",
            predicted,
            (),
            0,
        )
    raise ValueError(f"unknown GhostGraph-T strategy: {strategy}")


def _global_policy(
    truth: GraphHypothesis,
    experiments: tuple[DiscoveryExperiment, ...],
    certificate: GlobalPolicyCertificate,
) -> StrategyOutcome:
    decision_by_state = {
        (item.surviving_graph_ids, item.remaining_experiment_ids): item
        for item in certificate.decisions
    }
    experiment_by_id = {item.experiment_id: item for item in experiments}
    graph_ids = certificate.root_graph_ids
    remaining = tuple(sorted(experiment_by_id))
    executed: list[str] = []
    cost = 0
    while True:
        decision = decision_by_state[(graph_ids, remaining)]
        if decision.terminal_action is not None:
            return StrategyOutcome(
                "ACTION_IDENTIFIED",
                decision.terminal_action,
                tuple(executed),
                cost,
            )
        if decision.selected_experiment_id is None:
            return StrategyOutcome("UNVERIFIED", None, tuple(executed), cost)
        experiment = experiment_by_id[decision.selected_experiment_id]
        bits = predict_trace(truth, experiment).bits
        executed.append(experiment.experiment_id)
        cost += experiment.declared_cost
        branch = next((item for item in decision.branches if item.trace_bits == bits), None)
        if branch is None:
            return StrategyOutcome("OUT_OF_HYPOTHESIS", None, tuple(executed), cost)
        graph_ids = branch.surviving_graph_ids
        remaining = tuple(item for item in remaining if item != experiment.experiment_id)


def _adaptive(
    truth: GraphHypothesis,
    catalogue: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
    *,
    strategy: str,
    random_seed: int,
    terminal_exact: bool,
) -> StrategyOutcome:
    survivors = tuple(sorted(catalogue, key=lambda item: item.graph_id))
    unused = tuple(sorted(experiments, key=lambda item: item.experiment_id))
    executed: list[str] = []
    cost = 0
    rng = random.Random(random_seed)
    def terminal() -> bool:
        if terminal_exact:
            return len(survivors) == 1
        return len({action_signature(item) for item in survivors}) == 1

    while not terminal():
        separating = tuple(
            experiment
            for experiment in unused
            if len({predict_trace(item, experiment).bits for item in survivors}) > 1
        )
        if not separating:
            return StrategyOutcome("UNVERIFIED", None, tuple(executed), cost)
        if strategy == "minimax":
            certificate = select_next_experiment(
                survivors,
                experiments,
                used_ids=tuple(executed),
            )
            selected_id = certificate.selected_experiment_id
            if selected_id is None:
                return StrategyOutcome("UNVERIFIED", None, tuple(executed), cost)
            selected = next(item for item in experiments if item.experiment_id == selected_id)
        elif strategy == "greedy":
            selected = max(
                separating,
                key=lambda item: (
                    _separated_pairs(survivors, item),
                    -item.declared_cost,
                    tuple(-ord(char) for char in item.experiment_id),
                ),
            )
        else:
            selected = separating[rng.randrange(len(separating))]
        observed = predict_trace(truth, selected).bits
        survivors = tuple(
            item for item in survivors if predict_trace(item, selected).bits == observed
        )
        executed.append(selected.experiment_id)
        cost += selected.declared_cost
        unused = tuple(item for item in unused if item.experiment_id != selected.experiment_id)
        if not survivors:
            return StrategyOutcome("OUT_OF_HYPOTHESIS", None, tuple(executed), cost)
    predicted = action_signature(survivors[0])
    return StrategyOutcome("ACTION_IDENTIFIED", predicted, tuple(executed), cost)


def _exhaustive(
    truth: GraphHypothesis,
    catalogue: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
    *,
    sink_only: bool,
) -> StrategyOutcome:
    survivors = tuple(catalogue)
    for experiment in experiments:
        observed = _observable_bits(truth, experiment, sink_only=sink_only)
        survivors = tuple(
            graph
            for graph in survivors
            if _observable_bits(graph, experiment, sink_only=sink_only) == observed
        )
    cost = sum(item.declared_cost for item in experiments)
    executed = tuple(item.experiment_id for item in experiments)
    if not survivors:
        return StrategyOutcome("OUT_OF_HYPOTHESIS", None, executed, cost)
    signatures = {action_signature(item) for item in survivors}
    if len(signatures) != 1:
        return StrategyOutcome("UNVERIFIED", None, executed, cost)
    return StrategyOutcome("ACTION_IDENTIFIED", next(iter(signatures)), executed, cost)


def _observable_bits(
    graph: GraphHypothesis,
    experiment: DiscoveryExperiment,
    *,
    sink_only: bool,
) -> tuple[bool, ...]:
    trace = predict_trace(graph, experiment)
    if not sink_only:
        return trace.bits
    sink_index = trace.checkpoint_node_ids.index("sink")
    return tuple(
        trace.bits[bucket * len(trace.checkpoint_node_ids) + sink_index]
        for bucket in range(trace.time_buckets)
    )


def _separated_pairs(
    hypotheses: tuple[GraphHypothesis, ...],
    experiment: DiscoveryExperiment,
) -> int:
    buckets: dict[tuple[bool, ...], int] = {}
    for graph in hypotheses:
        bits = predict_trace(graph, experiment).bits
        buckets[bits] = buckets.get(bits, 0) + 1
    total = len(hypotheses) * (len(hypotheses) - 1) // 2
    unseparated = sum(size * (size - 1) // 2 for size in buckets.values())
    return total - unseparated
