from __future__ import annotations

import itertools
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyReport,
    TomographyVerdict,
    decode,
)
from erasemap.erasure_tomography_design import construct_minimum_design
from erasemap.temporal_multipath import (
    CARRIER_FACTS,
    MultiCarrierStorageLab,
    multipath_controls,
    multipath_coverage,
    multipath_protocol,
    multipath_transitions,
)
from erasemap.temporal_robust import (
    RobustStabilizationPlan,
    TopologyScenario,
    TopologyUncertaintyEnvelope,
    exact_robust_stabilization_cut,
)

TOMOGRAPHY_MECHANISM_IDS = tuple(sorted(CARRIER_FACTS))


@dataclass(frozen=True, slots=True)
class TomographyRound:
    design: ProbeDesign
    observations: tuple[bool, ...]
    evidence: TomographyEvidence
    report: TomographyReport
    workflow_evidence_complete: tuple[bool, ...]
    subject_commitments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TomographyStabilizationTrial:
    round: TomographyRound
    transition_ids: tuple[str, ...]
    plan: RobustStabilizationPlan | None
    post_control_recurrence: bool | None


@lru_cache(maxsize=1)
def default_probe_design() -> ProbeDesign:
    feasible_rows = tuple(
        itertools.product((False, True), repeat=len(TOMOGRAPHY_MECHANISM_IDS))
    )[1:]
    result = construct_minimum_design(
        TOMOGRAPHY_MECHANISM_IDS,
        feasible_rows,
        max_failures=1,
        error_budget=0,
    )
    if result.design is None:
        raise RuntimeError("frozen tomography catalogue has no identifying design")
    return result.design.probe_design


def _carriers_for(
    mechanism_ids: tuple[str, ...],
) -> frozenset[str]:
    return frozenset(CARRIER_FACTS[item] for item in mechanism_ids)


def run_tomography_round(
    root: str | Path,
    *,
    active_ids: tuple[str, ...],
    seed: int,
    design: ProbeDesign | None = None,
    skipped_probe_index: int | None = None,
    contaminate_subjects: bool = False,
) -> TomographyRound:
    if len(active_ids) != len(set(active_ids)):
        raise ValueError("active mechanism ids must be unique")
    selected_design = design or default_probe_design()
    known_ids = set(selected_design.mechanism_ids)
    unknown_ids = set(active_ids) - known_ids
    known_active = tuple(item for item in active_ids if item in known_ids)
    observations = []
    workflow_evidence = []
    commitments = []
    root_path = Path(root)
    for probe_index, row in enumerate(selected_design.rows):
        probe_seed = seed if contaminate_subjects else seed + probe_index + 1
        selected = tuple(
            mechanism_id
            for mechanism_id, enabled in zip(
                selected_design.mechanism_ids, row, strict=True
            )
            if enabled and mechanism_id in known_active
        )
        lab = MultiCarrierStorageLab(
            root_path / f"probe-{probe_index}",
            seed=probe_seed,
            carriers=_carriers_for(selected),
        )
        commitments.append(lab.lab.subject_commitment(lab.subject_id))
        executed = skipped_probe_index != probe_index
        observations.append(lab.replay_registered_workflows() if executed else False)
        workflow_evidence.append(executed)

    evidence = TomographyEvidence(
        catalogue_complete=not unknown_ids,
        workflows_executed=all(workflow_evidence),
        subjects_isolated=len(set(commitments)) == len(commitments),
        recurrence_observable=True,
        observations_complete=True,
        sparsity_bound_verified=(
            not unknown_ids and len(known_active) <= selected_design.max_failures
        ),
        noise_bound_verified=True,
        stable_behavior=True,
        synthetic_subjects_only=True,
    )
    observation_tuple = tuple(observations)
    return TomographyRound(
        selected_design,
        observation_tuple,
        evidence,
        decode(selected_design, observation_tuple, evidence),
        tuple(workflow_evidence),
        tuple(commitments),
    )


def _robust_plan_for_support(
    transition_ids: tuple[str, ...],
) -> RobustStabilizationPlan:
    carriers = _carriers_for(transition_ids)
    scenario = TopologyScenario(
        "tomography-localized",
        0,
        carriers,
        multipath_transitions(),
        multipath_coverage(),
        multipath_protocol(),
    )
    envelope = TopologyUncertaintyEnvelope(
        "tomography-localized-envelope",
        scenario.id,
        0,
        (scenario,),
    )
    return exact_robust_stabilization_cut(envelope, multipath_controls())


def run_tomography_and_stabilize(
    root: str | Path,
    *,
    active_ids: tuple[str, ...],
    seed: int,
) -> TomographyStabilizationTrial:
    root_path = Path(root)
    round_result = run_tomography_round(
        root_path / "tomography",
        active_ids=active_ids,
        seed=seed,
    )
    if round_result.report.verdict is not TomographyVerdict.LOCALIZED:
        return TomographyStabilizationTrial(round_result, (), None, None)
    transition_ids = round_result.report.support
    if any(item not in CARRIER_FACTS for item in transition_ids):
        return TomographyStabilizationTrial(round_result, (), None, None)
    plan = _robust_plan_for_support(transition_ids)
    if not plan.complete:
        return TomographyStabilizationTrial(round_result, transition_ids, plan, None)
    replay_lab = MultiCarrierStorageLab(
        root_path / "post-control",
        seed=seed + 10_000,
        carriers=_carriers_for(transition_ids),
    )
    replay_lab.install_controls(plan.control_ids)
    recurrence = replay_lab.replay_registered_workflows()
    return TomographyStabilizationTrial(
        round_result,
        transition_ids,
        plan,
        recurrence,
    )
