from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations


class RSEVerdict(StrEnum):
    SNAPSHOT_INCOMPLETE = "SNAPSHOT_INCOMPLETE"
    REGENERATION_RISK = "REGENERATION_RISK"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    RSE_VERIFIED = "RSE_VERIFIED"


class StabilizationStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    INFEASIBLE = "INFEASIBLE"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class TemporalTransition:
    id: str
    requires: frozenset[str]
    adds: frozenset[str]
    removes: frozenset[str] = frozenset()
    forbids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("transition id is required")
        if not self.adds and not self.removes:
            raise ValueError("transition must change at least one fact")
        if self.adds & self.removes:
            raise ValueError("transition cannot add and remove the same fact")
        if self.requires & self.forbids:
            raise ValueError("transition cannot require and forbid the same fact")

    def apply(self, state: frozenset[str]) -> frozenset[str] | None:
        if not self.requires <= state or self.forbids & state:
            return None
        result = (state - self.removes) | self.adds
        return result if result != state else None


@dataclass(frozen=True, slots=True)
class TransitionObservation:
    id: str
    sensor_id: str
    transition_id: str
    verified: bool

    def __post_init__(self) -> None:
        if not self.id or not self.sensor_id or not self.transition_id:
            raise ValueError("observation id, sensor, and transition are required")


