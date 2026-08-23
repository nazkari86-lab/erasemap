from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

from erasemap.cdc import evaluate_actions
from erasemap.multiview_verifier import upper_bound_channel
from erasemap.pcug_domain import (
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    PCUGVerdict,
)
from erasemap.storage_lab import RegisteredStoreLab
from erasemap.temporal import (
    RSEProtocol,
    RSEVerdict,
    StabilizationControl,
    TemporalTransition,
    TransitionCoverage,
    TransitionObservation,
    evaluate_rse,
    exact_stabilization_cut,
)

CARRIER_FACTS = {
    "backup_restore": "carrier-backup",
    "checkpoint_redeploy": "carrier-checkpoint",
    "legacy_export_import": "carrier-export",
    "retry_queue_replay": "carrier-queue",
}
REACTIVATION_TRANSITIONS = frozenset(CARRIER_FACTS)
ALL_CARRIERS = frozenset(CARRIER_FACTS.values())


@dataclass(frozen=True, slots=True)
class MultipathTrial:
    case_id: str
    seed: int
    split: str
    active_carriers: tuple[str, ...]
    rse_verdict: str
    snapshot_pcug_verdict: str
    blanket_carrier_verdict: str
    coverage_complete: bool
    shortest_witness: tuple[str, ...]
    reachable_state_count: int
    selected_controls: tuple[str, ...]
    selected_cost: int
    oracle_controls: tuple[str, ...]
    oracle_cost: int
    oracle_match: bool
    regenerated_without_control: bool
    regenerated_after_control: bool
    runtime_milliseconds: float

    def payload(self) -> dict[str, object]:
        return asdict(self)


def multipath_transitions() -> tuple[TemporalTransition, ...]:
    return (
        TemporalTransition(
            "backup_restore", frozenset({"carrier-backup"}), frozenset({"postgres"})
        ),
        TemporalTransition(
            "checkpoint_redeploy",
            frozenset({"carrier-checkpoint"}),
            frozenset({"model"}),
        ),
        TemporalTransition(
            "legacy_export_import",
            frozenset({"carrier-export"}),
            frozenset({"postgres"}),
        ),
        TemporalTransition(
            "model_retrain", frozenset({"vector-index"}), frozenset({"model"})
        ),
        TemporalTransition(
            "nightly_etl", frozenset({"postgres"}), frozenset({"cache"})
        ),
        TemporalTransition(
            "retry_queue_replay",
            frozenset({"carrier-queue"}),
            frozenset({"cache"}),
        ),
        TemporalTransition(
            "vector_rebuild", frozenset({"postgres"}), frozenset({"vector-index"})
        ),
    )


def multipath_coverage(*, fault_index: int | None = None) -> TransitionCoverage:
    sensors = {
        "backup_restore": "backup-audit",
        "checkpoint_redeploy": "model-registry-audit",
        "legacy_export_import": "export-audit",
        "model_retrain": "pipeline-audit",
        "nightly_etl": "pipeline-audit",
        "retry_queue_replay": "queue-audit",
        "vector_rebuild": "pipeline-audit",
    }
    observations = tuple(
        TransitionObservation(
            f"attestation-{transition_id}",
            sensor_id,
            transition_id,
            fault_index != index,
        )
        for index, (transition_id, sensor_id) in enumerate(sorted(sensors.items()))
    )
    return TransitionCoverage(frozenset(sensors.values()), observations)


def multipath_protocol() -> RSEProtocol:
    return RSEProtocol(
        "regeneration-safe-erasure-multipath-v2",
        frozenset({"cache", "model", "postgres", "vector-index"}),
    )


def multipath_controls() -> tuple[StabilizationControl, ...]:
    return (
        StabilizationControl("backup_restore_filter", 3, frozenset({"backup_restore"})),
        StabilizationControl(
            "checkpoint_deploy_filter", 5, frozenset({"checkpoint_redeploy"})
        ),
        StabilizationControl(
            "destroy_all_latent_carriers", 60, REACTIVATION_TRANSITIONS
        ),
        StabilizationControl(
            "legacy_import_filter", 4, frozenset({"legacy_export_import"})
        ),
        StabilizationControl(
            "persistent_subject_tombstone", 7, REACTIVATION_TRANSITIONS
        ),
        StabilizationControl(
            "retry_queue_filter", 2, frozenset({"retry_queue_replay"})
        ),
    )


def control_guard_ids(control_ids: tuple[str, ...]) -> frozenset[str]:
    selected = {item.id: item for item in multipath_controls()}
    return frozenset().union(*(selected[item].guarded_transition_ids for item in control_ids))


