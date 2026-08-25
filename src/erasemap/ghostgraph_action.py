from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from erasemap.ghostgraph import (
    DiscoveryExperiment,
    GraphHypothesis,
    predict_trace,
    relevant_signature,
)

MAX_GLOBAL_HYPOTHESES = 16
MAX_GLOBAL_EXPERIMENTS = 16


@dataclass(frozen=True, slots=True, order=True)
class ActionSignature:
    controllable: bool
    minimum_size: int | None
    minimal_control_sets: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True, order=True)
class IndistinguishableActionPair:
    left_graph_id: str
    right_graph_id: str
    left_action: ActionSignature
    right_action: ActionSignature
    shared_trace_vector: tuple[tuple[bool, ...], ...]


@dataclass(frozen=True, slots=True)
class IdentifiabilityReport:
    identifiable: bool
    action_class_count: int
    information_lower_bound_probes: int | None
    maximum_query_outcomes: int
    witnesses: tuple[IndistinguishableActionPair, ...]


@dataclass(frozen=True, slots=True, order=True)
class PolicyBranch:
    trace_bits: tuple[bool, ...]
    surviving_graph_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    surviving_graph_ids: tuple[str, ...]
    remaining_experiment_ids: tuple[str, ...]
    action_class_count: int
    selected_experiment_id: str | None
    worst_case_cost: int | None
    worst_case_probes: int | None
    terminal_action: ActionSignature | None
    branches: tuple[PolicyBranch, ...]


@dataclass(frozen=True, slots=True)
class GlobalPolicyCertificate:
    identifiable: bool
    root_graph_ids: tuple[str, ...]
    root_worst_case_cost: int | None
    root_worst_case_probes: int | None
    decisions: tuple[PolicyDecision, ...]
    impossibility_witnesses: tuple[IndistinguishableActionPair, ...]


def action_signature(graph: GraphHypothesis) -> ActionSignature:
    signature = relevant_signature(graph)
    if not signature.edge_paths:
        return ActionSignature(True, 0, ((),))
    if any(not path for path in signature.edge_paths):
        return ActionSignature(False, None, ())

    operation_by_edge = {edge.edge_id: edge.operation_id for edge in graph.edges}
    path_operations = tuple(
        frozenset(operation_by_edge[edge_id] for edge_id in path)
        for path in signature.edge_paths
    )
    operations = tuple(sorted(set().union(*path_operations)))
    for size in range(1, len(operations) + 1):
        controls = tuple(
            selected
            for selected in combinations(operations, size)
            if all(set(selected) & path for path in path_operations)
        )
        if controls:
            return ActionSignature(True, size, controls)
    return ActionSignature(False, None, ())


def assess_action_identifiability(
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
) -> IdentifiabilityReport:
    ordered_graphs, ordered_experiments = _validated_inputs(hypotheses, experiments)
    traces = {
        graph.graph_id: tuple(
            predict_trace(graph, experiment).bits for experiment in ordered_experiments
        )
        for graph in ordered_graphs
    }
    actions = {graph.graph_id: action_signature(graph) for graph in ordered_graphs}
    witnesses = tuple(
        IndistinguishableActionPair(
            left.graph_id,
            right.graph_id,
            actions[left.graph_id],
            actions[right.graph_id],
            traces[left.graph_id],
        )
        for left, right in combinations(ordered_graphs, 2)
        if actions[left.graph_id] != actions[right.graph_id]
        and traces[left.graph_id] == traces[right.graph_id]
    )
    class_count = len(set(actions.values()))
    max_outcomes = max(
        (
            len({predict_trace(graph, experiment).bits for graph in ordered_graphs})
            for experiment in ordered_experiments
        ),
        default=1,
    )
    return IdentifiabilityReport(
        identifiable=not witnesses,
        action_class_count=class_count,
        information_lower_bound_probes=_information_lower_bound(class_count, max_outcomes),
        maximum_query_outcomes=max_outcomes,
        witnesses=witnesses,
    )


