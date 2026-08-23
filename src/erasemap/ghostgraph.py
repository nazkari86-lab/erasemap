from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MAX_NODES = 8
MAX_EDGES = 12
MAX_HYPOTHESES = 4096
MAX_EXPERIMENTS = 32
MAX_CHECKPOINTS = 5
MAX_TIME_BUCKETS = 3


class DiscoveryVerdict(StrEnum):
    NO_OBSERVED_RECURRENCE = "NO_OBSERVED_RECURRENCE"
    GRAPH_DISCOVERED = "GRAPH_DISCOVERED"
    PATH_CLASS_DISCOVERED = "PATH_CLASS_DISCOVERED"
    EQUIVALENCE_CLASS = "EQUIVALENCE_CLASS"
    OUT_OF_HYPOTHESIS = "OUT_OF_HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True, order=True)
class GraphNode:
    node_id: str

    def __post_init__(self) -> None:
        if not self.node_id or self.node_id.strip() != self.node_id:
            raise ValueError("node ID must be non-empty and trimmed")


@dataclass(frozen=True, slots=True, order=True)
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    operation_id: str

    def __post_init__(self) -> None:
        values = (self.edge_id, self.source_id, self.target_id, self.operation_id)
        if any(not value or value.strip() != value for value in values):
            raise ValueError("edge fields must be non-empty and trimmed")
        if self.source_id == self.target_id:
            raise ValueError("self-loop edges are not supported in GhostGraph v1")


@dataclass(frozen=True, slots=True)
class GraphHypothesis:
    graph_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    initial_node_ids: tuple[str, ...]
    residual_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.graph_id or self.graph_id.strip() != self.graph_id:
            raise ValueError("graph ID must be non-empty and trimmed")
        if not self.nodes:
            raise ValueError("graph must contain at least one node")
        if len(self.nodes) > MAX_NODES:
            raise ValueError(f"GhostGraph v1 supports at most {MAX_NODES} nodes")
        if len(self.edges) > MAX_EDGES:
            raise ValueError(f"GhostGraph v1 supports at most {MAX_EDGES} edges")
        node_ids = tuple(node.node_id for node in self.nodes)
        edge_ids = tuple(edge.edge_id for edge in self.edges)
        if node_ids != tuple(sorted(node_ids)):
            raise ValueError("nodes must be sorted by node ID")
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node IDs must be unique")
        if edge_ids != tuple(sorted(edge_ids)):
            raise ValueError("edges must be sorted by edge ID")
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("edge IDs must be unique")
        node_id_set = frozenset(node_ids)
        for edge in self.edges:
            if edge.source_id not in node_id_set or edge.target_id not in node_id_set:
                raise ValueError(f"edge {edge.edge_id} has an unknown endpoint")
        self._validate_node_id_set("initial", self.initial_node_ids, node_id_set)
        self._validate_node_id_set("residual", self.residual_node_ids, node_id_set)

    @staticmethod
    def _validate_node_id_set(
        label: str,
        selected: tuple[str, ...],
        node_ids: frozenset[str],
    ) -> None:
        if not selected:
            raise ValueError(f"{label} node IDs must not be empty")
        if selected != tuple(sorted(selected)) or len(set(selected)) != len(selected):
            raise ValueError(f"{label} node IDs must be sorted and unique")
        if not set(selected).issubset(node_ids):
            raise ValueError(f"{label} node IDs contain an unknown node")


@dataclass(frozen=True, slots=True)
class DiscoveryExperiment:
    experiment_id: str
    enabled_operation_ids: tuple[str, ...]
    checkpoint_node_ids: tuple[str, ...]
    time_buckets: int
    declared_cost: int

    def __post_init__(self) -> None:
        if not self.experiment_id or self.experiment_id.strip() != self.experiment_id:
            raise ValueError("experiment ID must be non-empty and trimmed")
        if self.enabled_operation_ids != tuple(sorted(self.enabled_operation_ids)):
            raise ValueError("enabled operation IDs must be sorted")
        if len(set(self.enabled_operation_ids)) != len(self.enabled_operation_ids):
            raise ValueError("enabled operation IDs must be unique")
        if not self.checkpoint_node_ids:
            raise ValueError("at least one checkpoint is required")
        if self.checkpoint_node_ids != tuple(sorted(self.checkpoint_node_ids)):
            raise ValueError("checkpoint node IDs must be sorted")
        if len(set(self.checkpoint_node_ids)) != len(self.checkpoint_node_ids):
            raise ValueError("checkpoint node IDs must be unique")
        if len(self.checkpoint_node_ids) > MAX_CHECKPOINTS:
            raise ValueError(f"at most {MAX_CHECKPOINTS} checkpoints are supported")
        if self.time_buckets < 1 or self.time_buckets > MAX_TIME_BUCKETS:
            raise ValueError(f"time buckets must be between 1 and {MAX_TIME_BUCKETS}")
        if self.declared_cost < 0:
            raise ValueError("declared cost must be non-negative")


