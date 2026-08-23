from __future__ import annotations

from erasemap.ghostgraph import DiscoveryExperiment, ExecutedObservation, GraphHypothesis


def oracle_predict_bits(
    graph: GraphHypothesis,
    experiment: DiscoveryExperiment,
) -> tuple[bool, ...]:
    node_index = {node.node_id: index for index, node in enumerate(graph.nodes)}
    reached = 0
    for node_id in graph.initial_node_ids:
        reached |= 1 << node_index[node_id]
    enabled = frozenset(experiment.enabled_operation_ids)
    output = 0
    output_index = 0
    for _ in range(experiment.time_buckets):
        before = reached
        for edge in graph.edges:
            source_bit = 1 << node_index[edge.source_id]
            if edge.operation_id in enabled and before & source_bit:
                reached |= 1 << node_index[edge.target_id]
        for checkpoint_id in experiment.checkpoint_node_ids:
            if reached & (1 << node_index[checkpoint_id]):
                output |= 1 << output_index
            output_index += 1
    return tuple(bool(output & (1 << index)) for index in range(output_index))


def oracle_path_signature(
    graph: GraphHypothesis,
) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]:
    outgoing: dict[str, tuple[int, ...]] = {}
    for node in graph.nodes:
        outgoing[node.node_id] = tuple(
            index for index, edge in enumerate(graph.edges) if edge.source_id == node.node_id
        )
    found: set[tuple[str, ...]] = set()
    stack: list[tuple[str, frozenset[str], tuple[str, ...]]] = [
        (node_id, frozenset((node_id,)), ()) for node_id in graph.initial_node_ids
    ]
    residual = frozenset(graph.residual_node_ids)
    while stack:
        node_id, visited, path = stack.pop()
        if node_id in residual:
            found.add(path)
            continue
        for edge_index in outgoing[node_id]:
            edge = graph.edges[edge_index]
            if edge.target_id not in visited:
                stack.append(
                    (
                        edge.target_id,
                        visited | {edge.target_id},
                        (*path, edge.edge_id),
                    )
                )
    paths = tuple(sorted(found))
    edge_by_id = {edge.edge_id: edge.operation_id for edge in graph.edges}
    operations = tuple(sorted({edge_by_id[edge_id] for path in paths for edge_id in path}))
    return paths, operations


def oracle_surviving_ids(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
    error_budget: int,
) -> tuple[str, ...]:
    survivors: list[str] = []
    for graph in sorted(hypotheses, key=lambda item: item.graph_id):
        consistent = True
        for observation in observations:
            predicted = oracle_predict_bits(graph, observation.experiment)
            distance = sum(
                predicted_bit != observed_bit
                for predicted_bit, observed_bit in zip(
                    predicted,
                    observation.trace.bits,
                    strict=True,
                )
            )
            if distance > error_budget:
                consistent = False
                break
        if consistent:
            survivors.append(graph.graph_id)
    return tuple(survivors)


def oracle_verdict(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
    error_budget: int,
) -> str:
    survivor_ids = oracle_surviving_ids(hypotheses, observations, error_budget)
    if not survivor_ids:
        return "OUT_OF_HYPOTHESIS"
    if observations and not any(bit for item in observations for bit in item.trace.bits):
        return "NO_OBSERVED_RECURRENCE"
    if len(survivor_ids) == 1:
        return "GRAPH_DISCOVERED"
    graph_by_id = {graph.graph_id: graph for graph in hypotheses}
    signatures = {oracle_path_signature(graph_by_id[graph_id]) for graph_id in survivor_ids}
    return "PATH_CLASS_DISCOVERED" if len(signatures) == 1 else "EQUIVALENCE_CLASS"


def oracle_select_next(
    hypotheses: tuple[GraphHypothesis, ...],
    experiments: tuple[DiscoveryExperiment, ...],
    used_ids: tuple[str, ...],
) -> tuple[str | None, tuple[int, int, int, str] | None]:
    used = frozenset(used_ids)
    scored: list[tuple[int, int, int, str]] = []
    for experiment in experiments:
        if experiment.experiment_id in used:
            continue
        buckets: dict[tuple[bool, ...], int] = {}
        for graph in hypotheses:
            bits = oracle_predict_bits(graph, experiment)
            buckets[bits] = buckets.get(bits, 0) + 1
        if len(buckets) < 2:
            continue
        sizes = tuple(buckets.values())
        scored.append(
            (
                max(sizes),
                sum(size * size for size in sizes),
                experiment.declared_cost,
                experiment.experiment_id,
            )
        )
    if not scored:
        return None, None
    selected = min(scored)
    return selected[3], selected
