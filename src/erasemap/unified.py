from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from erasemap.cdc import exact_cdc
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
    FIND = "FIND"
    ERASE = "ERASE"
    PROVE = "PROVE"


class StageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIED = "UNVERIFIED"


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

    stages: list[EraSeMapStageResult] = []

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
                    EraSeMapStage.FIND,
                    StageStatus.UNVERIFIED,
                    "registered traces were checked, but recovery-path evidence "
                    "was insufficient",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.ERASE,
                    minimize_status,
                    "the least-cost registered physical and model-erasure actions were evaluated",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.PROVE,
                    StageStatus.INCOMPLETE
                    if deletion_plan.verdict is PCUGVerdict.INCOMPLETE
                    else StageStatus.UNVERIFIED,
                    "the result cannot be certified without evidence-backed recovery replay",
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
                    EraSeMapStage.FIND,
                    StageStatus.UNVERIFIED,
                    "the recovery-path evidence could not be reconciled with the "
                    "registered system map",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.ERASE,
                    minimize_status,
                    "the least-cost registered physical and model-erasure actions were evaluated",
                ),
                EraSeMapStageResult(
                    EraSeMapStage.PROVE,
                    StageStatus.INCOMPLETE
                    if deletion_plan.verdict is PCUGVerdict.INCOMPLETE
                    else StageStatus.UNVERIFIED,
                    "the result cannot be certified without a reconciled recovery-path map",
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
            EraSeMapStage.FIND,
            StageStatus.COMPLETE,
            "copies, derivatives, model influence, and bounded recovery paths were identified",
        )
    )
    stages.append(
        EraSeMapStageResult(
            EraSeMapStage.ERASE,
            minimize_status,
            "the least-cost sufficient physical and model-erasure actions were selected",
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
            EraSeMapStage.PROVE,
            StageStatus.COMPLETE
            if verdict is EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE
            else StageStatus.INCOMPLETE
            if verdict is EraSeMapVerdict.INCOMPLETE
            else StageStatus.UNVERIFIED,
            "recovery replay passed and the result is ready for a signed certificate"
            if verdict is EraSeMapVerdict.COMPLETE_WITHIN_ENVELOPE
            else "recovery replay did not justify a deletion certificate",
        )
    )
    return EraSeMapResult(
        verdict,
        tuple(stages),
        deletion_plan,
        envelope,
        stabilization_plan,
    )