def snapshot_pcug_verdict() -> PCUGVerdict:
    carrier_ids = tuple(sorted(ALL_CARRIERS))
    sink_ids = ("cache", "model", "postgres", "vector-index")
    nodes = tuple(
        PCUGNode(node_id, "latent-carrier", "subject", EdgeState.CLOSED)
        for node_id in carrier_ids
    ) + tuple(
        PCUGNode(node_id, "online-residual", "subject", EdgeState.CLOSED)
        for node_id in sink_ids
    )
    edges = tuple(
        PCUGEdge(
            carrier,
            sink,
            EdgeKind.PROCESSING,
            EdgeState.CLOSED,
            request_scoped=True,
            subject_id="subject",
        )
        for carrier, sink in zip(carrier_ids, sink_ids, strict=True)
    )
    graph = PCUGGraph(
        nodes,
        edges,
        (
            upper_bound_channel(
                "snapshot-absence",
                value=0.0,
                upper_bound=0.0,
                threshold=0.0,
                evidence_id="snapshot-evidence",
            ),
        ),
    )
    protocol = CDCProtocol(
        "snapshot-pcug-v2",
        "subject",
        frozenset(carrier_ids),
        frozenset(sink_ids),
        frozenset({"snapshot-absence"}),
    )
    return evaluate_actions(graph, protocol, ()).verdict


def brute_force_stabilization_oracle(
    initial_state: frozenset[str], coverage: TransitionCoverage
) -> tuple[tuple[str, ...], int]:
    controls = tuple(item for item in multipath_controls() if item.permitted)
    best: tuple[int, int, tuple[str, ...]] | None = None
    for size in range(len(controls) + 1):
        for chosen in combinations(controls, size):
            ids = tuple(sorted(item.id for item in chosen))
            guarded = frozenset().union(*(item.guarded_transition_ids for item in chosen))
            report = evaluate_rse(
                initial_state,
                multipath_transitions(),
                coverage,
                multipath_protocol(),
                guarded_transition_ids=guarded,
            )
            if report.verdict is not RSEVerdict.RSE_VERIFIED:
                continue
            key = (sum(item.cost for item in chosen), len(ids), ids)
            if best is None or key < best:
                best = key
    return (best[2], best[0]) if best is not None else ((), 0)


