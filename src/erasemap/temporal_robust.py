from __future__ import annotations

from dataclasses import dataclass

from erasemap.temporal import (
    RSEProtocol,
    RSEReport,
    RSEVerdict,
    StabilizationControl,
    StabilizationStatus,
    TemporalTransition,
    TransitionCoverage,
    evaluate_rse,
)


@dataclass(frozen=True, slots=True)
class TopologyScenario:
    id: str
    mutation_count: int
    initial_state: frozenset[str]
    transitions: tuple[TemporalTransition, ...]
    coverage: TransitionCoverage
    protocol: RSEProtocol

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("scenario id is required")
        if self.mutation_count < 0:
            raise ValueError("scenario mutation count cannot be negative")
        transition_ids = [item.id for item in self.transitions]
        if len(transition_ids) != len(set(transition_ids)):
            raise ValueError(f"scenario {self.id!r} has duplicate transition ids")


@dataclass(frozen=True, slots=True)
class TopologyUncertaintyEnvelope:
    id: str
    nominal_scenario_id: str
    max_mutations: int
    scenarios: tuple[TopologyScenario, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.nominal_scenario_id:
            raise ValueError("envelope and nominal scenario ids are required")
        if self.max_mutations < 0:
            raise ValueError("maximum mutations cannot be negative")
        if not self.scenarios:
            raise ValueError("at least one topology scenario is required")
        scenario_ids = [item.id for item in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("duplicate topology scenario id")
        matching_nominal = [
            item for item in self.scenarios if item.id == self.nominal_scenario_id
        ]
        if len(matching_nominal) != 1 or matching_nominal[0].mutation_count != 0:
            raise ValueError("nominal scenario must exist exactly once with zero mutations")
        if any(item.mutation_count > self.max_mutations for item in self.scenarios):
            raise ValueError("scenario exceeds the envelope mutation budget")
        residual_sets = {item.protocol.residual_facts for item in self.scenarios}
        if len(residual_sets) != 1:
            raise ValueError("all scenarios must use the same residual semantics")

    @property
    def nominal(self) -> TopologyScenario:
        return next(item for item in self.scenarios if item.id == self.nominal_scenario_id)


@dataclass(frozen=True, slots=True)
class RobustScenarioReport:
    scenario_id: str
    mutation_count: int
    report: RSEReport


@dataclass(frozen=True, slots=True)
class AdversarialRegenerationWitness:
    scenario_id: str
    mutation_count: int
    transition_ids: tuple[str, ...]
    witness_state: frozenset[str]


@dataclass(frozen=True, slots=True)
class RobustStabilizationPlan:
    control_ids: tuple[str, ...]
    total_cost: int
    status: StabilizationStatus
    scenario_reports: tuple[RobustScenarioReport, ...]
    shortest_adversarial_witness: AdversarialRegenerationWitness | None

    @property
    def complete(self) -> bool:
        return bool(self.scenario_reports) and all(
            item.report.verdict is RSEVerdict.RSE_VERIFIED
            for item in self.scenario_reports
        )


def _reports(
    envelope: TopologyUncertaintyEnvelope,
    guarded_transition_ids: frozenset[str],
) -> tuple[RobustScenarioReport, ...]:
    reports = []
    for scenario in sorted(envelope.scenarios, key=lambda item: item.id):
        scenario_transition_ids = frozenset(item.id for item in scenario.transitions)
        report = evaluate_rse(
            scenario.initial_state,
            scenario.transitions,
            scenario.coverage,
            scenario.protocol,
            guarded_transition_ids=guarded_transition_ids & scenario_transition_ids,
        )
        reports.append(
            RobustScenarioReport(scenario.id, scenario.mutation_count, report)
        )
    return tuple(reports)


def shortest_adversarial_witness(
    reports: tuple[RobustScenarioReport, ...],
) -> AdversarialRegenerationWitness | None:
    candidates = []
    for item in reports:
        path = item.report.shortest_witness
        state = item.report.witness_state
        if item.report.verdict is not RSEVerdict.REGENERATION_RISK:
            continue
        if path is None or state is None:
            raise ValueError("regeneration risk is missing its witness")
        candidates.append(
            (
                (len(path), item.mutation_count, item.scenario_id, path),
                AdversarialRegenerationWitness(
                    item.scenario_id, item.mutation_count, path, state
                ),
            )
        )
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def exact_robust_stabilization_cut(
    envelope: TopologyUncertaintyEnvelope,
    controls: tuple[StabilizationControl, ...],
    *,
    max_exact_controls: int = 24,
) -> RobustStabilizationPlan:
    control_ids = [item.id for item in controls]
    if len(control_ids) != len(set(control_ids)):
        raise ValueError("duplicate robust stabilization control id")
    all_transition_ids = {
        transition.id
        for scenario in envelope.scenarios
        for transition in scenario.transitions
    }
    for control in controls:
        unknown = control.guarded_transition_ids - all_transition_ids
        if unknown:
            raise ValueError(
                f"control {control.id!r} guards transition outside envelope: {min(unknown)}"
            )
    permitted = tuple(
        sorted((item for item in controls if item.permitted), key=lambda item: item.id)
    )
    if len(permitted) > max_exact_controls:
        raise ValueError("exact robust stabilization control limit exceeded")

    baseline_reports = _reports(envelope, frozenset())
    witness = shortest_adversarial_witness(baseline_reports)
    if any(not item.report.coverage.complete for item in baseline_reports):
        return RobustStabilizationPlan(
            (), 0, StabilizationStatus.UNVERIFIED, baseline_reports, witness
        )
    if all(
        item.report.verdict is RSEVerdict.RSE_VERIFIED for item in baseline_reports
    ):
        return RobustStabilizationPlan(
            (), 0, StabilizationStatus.OPTIMAL, baseline_reports, None
        )

    best: tuple[tuple[int, int, tuple[str, ...]], RobustStabilizationPlan] | None = None

    def search(
        index: int,
        chosen: tuple[StabilizationControl, ...],
        guarded: frozenset[str],
        cost: int,
    ) -> None:
        nonlocal best
        ids = tuple(item.id for item in chosen)
        if best is not None and (
            cost > best[0][0]
            or (cost == best[0][0] and len(chosen) > best[0][1])
        ):
            return
        reports = _reports(envelope, guarded)
        if all(item.report.verdict is RSEVerdict.RSE_VERIFIED for item in reports):
            key = (cost, len(chosen), ids)
            plan = RobustStabilizationPlan(
                ids, cost, StabilizationStatus.OPTIMAL, reports, witness
            )
            if best is None or key < best[0]:
                best = (key, plan)
            return
        if index == len(permitted):
            return
        control = permitted[index]
        search(
            index + 1,
            (*chosen, control),
            guarded | control.guarded_transition_ids,
            cost + control.cost,
        )
        search(index + 1, chosen, guarded, cost)

    search(0, (), frozenset(), 0)
    if best is not None:
        return best[1]
    return RobustStabilizationPlan(
        (), 0, StabilizationStatus.INFEASIBLE, baseline_reports, witness
    )