@dataclass(frozen=True, slots=True)
class TransitionCoverage:
    required_sensor_ids: frozenset[str]
    observations: tuple[TransitionObservation, ...]

    def __post_init__(self) -> None:
        if not self.required_sensor_ids:
            raise ValueError("at least one transition sensor is required")
        observation_ids = [item.id for item in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("duplicate transition observation id")


@dataclass(frozen=True, slots=True)
class CoverageReport:
    complete: bool
    missing_sensor_ids: tuple[str, ...]
    unobserved_transition_ids: tuple[str, ...]
    unregistered_transition_ids: tuple[str, ...]
    unverified_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RSEProtocol:
    protocol_id: str
    residual_facts: frozenset[str]
    max_reachable_states: int = 65_536

    def __post_init__(self) -> None:
        if not self.protocol_id or not self.residual_facts:
            raise ValueError("protocol id and residual facts are required")
        if self.max_reachable_states <= 0:
            raise ValueError("max reachable states must be positive")


@dataclass(frozen=True, slots=True)
class RSEReport:
    verdict: RSEVerdict
    snapshot_complete: bool
    coverage: CoverageReport
    reachable_state_count: int
    shortest_witness: tuple[str, ...] | None
    witness_state: frozenset[str] | None


@dataclass(frozen=True, slots=True)
class StabilizationControl:
    id: str
    cost: int
    guarded_transition_ids: frozenset[str]
    permitted: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.guarded_transition_ids:
            raise ValueError("control id and guarded transitions are required")
        if self.cost < 0:
            raise ValueError("control cost cannot be negative")


@dataclass(frozen=True, slots=True)
class StabilizationPlan:
    control_ids: tuple[str, ...]
    total_cost: int
    status: StabilizationStatus
    report: RSEReport

    @property
    def complete(self) -> bool:
        return self.report.verdict is RSEVerdict.RSE_VERIFIED


def evaluate_coverage(
    transitions: tuple[TemporalTransition, ...], coverage: TransitionCoverage
) -> CoverageReport:
    transition_ids = {item.id for item in transitions}
    observed_sensors = {item.sensor_id for item in coverage.observations if item.verified}
    observed_transitions = {
        item.transition_id for item in coverage.observations if item.verified
    }
    missing = tuple(sorted(coverage.required_sensor_ids - observed_sensors))
    unobserved = tuple(sorted(transition_ids - observed_transitions))
    unregistered = tuple(
        sorted(
            {
                item.transition_id
                for item in coverage.observations
                if item.transition_id not in transition_ids
            }
        )
    )
    unverified = tuple(sorted(item.id for item in coverage.observations if not item.verified))
    return CoverageReport(
        complete=not missing and not unobserved and not unregistered and not unverified,
        missing_sensor_ids=missing,
        unobserved_transition_ids=unobserved,
        unregistered_transition_ids=unregistered,
        unverified_observation_ids=unverified,
    )


def evaluate_rse(
    initial_state: frozenset[str],
    transitions: tuple[TemporalTransition, ...],
    coverage: TransitionCoverage,
    protocol: RSEProtocol,
    *,
    guarded_transition_ids: frozenset[str] = frozenset(),
) -> RSEReport:
    transition_ids = [item.id for item in transitions]
    if len(transition_ids) != len(set(transition_ids)):
        raise ValueError("duplicate transition id")
    unknown_guards = guarded_transition_ids - set(transition_ids)
    if unknown_guards:
        raise ValueError(f"guard targets unknown transition: {min(unknown_guards)}")

    coverage_report = evaluate_coverage(transitions, coverage)
    if initial_state & protocol.residual_facts:
        return RSEReport(
            verdict=RSEVerdict.SNAPSHOT_INCOMPLETE,
            snapshot_complete=False,
            coverage=coverage_report,
            reachable_state_count=1,
            shortest_witness=(),
            witness_state=initial_state,
        )

    ordered = tuple(sorted(transitions, key=lambda item: item.id))
    queue: deque[tuple[frozenset[str], tuple[str, ...]]] = deque(
        [(initial_state, ())]
    )
    visited = {initial_state}
    while queue:
        state, path = queue.popleft()
        for transition in ordered:
            if transition.id in guarded_transition_ids:
                continue
            next_state = transition.apply(state)
            if next_state is None or next_state in visited:
                continue
            next_path = (*path, transition.id)
            if next_state & protocol.residual_facts:
                return RSEReport(
                    verdict=RSEVerdict.REGENERATION_RISK,
                    snapshot_complete=True,
                    coverage=coverage_report,
                    reachable_state_count=len(visited) + 1,
                    shortest_witness=next_path,
                    witness_state=next_state,
                )
            visited.add(next_state)
            if len(visited) > protocol.max_reachable_states:
                raise ValueError("reachable-state limit exceeded")
            queue.append((next_state, next_path))

    verdict = (
        RSEVerdict.RSE_VERIFIED
        if coverage_report.complete
        else RSEVerdict.INCOMPLETE_COVERAGE
    )
    return RSEReport(
        verdict=verdict,
        snapshot_complete=True,
        coverage=coverage_report,
        reachable_state_count=len(visited),
        shortest_witness=None,
        witness_state=None,
    )


def exact_stabilization_cut(
    initial_state: frozenset[str],
    transitions: tuple[TemporalTransition, ...],
    coverage: TransitionCoverage,
    protocol: RSEProtocol,
    controls: tuple[StabilizationControl, ...],
    *,
    max_exact_controls: int = 24,
) -> StabilizationPlan:
    control_ids = [item.id for item in controls]
    if len(control_ids) != len(set(control_ids)):
        raise ValueError("duplicate stabilization control id")
    transition_ids = {item.id for item in transitions}
    for control in controls:
        unknown = control.guarded_transition_ids - transition_ids
        if unknown:
            raise ValueError(
                f"control {control.id!r} guards unknown transition: {min(unknown)}"
            )
    permitted = tuple(sorted((item for item in controls if item.permitted), key=lambda x: x.id))
    if len(permitted) > max_exact_controls:
        raise ValueError("exact stabilization control limit exceeded")

    baseline = evaluate_rse(initial_state, transitions, coverage, protocol)
    if baseline.verdict is RSEVerdict.RSE_VERIFIED:
        return StabilizationPlan((), 0, StabilizationStatus.OPTIMAL, baseline)
    best: tuple[tuple[int, int, tuple[str, ...]], StabilizationPlan] | None = None
    for size in range(1, len(permitted) + 1):
        for chosen in combinations(permitted, size):
            ids = tuple(item.id for item in chosen)
            guarded = frozenset().union(*(item.guarded_transition_ids for item in chosen))
            report = evaluate_rse(
                initial_state,
                transitions,
                coverage,
                protocol,
                guarded_transition_ids=guarded,
            )
            if report.verdict is not RSEVerdict.RSE_VERIFIED:
                continue
            cost = sum(item.cost for item in chosen)
            key = (cost, len(chosen), ids)
            plan = StabilizationPlan(ids, cost, StabilizationStatus.OPTIMAL, report)
            if best is None or key < best[0]:
                best = (key, plan)

    if best is not None:
        return best[1]
    status = (
        StabilizationStatus.UNVERIFIED
        if not baseline.coverage.complete
        else StabilizationStatus.INFEASIBLE
    )
    return StabilizationPlan((), 0, status, baseline)
