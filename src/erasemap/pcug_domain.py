from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class EdgeState(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class EdgeKind(StrEnum):
    MATERIAL = "MATERIAL"
    INFLUENCE = "INFLUENCE"
    PROCESSING = "PROCESSING"


class ChannelDecision(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class PCUGVerdict(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIED = "UNVERIFIED"


class TransitionTarget(StrEnum):
    NODE = "NODE"
    EDGE = "EDGE"


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    APPROXIMATE = "APPROXIMATE"
    INFEASIBLE = "INFEASIBLE"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class ChannelResult:
    name: str
    value: float
    upper_bound: float
    threshold: float
    decision: ChannelDecision
    mandatory: bool
    evidence_id: str = ""
    stratum: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("channel name is required")
        if not all(
            math.isfinite(value) for value in (self.value, self.upper_bound, self.threshold)
        ):
            raise ValueError("channel values must be finite")
        if self.upper_bound < self.value:
            raise ValueError("channel upper bound cannot be below its value")


@dataclass(frozen=True, slots=True)
class PCUGNode:
    id: str
    kind: str
    subject_id: str
    state: EdgeState = EdgeState.ACTIVE
    active_sink: bool = False
    evidence_id: str = ""
    display_name: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.kind or not self.subject_id:
            raise ValueError("node id, kind, and subject are required")
        if self.active_sink and self.state is EdgeState.CLOSED:
            raise ValueError("closed node cannot remain an active sink")


@dataclass(frozen=True, slots=True)
class PCUGEdge:
    source_id: str
    target_id: str
    kind: EdgeKind
    state: EdgeState
    request_scoped: bool = False
    subject_id: str = ""
    evidence_id: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("edge endpoints are required")
        if self.kind is EdgeKind.INFLUENCE and not self.subject_id:
            raise ValueError("influence edge requires a subject")
        if self.request_scoped and not self.subject_id:
            raise ValueError("request-scoped edge requires a subject")
        if not self.id:
            subject = self.subject_id or "shared"
            generated = f"{self.source_id}->{self.target_id}:{self.kind.value}:{subject}"
            object.__setattr__(self, "id", generated)


@dataclass(frozen=True, slots=True)
class PCUGGraph:
    nodes: tuple[PCUGNode, ...]
    edges: tuple[PCUGEdge, ...]
    channel_results: tuple[ChannelResult, ...]

    def __post_init__(self) -> None:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate node id")
        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate edge id")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source_id not in known:
                raise ValueError(f"edge has unknown source {edge.source_id!r}")
            if edge.target_id not in known:
                raise ValueError(f"edge has unknown target {edge.target_id!r}")
        channel_keys = [(channel.name, channel.stratum) for channel in self.channel_results]
        if len(channel_keys) != len(set(channel_keys)):
            raise ValueError("duplicate verification channel")

    def node(self, node_id: str) -> PCUGNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def edge(self, edge_id: str) -> PCUGEdge:
        for edge in self.edges:
            if edge.id == edge_id:
                return edge
        raise KeyError(edge_id)


@dataclass(frozen=True, slots=True)
class Transition:
    target_id: str
    result_state: EdgeState
    evidence_id: str
    target: TransitionTarget = TransitionTarget.EDGE
    verified: bool = True

    def __post_init__(self) -> None:
        if not self.target_id or not self.evidence_id:
            raise ValueError("transition target and evidence are required")


@dataclass(frozen=True, slots=True)
class CDCAction:
    id: str
    cost: int
    transitions: tuple[Transition, ...]
    permitted: bool = True
    result_channels: tuple[ChannelResult, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("action id is required")
        if self.cost < 0:
            raise ValueError("action cost cannot be negative")
        if not self.transitions:
            raise ValueError("action transitions are required")
        targets = [(transition.target, transition.target_id) for transition in self.transitions]
        if len(targets) != len(set(targets)):
            raise ValueError("duplicate transition target")
        channel_keys = [(channel.name, channel.stratum) for channel in self.result_channels]
        if len(channel_keys) != len(set(channel_keys)):
            raise ValueError("duplicate action result channel")


@dataclass(frozen=True, slots=True)
class CDCProtocol:
    request_id: str
    subject_id: str
    source_ids: frozenset[str]
    sink_ids: frozenset[str]
    mandatory_channels: frozenset[str] = frozenset()
    max_exact_actions: int = 24

    def __post_init__(self) -> None:
        if not self.request_id or not self.subject_id:
            raise ValueError("request id and subject are required")
        if not self.source_ids or not self.sink_ids:
            raise ValueError("source and sink ids are required")
        if self.max_exact_actions <= 0:
            raise ValueError("max exact actions must be positive")

    def validate_graph(self, graph: PCUGGraph) -> None:
        known = {node.id for node in graph.nodes}
        missing_sources = self.source_ids - known
        if missing_sources:
            raise ValueError(f"unknown source id: {min(missing_sources)}")
        missing_sinks = self.sink_ids - known
        if missing_sinks:
            raise ValueError(f"unknown sink id: {min(missing_sinks)}")


@dataclass(frozen=True, slots=True)
class FeasibilityReport:
    graph: PCUGGraph
    verdict: PCUGVerdict
    active_paths: tuple[tuple[str, ...], ...]
    unknown_paths: tuple[tuple[str, ...], ...]
    shortest_counterexample: tuple[str, ...] | None
    failed_channels: tuple[str, ...]
    unknown_channels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CDCPlan:
    action_ids: tuple[str, ...]
    total_cost: int
    verdict: PCUGVerdict
    solver_status: SolverStatus
    report: FeasibilityReport
    lower_cost_bound: int
    upper_cost_bound: int | None

    def __post_init__(self) -> None:
        if self.total_cost < 0 or self.lower_cost_bound < 0:
            raise ValueError("plan costs cannot be negative")
        if self.upper_cost_bound is not None and self.upper_cost_bound < self.lower_cost_bound:
            raise ValueError("upper cost bound cannot be below lower bound")

    @property
    def complete(self) -> bool:
        return self.verdict is PCUGVerdict.COMPLETE
