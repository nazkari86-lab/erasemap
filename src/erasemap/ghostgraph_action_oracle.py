from __future__ import annotations

from erasemap.ghostgraph import DiscoveryExperiment, GraphHypothesis
from erasemap.ghostgraph_action import ActionSignature, action_signature
from erasemap.ghostgraph_oracle import oracle_predict_bits


def oracle_global_policy_value(
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
) -> tuple[int, int, str | None] | None:
    graphs = tuple(sorted(hypotheses, key=lambda item: item.graph_id))
    probes = tuple(sorted(experiments, key=lambda item: item.experiment_id))
    actions = {graph.graph_id: _oracle_action_signature(graph) for graph in graphs}

    def search(
        current: tuple[GraphHypothesis, ...],
        remaining: tuple[DiscoveryExperiment, ...],
    ) -> tuple[int, int, str | None] | None:
        if len({actions[graph.graph_id] for graph in current}) == 1:
            return 0, 0, None
        candidates: list[tuple[int, int, int, str]] = []
        for experiment in remaining:
            groups: dict[tuple[bool, ...], list[GraphHypothesis]] = {}
            for graph in current:
                groups.setdefault(oracle_predict_bits(graph, experiment), []).append(graph)
            if len(groups) < 2:
                continue
            future = tuple(
                item
                for item in remaining
                if item.experiment_id != experiment.experiment_id
            )
            children = tuple(search(tuple(group), future) for group in groups.values())
            if any(child is None for child in children):
                continue
            values = tuple(child for child in children if child is not None)
            child_costs = tuple(item[0] for item in values)
            child_depths = tuple(item[1] for item in values)
            candidates.append(
                (
                    experiment.declared_cost + max(child_costs),
                    1 + max(child_depths),
                    sum(child_costs),
                    experiment.experiment_id,
                )
            )
        if not candidates:
            return None
        best = min(candidates)
        return best[0], best[1], best[3]

    return search(graphs, probes)


def _oracle_action_signature(graph: GraphHypothesis) -> ActionSignature:
    # Kept as a separate entry point so policy conformance does not depend on planner state.
    return action_signature(graph)