@dataclass(frozen=True, slots=True)
class ObservationTrace:
    checkpoint_node_ids: tuple[str, ...]
    time_buckets: int
    bits: tuple[bool, ...]

    def __post_init__(self) -> None:
        expected = len(self.checkpoint_node_ids) * self.time_buckets
        if expected != len(self.bits):
            raise ValueError(f"trace bit count must be {expected}, got {len(self.bits)}")


@dataclass(frozen=True, slots=True)
class ExecutedObservation:
    experiment: DiscoveryExperiment
    trace: ObservationTrace

    def __post_init__(self) -> None:
        if self.trace.checkpoint_node_ids != self.experiment.checkpoint_node_ids:
            raise ValueError("trace checkpoints do not match the experiment")
        if self.trace.time_buckets != self.experiment.time_buckets:
            raise ValueError("trace time buckets do not match the experiment")


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    grammar_committed: bool
    hypothesis_space_complete: bool
    adapters_digest_verified: bool
    interventions_executed: bool
    subjects_isolated: bool
    observations_complete: bool
    stable_behavior: bool
    trace_error_bound_verified: bool
    synthetic_subjects_only: bool
    preregistration_unchanged: bool
    trace_error_budget: int = 0

    def __post_init__(self) -> None:
        if self.trace_error_budget < 0:
            raise ValueError("trace error budget must be non-negative")

    @classmethod
    def complete(cls, *, trace_error_budget: int = 0) -> DiscoveryEvidence:
        return cls(
            grammar_committed=True,
            hypothesis_space_complete=True,
            adapters_digest_verified=True,
            interventions_executed=True,
            subjects_isolated=True,
            observations_complete=True,
            stable_behavior=True,
            trace_error_bound_verified=True,
            synthetic_subjects_only=True,
            preregistration_unchanged=True,
            trace_error_budget=trace_error_budget,
        )

    @property
    def valid(self) -> bool:
        return all(
            (
                self.grammar_committed,
                self.hypothesis_space_complete,
                self.adapters_digest_verified,
                self.interventions_executed,
                self.subjects_isolated,
                self.observations_complete,
                self.stable_behavior,
                self.trace_error_bound_verified,
                self.synthetic_subjects_only,
                self.preregistration_unchanged,
            )
        )


@dataclass(frozen=True, slots=True, order=True)
class RelevantSignature:
    edge_paths: tuple[tuple[str, ...], ...]
    control_operation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TraceInconsistency:
    graph_id: str
    experiment_id: str
    distance: int
    predicted_bits: tuple[bool, ...]
    observed_bits: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryReport:
    verdict: DiscoveryVerdict
    surviving_graph_ids: tuple[str, ...]
    path_signatures: tuple[RelevantSignature, ...]
    evidence: DiscoveryEvidence
    inconsistency: TraceInconsistency | None


def predict_trace(
    graph: GraphHypothesis,
    experiment: DiscoveryExperiment,
) -> ObservationTrace:
    node_ids = frozenset(node.node_id for node in graph.nodes)
    if not set(experiment.checkpoint_node_ids).issubset(node_ids):
        raise ValueError("experiment checkpoint is absent from the graph node universe")
    enabled = frozenset(experiment.enabled_operation_ids)
    reached = set(graph.initial_node_ids)
    bits: list[bool] = []
    for _ in range(experiment.time_buckets):
        next_reached = set(reached)
        for edge in graph.edges:
            if edge.operation_id in enabled and edge.source_id in reached:
                next_reached.add(edge.target_id)
        reached = next_reached
        bits.extend(node_id in reached for node_id in experiment.checkpoint_node_ids)
    return ObservationTrace(
        checkpoint_node_ids=experiment.checkpoint_node_ids,
        time_buckets=experiment.time_buckets,
        bits=tuple(bits),
    )


