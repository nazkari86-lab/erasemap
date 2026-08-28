from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from erasemap.cdc import evaluate_actions, exact_cdc
from erasemap.ghostgraph import DiscoveryReport, DiscoveryVerdict, GraphHypothesis
from erasemap.ghostgraph_bridge import build_controls, build_topology_envelope
from erasemap.pcug_domain import (
    CDCAction,
    CDCPlan,
    CDCProtocol,
    PCUGGraph,
    PCUGVerdict,
)
from erasemap.temporal import StabilizationControl, StabilizationStatus
from erasemap.temporal_robust import (
    RobustStabilizationPlan,
    TopologyUncertaintyEnvelope,
    exact_robust_stabilization_cut,
)


class EraSeMapVerdict(StrEnum):
    COMPLETE_WITHIN_ENVELOPE = "COMPLETE_WITHIN_ENVELOPE"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIED = "UNVERIFIED"


class EraSeMapStage(StrEnum):
    MAP = "MAP"
    DISCOVER = "DISCOVER"
    MINIMIZE = "MINIMIZE"
    VERIFY_OVER_TIME = "VERIFY_OVER_TIME"
    CERTIFY = "CERTIFY"


class StageStatus(StrEnum):
    READY = "READY"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class EraSeMapStageResult:
    stage: EraSeMapStage
    status: StageStatus
    explanation: str


@dataclass(frozen=True, slots=True)
class EraSeMapResult:
    verdict: EraSeMapVerdict
    stages: tuple[EraSeMapStageResult, ...]
    deletion_plan: CDCPlan
    topology_envelope: TopologyUncertaintyEnvelope | None
    stabilization_plan: RobustStabilizationPlan | None

    @property
    def certificate_ready(self) -> bool:
        return self.verdict is EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE


_ACTIONABLE_DISCOVERY = frozenset(
    {
        DiscoveryVerdict.GRAPH_DISCOVERED,
        DiscoveryVerdict.PATH_CLASS_DISCOVERED,
        DiscoveryVerdict.EQUIVALENCE_CLASS,
    }
)