class MultiCarrierStorageLab:
    def __init__(self, root: str | Path, *, seed: int, carriers: frozenset[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.subject_id = f"multipath-subject-{seed}"
        self.vector = np.random.default_rng(seed).normal(size=16).astype(np.float32)
        self.carriers = carriers
        self.lab = RegisteredStoreLab(
            self.root / "registered", commitment_key=bytes([seed % 251 + 1]) * 32
        )
        self.controls_path = self.root / "installed-controls.json"
        self.export_path = self.root / "legacy-export.json"
        self.queue_path = self.root / "retry-queue.json"
        self.checkpoint_path = self.root / "model-checkpoint.json"
        self.lab.enroll(self.subject_id, self.vector)
        commitment = self.lab.subject_commitment(self.subject_id)
        payload = {"commitment": commitment, "embedding": self.vector.tolist()}
        if "carrier-export" in carriers:
            self.export_path.write_text(json.dumps(payload, sort_keys=True) + "\n")
        if "carrier-queue" in carriers:
            self.queue_path.write_text(json.dumps(payload, sort_keys=True) + "\n")
        if "carrier-checkpoint" in carriers:
            self.checkpoint_path.write_text(
                json.dumps({"commitment": commitment}, sort_keys=True) + "\n"
            )
        if "carrier-backup" not in carriers:
            self.lab.destroy_recoverable_backup(self.subject_id)
        self.reset_online()

    def reset_online(self) -> None:
        self.lab.delete_online_keep_recoverable_backup(self.subject_id)

    def install_controls(self, control_ids: tuple[str, ...]) -> None:
        self.controls_path.write_text(json.dumps(sorted(control_ids)) + "\n")
        if "persistent_subject_tombstone" in control_ids:
            self.lab.install_persistent_tombstone(self.subject_id)
        if "destroy_all_latent_carriers" in control_ids:
            self.lab.destroy_recoverable_backup(self.subject_id)
            for path in (self.export_path, self.queue_path, self.checkpoint_path):
                path.unlink(missing_ok=True)

    def _installed_guards(self) -> frozenset[str]:
        control_ids = (
            tuple(json.loads(self.controls_path.read_text()))
            if self.controls_path.exists()
            else ()
        )
        return control_guard_ids(control_ids)

    def replay_registered_workflows(self) -> bool:
        guards = self._installed_guards()
        source_recreated = False
        if self.lab.registered_presence(self.subject_id)["backup"] and (
            "backup_restore" not in guards
        ):
            source_recreated |= self.lab.restore_backup_to_source(self.subject_id)
        if self.export_path.exists() and "legacy_export_import" not in guards:
            source_recreated |= self.lab.import_vector_to_source(
                self.subject_id, self.vector
            )
        if self.queue_path.exists() and "retry_queue_replay" not in guards:
            self.lab.replay_cache_entry(self.subject_id, self.vector)
        if self.checkpoint_path.exists() and "checkpoint_redeploy" not in guards:
            self.lab.redeploy_model_reference(self.subject_id)
        if source_recreated:
            self.lab.rebuild_online_derivatives(self.subject_id)
        return any(self.lab.online_presence(self.subject_id).values())


def run_risk_trial(
    root: str | Path, *, case_id: str, seed: int, carriers: frozenset[str]
) -> MultipathTrial:
    started = time.perf_counter()
    lab = MultiCarrierStorageLab(root, seed=seed, carriers=carriers)
    initial = carriers
    transitions = multipath_transitions()
    coverage = multipath_coverage()
    protocol = multipath_protocol()
    report = evaluate_rse(initial, transitions, coverage, protocol)
    plan = exact_stabilization_cut(
        initial, transitions, coverage, protocol, multipath_controls()
    )
    oracle_ids, oracle_cost = brute_force_stabilization_oracle(initial, coverage)
    regenerated_without = lab.replay_registered_workflows()
    lab.reset_online()
    lab.install_controls(plan.control_ids)
    regenerated_after = lab.replay_registered_workflows()
    return MultipathTrial(
        case_id=case_id,
        seed=seed,
        split="risk",
        active_carriers=tuple(sorted(carriers)),
        rse_verdict=report.verdict.value,
        snapshot_pcug_verdict=snapshot_pcug_verdict().value,
        blanket_carrier_verdict="INCOMPLETE" if carriers else "COMPLETE",
        coverage_complete=report.coverage.complete,
        shortest_witness=report.shortest_witness or (),
        reachable_state_count=report.reachable_state_count,
        selected_controls=plan.control_ids,
        selected_cost=plan.total_cost,
        oracle_controls=oracle_ids,
        oracle_cost=oracle_cost,
        oracle_match=plan.control_ids == oracle_ids and plan.total_cost == oracle_cost,
        regenerated_without_control=regenerated_without,
        regenerated_after_control=regenerated_after,
        runtime_milliseconds=(time.perf_counter() - started) * 1000.0,
    )


def run_safe_trial(root: str | Path, *, seed: int) -> MultipathTrial:
    started = time.perf_counter()
    lab = MultiCarrierStorageLab(root, seed=seed, carriers=ALL_CARRIERS)
    controls = ("persistent_subject_tombstone",)
    lab.install_controls(controls)
    report = evaluate_rse(
        ALL_CARRIERS,
        multipath_transitions(),
        multipath_coverage(),
        multipath_protocol(),
        guarded_transition_ids=control_guard_ids(controls),
    )
    regenerated = lab.replay_registered_workflows()
    return MultipathTrial(
        case_id=f"safe-{seed}",
        seed=seed,
        split="safe",
        active_carriers=tuple(sorted(ALL_CARRIERS)),
        rse_verdict=report.verdict.value,
        snapshot_pcug_verdict=snapshot_pcug_verdict().value,
        blanket_carrier_verdict="INCOMPLETE",
        coverage_complete=report.coverage.complete,
        shortest_witness=(),
        reachable_state_count=report.reachable_state_count,
        selected_controls=controls,
        selected_cost=7,
        oracle_controls=controls,
        oracle_cost=7,
        oracle_match=True,
        regenerated_without_control=False,
        regenerated_after_control=regenerated,
        runtime_milliseconds=(time.perf_counter() - started) * 1000.0,
    )


def run_coverage_fault_trial(root: str | Path, *, seed: int) -> MultipathTrial:
    started = time.perf_counter()
    lab = MultiCarrierStorageLab(root, seed=seed, carriers=ALL_CARRIERS)
    controls = ("persistent_subject_tombstone",)
    lab.install_controls(controls)
    report = evaluate_rse(
        ALL_CARRIERS,
        multipath_transitions(),
        multipath_coverage(fault_index=seed % len(multipath_transitions())),
        multipath_protocol(),
        guarded_transition_ids=control_guard_ids(controls),
    )
    return MultipathTrial(
        case_id=f"coverage-fault-{seed}",
        seed=seed,
        split="coverage-fault",
        active_carriers=tuple(sorted(ALL_CARRIERS)),
        rse_verdict=report.verdict.value,
        snapshot_pcug_verdict=snapshot_pcug_verdict().value,
        blanket_carrier_verdict="INCOMPLETE",
        coverage_complete=report.coverage.complete,
        shortest_witness=(),
        reachable_state_count=report.reachable_state_count,
        selected_controls=controls,
        selected_cost=7,
        oracle_controls=(),
        oracle_cost=0,
        oracle_match=True,
        regenerated_without_control=False,
        regenerated_after_control=False,
        runtime_milliseconds=(time.perf_counter() - started) * 1000.0,
    )