def build_global_policy(
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
) -> GlobalPolicyCertificate:
    ordered_graphs, ordered_experiments = _validated_inputs(hypotheses, experiments)
    if len(ordered_graphs) > MAX_GLOBAL_HYPOTHESES:
        raise ValueError(f"global policy supports at most {MAX_GLOBAL_HYPOTHESES} hypotheses")
    if len(ordered_experiments) > MAX_GLOBAL_EXPERIMENTS:
        raise ValueError(f"global policy supports at most {MAX_GLOBAL_EXPERIMENTS} experiments")

    graph_by_id = {graph.graph_id: graph for graph in ordered_graphs}
    experiment_by_id = {item.experiment_id: item for item in ordered_experiments}
    actions = {graph.graph_id: action_signature(graph) for graph in ordered_graphs}
    trace_table = {
        (graph.graph_id, experiment.experiment_id): predict_trace(graph, experiment).bits
        for graph in ordered_graphs
        for experiment in ordered_experiments
    }
    memo: dict[tuple[tuple[str, ...], tuple[str, ...]], PolicyDecision] = {}

    def solve(graph_ids: tuple[str, ...], remaining_ids: tuple[str, ...]) -> PolicyDecision:
        key = (graph_ids, remaining_ids)
        if key in memo:
            return memo[key]
        present_actions = {actions[graph_id] for graph_id in graph_ids}
        if len(present_actions) == 1:
            decision = PolicyDecision(
                graph_ids,
                remaining_ids,
                1,
                None,
                0,
                0,
                next(iter(present_actions)),
                (),
            )
            memo[key] = decision
            return decision

        candidates: list[tuple[tuple[int, int, int, str], PolicyDecision]] = []
        for experiment_id in remaining_ids:
            buckets: dict[tuple[bool, ...], list[str]] = {}
            for graph_id in graph_ids:
                buckets.setdefault(trace_table[(graph_id, experiment_id)], []).append(graph_id)
            if len(buckets) < 2:
                continue
            child_remaining = tuple(item for item in remaining_ids if item != experiment_id)
            children = tuple(
                (
                    bits,
                    solve(tuple(bucket_graph_ids), child_remaining),
                )
                for bits, bucket_graph_ids in sorted(buckets.items())
            )
            if any(child.worst_case_cost is None for _, child in children):
                continue
            experiment = experiment_by_id[experiment_id]
            exact_values = tuple(_exact_policy_value(child) for _, child in children)
            child_costs = tuple(item[0] for item in exact_values)
            child_probes = tuple(item[1] for item in exact_values)
            worst_cost = experiment.declared_cost + max(child_costs)
            worst_probes = 1 + max(child_probes)
            score = (worst_cost, worst_probes, sum(child_costs), experiment_id)
            candidates.append(
                (
                    score,
                    PolicyDecision(
                        graph_ids,
                        remaining_ids,
                        len(present_actions),
                        experiment_id,
                        worst_cost,
                        worst_probes,
                        None,
                        tuple(
                            PolicyBranch(bits, child.surviving_graph_ids)
                            for bits, child in children
                        ),
                    ),
                )
            )
        if candidates:
            decision = min(candidates, key=lambda item: item[0])[1]
        else:
            decision = PolicyDecision(
                graph_ids,
                remaining_ids,
                len(present_actions),
                None,
                None,
                None,
                None,
                (),
            )
        memo[key] = decision
        return decision

    root_ids = tuple(graph_by_id)
    remaining_ids = tuple(experiment_by_id)
    root = solve(root_ids, remaining_ids)
    report = assess_action_identifiability(ordered_graphs, ordered_experiments)
    return GlobalPolicyCertificate(
        identifiable=root.worst_case_cost is not None,
        root_graph_ids=root_ids,
        root_worst_case_cost=root.worst_case_cost,
        root_worst_case_probes=root.worst_case_probes,
        decisions=tuple(sorted(memo.values(), key=_decision_key)),
        impossibility_witnesses=report.witnesses if root.worst_case_cost is None else (),
    )


def run_global_policy(
    certificate: GlobalPolicyCertificate,
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
    truth: GraphHypothesis,
) -> tuple[ActionSignature | None, tuple[str, ...], int]:
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
            return decision.terminal_action, tuple(executed), cost
        if decision.selected_experiment_id is None:
            return None, tuple(executed), cost
        experiment = experiment_by_id[decision.selected_experiment_id]
        bits = predict_trace(truth, experiment).bits
        executed.append(experiment.experiment_id)
        cost += experiment.declared_cost
        branch = next((item for item in decision.branches if item.trace_bits == bits), None)
        if branch is None:
            return None, tuple(executed), cost
        graph_ids = branch.surviving_graph_ids
        remaining = tuple(item for item in remaining if item != experiment.experiment_id)


def _validated_inputs(
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
) -> tuple[tuple[GraphHypothesis, ...], tuple[DiscoveryExperiment, ...]]:
    if not hypotheses:
        raise ValueError("at least one hypothesis is required")
    graph_ids = tuple(graph.graph_id for graph in hypotheses)
    experiment_ids = tuple(item.experiment_id for item in experiments)
    if len(set(graph_ids)) != len(graph_ids):
        raise ValueError("graph hypothesis IDs must be unique")
    if len(set(experiment_ids)) != len(experiment_ids):
        raise ValueError("experiment IDs must be unique")
    return (
        tuple(sorted(hypotheses, key=lambda item: item.graph_id)),
        tuple(sorted(experiments, key=lambda item: item.experiment_id)),
    )


def _information_lower_bound(class_count: int, max_outcomes: int) -> int | None:
    if class_count <= 1:
        return 0
    if max_outcomes <= 1:
        return None
    probes = 0
    capacity = 1
    while capacity < class_count:
        probes += 1
        capacity *= max_outcomes
    return probes


def _decision_key(item: PolicyDecision) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    return (len(item.surviving_graph_ids), item.surviving_graph_ids, item.remaining_experiment_ids)


def _exact_policy_value(item: PolicyDecision) -> tuple[int, int]:
    if item.worst_case_cost is None or item.worst_case_probes is None:
        raise AssertionError("feasible child lost its exact policy value")
    return item.worst_case_cost, item.worst_case_probes
