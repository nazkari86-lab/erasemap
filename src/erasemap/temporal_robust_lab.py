from __future__ import annotations

import itertools
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from erasemap.temporal import (
    RSEVerdict,
    StabilizationControl,
    StabilizationPlan,
    StabilizationStatus,
    TransitionCoverage,
    evaluate_rse,
    exact_stabilization_cut,
)
from erasemap.temporal_multipath import (
    CARRIER_FACTS,
    MultiCarrierStorageLab,
    control_guard_ids,
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

OPTIONAL_TRANSITION_IDS = (
    "checkpoint_redeploy",
    "legacy_export_import",
    "retry_queue_replay",
)
ALWAYS_REGISTERED_TRANSITION_IDS = frozenset(
    {"backup_restore", "model_retrain", "nightly_etl", "vector_rebuild"}
)


@dataclass(frozen=True, slots=True)
class RobustPhysicalTrial:
    case_id: str
    scenario_id: str
    scenario_mask: int
    seed: int
    active_carriers: tuple[str, ...]
    nominal_control_ids: tuple[str, ...]
    nominal_cost: int
    robust_control_ids: tuple[str, ...]
    robust_cost: int
    robustness_premium: int
    adversarial_witness: tuple[str, ...]
    uncontrolled_regeneration: bool
    nominal_plan_regeneration: bool
    robust_post_control_regeneration: bool
    oracle_control_ids: tuple[str, ...]
    oracle_cost: int
    oracle_match: bool
    runtime_milliseconds: float

    def payload(self) -> dict[str, object]:
        return asdict(self)


def _coverage_for_transition_ids(
    transition_ids: frozenset[str],
) -> TransitionCoverage:
    full = multipath_coverage()
    observations = tuple(
        item for item in full.observations if item.transition_id in transition_ids
    )
    return TransitionCoverage(
        frozenset(item.sensor_id for item in observations), observations
    )


def scenario_from_mask(mask: int) -> TopologyScenario:
    if mask < 0 or mask >= 1 << len(OPTIONAL_TRANSITION_IDS):
        raise ValueError("scenario mask is outside the frozen three-bit envelope")
    optional = frozenset(
        transition_id
        for index, transition_id in enumerate(OPTIONAL_TRANSITION_IDS)
        if mask & (1 << index)
    )
    transition_ids = ALWAYS_REGISTERED_TRANSITION_IDS | optional
    transitions = tuple(
        item for item in multipath_transitions() if item.id in transition_ids
    )
    active_reactivation_ids = frozenset({"backup_restore"}) | optional
    carriers = frozenset(CARRIER_FACTS[item] for item in active_reactivation_ids)
    return TopologyScenario(
        id="nominal-backup" if mask == 0 else f"shift-{mask:03b}",
        mutation_count=mask.bit_count(),
        initial_state=carriers,
        transitions=transitions,
        coverage=_coverage_for_transition_ids(transition_ids),
        protocol=multipath_protocol(),
    )


def topology_uncertainty_envelope() -> TopologyUncertaintyEnvelope:
    return TopologyUncertaintyEnvelope(
        "erasemap-prove-envelope-v1",
        "nominal-backup",
        len(OPTIONAL_TRANSITION_IDS),
        tuple(scenario_from_mask(mask) for mask in range(8)),
    )


def _controls_for_scenario(
    controls: tuple[StabilizationControl, ...], scenario: TopologyScenario
) -> tuple[StabilizationControl, ...]:
    transition_ids = frozenset(item.id for item in scenario.transitions)
    return tuple(
        StabilizationControl(
            item.id,
            item.cost,
            item.guarded_transition_ids & transition_ids,
            item.permitted,
        )
        for item in controls
        if item.guarded_transition_ids & transition_ids
    )


def nominal_plan(
    envelope: TopologyUncertaintyEnvelope | None = None,
    controls: tuple[StabilizationControl, ...] | None = None,
) -> StabilizationPlan:
    selected_envelope = envelope or topology_uncertainty_envelope()
    selected_controls = controls or multipath_controls()
    scenario = selected_envelope.nominal
    return exact_stabilization_cut(
        scenario.initial_state,
        scenario.transitions,
        scenario.coverage,
        scenario.protocol,
        _controls_for_scenario(selected_controls, scenario),
    )


def robust_plan(
    envelope: TopologyUncertaintyEnvelope | None = None,
    controls: tuple[StabilizationControl, ...] | None = None,
) -> RobustStabilizationPlan:
    return exact_robust_stabilization_cut(
        envelope or topology_uncertainty_envelope(), controls or multipath_controls()
    )


def brute_force_robust_oracle(
    envelope: TopologyUncertaintyEnvelope,
    controls: tuple[StabilizationControl, ...],
) -> tuple[tuple[str, ...], int, str]:
    permitted = tuple(item for item in controls if item.permitted)
    best: tuple[int, int, tuple[str, ...]] | None = None
    for size in range(len(permitted) + 1):
        for chosen in itertools.combinations(permitted, size):
            safe = True
            for scenario in envelope.scenarios:
                transition_ids = frozenset(item.id for item in scenario.transitions)
                guards = frozenset().union(
                    *(item.guarded_transition_ids for item in chosen)
                )
                report = evaluate_rse(
                    scenario.initial_state,
                    scenario.transitions,
                    scenario.coverage,
                    scenario.protocol,
                    guarded_transition_ids=guards & transition_ids,
                )
                if report.verdict is not RSEVerdict.RSE_VERIFIED:
                    safe = False
                    break
            if not safe:
                continue
            ids = tuple(sorted(item.id for item in chosen))
            key = (sum(item.cost for item in chosen), len(ids), ids)
            if best is None or key < best:
                best = key
    if best is None:
        return (), 0, StabilizationStatus.INFEASIBLE.value
    return best[2], best[0], StabilizationStatus.OPTIMAL.value


def run_robust_physical_trial(
    root: str | Path,
    *,
    scenario_mask: int,
    seed: int,
    selected_nominal_plan: StabilizationPlan | None = None,
    selected_robust_plan: RobustStabilizationPlan | None = None,
) -> RobustPhysicalTrial:
    if scenario_mask == 0:
        raise ValueError("physical topology-shift trial requires a non-nominal mask")
    started = time.perf_counter()
    scenario = scenario_from_mask(scenario_mask)
    nominal = selected_nominal_plan or nominal_plan()
    robust = selected_robust_plan or robust_plan()
    if not nominal.complete or not robust.complete:
        raise ValueError("physical trial requires complete nominal and robust plans")
    oracle_ids, oracle_cost, oracle_status = brute_force_robust_oracle(
        topology_uncertainty_envelope(), multipath_controls()
    )
    if oracle_status != StabilizationStatus.OPTIMAL.value:
        raise ValueError("frozen temporal oracle unexpectedly found no plan")

    carriers = scenario.initial_state
    lab = MultiCarrierStorageLab(root, seed=seed, carriers=carriers)
    uncontrolled = lab.replay_registered_workflows()
    lab.reset_online()
    lab.install_controls(nominal.control_ids)
    after_nominal = lab.replay_registered_workflows()
    lab.reset_online()
    lab.install_controls(robust.control_ids)
    after_robust = lab.replay_registered_workflows()
    scenario_transition_ids = frozenset(item.id for item in scenario.transitions)
    nominal_shift_report = evaluate_rse(
        scenario.initial_state,
        scenario.transitions,
        scenario.coverage,
        scenario.protocol,
        guarded_transition_ids=(
            control_guard_ids(nominal.control_ids) & scenario_transition_ids
        ),
    )
    witness = nominal_shift_report.shortest_witness
    if nominal_shift_report.verdict is not RSEVerdict.REGENERATION_RISK or witness is None:
        raise ValueError("shifted scenario did not expose an adversarial witness")
    return RobustPhysicalTrial(
        case_id=f"mask-{scenario_mask}-{seed}",
        scenario_id=scenario.id,
        scenario_mask=scenario_mask,
        seed=seed,
        active_carriers=tuple(sorted(carriers)),
        nominal_control_ids=nominal.control_ids,
        nominal_cost=nominal.total_cost,
        robust_control_ids=robust.control_ids,
        robust_cost=robust.total_cost,
        robustness_premium=robust.total_cost - nominal.total_cost,
        adversarial_witness=witness,
        uncontrolled_regeneration=uncontrolled,
        nominal_plan_regeneration=after_nominal,
        robust_post_control_regeneration=after_robust,
        oracle_control_ids=oracle_ids,
        oracle_cost=oracle_cost,
        oracle_match=(
            robust.control_ids == oracle_ids and robust.total_cost == oracle_cost
        ),
        runtime_milliseconds=(time.perf_counter() - started) * 1000.0,
    )