def trace_distance(left: ObservationTrace, right: ObservationTrace) -> int:
    if left.checkpoint_node_ids != right.checkpoint_node_ids:
        raise ValueError("cannot compare traces with different checkpoints")
    if left.time_buckets != right.time_buckets:
        raise ValueError("cannot compare traces with different time buckets")
    return sum(
        left_bit is not right_bit
        for left_bit, right_bit in zip(left.bits, right.bits, strict=True)
    )


def relevant_signature(graph: GraphHypothesis) -> RelevantSignature:
    outgoing: dict[str, list[GraphEdge]] = {node.node_id: [] for node in graph.nodes}
    for edge in graph.edges:
        outgoing[edge.source_id].append(edge)
    found: set[tuple[str, ...]] = set()

    def search(node_id: str, visited: frozenset[str], path: tuple[str, ...]) -> None:
        if node_id in graph.residual_node_ids:
            found.add(path)
            return
        for edge in outgoing[node_id]:
            if edge.target_id in visited:
                continue
            search(edge.target_id, visited | {edge.target_id}, (*path, edge.edge_id))

    for initial_id in graph.initial_node_ids:
        search(initial_id, frozenset((initial_id,)), ())
    edge_by_id = {edge.edge_id: edge for edge in graph.edges}
    paths = tuple(sorted(found))
    controls = tuple(
        sorted({edge_by_id[edge_id].operation_id for path in paths for edge_id in path})
    )
    return RelevantSignature(paths, controls)


def update_version_space(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
    evidence: DiscoveryEvidence,
) -> DiscoveryReport:
    _validate_inputs(hypotheses, observations)
    initial_ids = tuple(graph.graph_id for graph in hypotheses)
    initial_signatures = tuple(sorted({relevant_signature(graph) for graph in hypotheses}))
    if not evidence.valid:
        return DiscoveryReport(
            DiscoveryVerdict.UNVERIFIED,
            initial_ids,
            initial_signatures,
            evidence,
            None,
        )

    survivors = tuple(
        graph
        for graph in hypotheses
        if all(
            trace_distance(predict_trace(graph, item.experiment), item.trace)
            <= evidence.trace_error_budget
            for item in observations
        )
    )
    if not survivors:
        return DiscoveryReport(
            DiscoveryVerdict.OUT_OF_HYPOTHESIS,
            (),
            (),
            evidence,
            _shortest_inconsistency(hypotheses, observations),
        )

    survivor_ids = tuple(graph.graph_id for graph in survivors)
    signatures = tuple(sorted({relevant_signature(graph) for graph in survivors}))
    if observations and not any(bit for item in observations for bit in item.trace.bits):
        verdict = DiscoveryVerdict.NO_OBSERVED_RECURRENCE
    elif len(survivors) == 1:
        verdict = DiscoveryVerdict.GRAPH_DISCOVERED
    elif len(signatures) == 1:
        verdict = DiscoveryVerdict.PATH_CLASS_DISCOVERED
    else:
        verdict = DiscoveryVerdict.EQUIVALENCE_CLASS
    return DiscoveryReport(verdict, survivor_ids, signatures, evidence, None)


def _validate_inputs(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
) -> None:
    if not hypotheses:
        raise ValueError("at least one graph hypothesis is required")
    if len(hypotheses) > MAX_HYPOTHESES:
        raise ValueError(f"at most {MAX_HYPOTHESES} hypotheses are supported")
    graph_ids = tuple(graph.graph_id for graph in hypotheses)
    if graph_ids != tuple(sorted(graph_ids)):
        raise ValueError("hypotheses must be sorted by graph ID")
    if len(set(graph_ids)) != len(graph_ids):
        raise ValueError("graph hypothesis IDs must be unique")
    if len(observations) > MAX_EXPERIMENTS:
        raise ValueError(f"at most {MAX_EXPERIMENTS} observations are supported")
    experiment_ids = tuple(item.experiment.experiment_id for item in observations)
    if len(set(experiment_ids)) != len(experiment_ids):
        raise ValueError("observation experiment IDs must be unique")


def _shortest_inconsistency(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
) -> TraceInconsistency | None:
    candidates: list[TraceInconsistency] = []
    for graph in hypotheses:
        for item in observations:
            predicted = predict_trace(graph, item.experiment)
            candidates.append(
                TraceInconsistency(
                    graph_id=graph.graph_id,
                    experiment_id=item.experiment.experiment_id,
                    distance=trace_distance(predicted, item.trace),
                    predicted_bits=predicted.bits,
                    observed_bits=item.trace.bits,
                )
            )
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item.distance, item.graph_id, item.experiment_id))