def run_erasemap(
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
    discovery: DiscoveryReport,
    graph_by_id: Mapping[str, GraphHypothesis],
    *,
    temporal_controls: tuple[StabilizationControl, ...] | None = None,
    max_exact_controls: int = 24,
) -> EraSeMapResult:
    """Run the single fail-closed EraSeMap decision pipeline.

    Internal PCUG, GhostGraph, CDC, and robust temporal routines are stages of this
    function, not competing top-level algorithms. COMPLETE is returned only when the
    physical/model action plan and every registered temporal scenario both verify.
    """

    baseline = evaluate_actions(graph, protocol, ())
    map_status = (
        StageStatus.COMPLETE
        if baseline.verdict is PCUGVerdict.COMPLETE
        else StageStatus.UNVERIFIED
        if baseline.verdict is PCUGVerdict.UNVERIFIED
        else StageStatus.ACTION_REQUIRED
    )
    stages = [
        EraSeMapStageResult(
            EraSeMapStage.MAP,
            map_status,
            "registered artifacts, derivatives, channels, and residual paths were replayed",
        )
    ]

    deletion_plan = exact_cdc(graph, protocol, actions)
    minimize_status = (
        StageStatus.COMPLETE
        if deletion_plan.complete
        else StageStatus.UNVERIFIED
        if deletion_plan.verdict is PCUGVerdict.UNVERIFIED
        else StageStatus.INCOMPLETE
    )

    if discovery.verdict not in _ACTIONABLE_DISCOVERY or not discovery.evidence.valid:
        stages.extend(
            (
                EraSeMapStageResult(
                    EraSeMapStage.DISCOVER,
                    StageStatus.UNVERIFIED,
                    "bounded active evidence did not identify an actionable topology class",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.MINIMIZE,
                    minimize_status,
                    "the minimum registered deletion plan was evaluated independently",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.VERIFY_OVER_TIME,
                    StageStatus.BLOCKED,
                    "temporal replay requires an evidence-backed topology envelope",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.CERTIFY,
                    StageStatus.BLOCKED,
                    "a fail-closed run cannot certify an unverified topology",
                ),
            )
        )
        verdict = (
            EraSeMapVerdict.INCOMPLETE
            if deletion_plan.verdict is PCUGVerdict.INCOMPLETE
            else EraSeMapVerdict.UNVERIFIED
        )
        return EraSeMapResult(verdict, tuple(stages), deletion_plan, None, None)

    try:
        envelope = build_topology_envelope(discovery, graph_by_id)
    except (KeyError, ValueError):
        # A stale or tampered discovery report is uncertainty, never success.
        stages.extend(
            (
                EraSeMapStageResult(
                    EraSeMapStage.DISCOVER,
                    StageStatus.UNVERIFIED,
                    "discovery evidence could not be reconciled with the registered hypotheses",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.MINIMIZE,
                    minimize_status,
                    "the minimum registered deletion plan was evaluated independently",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.VERIFY_OVER_TIME,
                    StageStatus.BLOCKED,
                    "temporal replay requires a reconciled topology envelope",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.CERTIFY,
                    StageStatus.BLOCKED,
                    "certificate issuance is blocked by unreconciled discovery evidence",
                ),
            )
        )
        verdict = (
            EraSeMapVerdict.INCOMPLETE
            if deletion_plan.verdict is PCUGVerdict.INCOMPLETE
            else EraSeMapVerdict.UNVERIFIED
        )
        return EraSeMapResult(verdict, tuple(stages), deletion_plan, None, None)
    stages.append(
        EraSeMapStageResult(
            EraSeMapStage.DISCOVER,
            StageStatus.COMPLETE,
            "active probes reduced the registered hypotheses to an actionable envelope",
        )
    )
    stages.append(
        EraSeMapStageResult(
            EraSeMapStage.MINIMIZE,
            minimize_status,
            "exact finite search selected the least-cost sufficient registered actions",
        )
    )

    controls = build_controls(envelope) if temporal_controls is None else temporal_controls
    try:
        stabilization_plan = exact_robust_stabilization_cut(
            envelope,
            controls,
            max_exact_controls=max_exact_controls,
        )
    except ValueError:
        # Invalid controls or an excessive exact-search request must fail closed.
        stabilization_plan = None
    temporal_status = (
        StageStatus.COMPLETE
        if stabilization_plan is not None and stabilization_plan.complete
        else StageStatus.UNVERIFIED
        if stabilization_plan is None
        or stabilization_plan.status is StabilizationStatus.UNVERIFIED
        else StageStatus.INCOMPLETE
    )
    stages.append(
        EraSeMapStageResult(
            EraSeMapStage.VERIFY_OVER_TIME,
            temporal_status,
            "all registered future recovery scenarios were replayed after control selection",
        )
    )

    if deletion_plan.verdict is PCUGVerdict.INCOMPLETE:
        verdict = EraSeMapVerdict.INCOMPLETE
    elif deletion_plan.verdict is PCUGVerdict.UNVERIFIED:
        verdict = EraSeMapVerdict.UNVERIFIED
    elif stabilization_plan is not None and stabilization_plan.complete:
        verdict = EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE
    elif stabilization_plan is None or stabilization_plan.status is StabilizationStatus.UNVERIFIED:
        verdict = EraSeMapVerdict.UNVERIFIED
    else:
        verdict = EraSeMapVerdict.INCOMPLETE

    stages.append(
        EraSeMapStageResult(
            EraSeMapStage.CERTIFY,
            StageStatus.READY
            if verdict is EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE
            else StageStatus.BLOCKED,
            "the result is ready for signed certificate issuance"
            if verdict is EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE
            else "certificate issuance is blocked until every mandatory stage verifies",
        )
    )
    return EraSeMapResult(
        verdict,
        tuple(stages),
        deletion_plan,
        envelope,
        stabilization_plan,
    )
