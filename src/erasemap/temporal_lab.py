from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from erasemap.storage_lab import RegisteredStoreLab
from erasemap.temporal import (
    RSEProtocol,
    StabilizationControl,
    TemporalTransition,
    TransitionCoverage,
    TransitionObservation,
    evaluate_rse,
    exact_stabilization_cut,
)


@dataclass(frozen=True, slots=True)
class TemporalLabTrial:
    seed: int
    snapshot_complete: bool
    regenerated_without_control: bool
    rse_verdict: str
    shortest_witness: tuple[str, ...]
    coverage_complete: bool
    selected_controls: tuple[str, ...]
    selected_cost: int
    regenerated_after_control: bool
    retained_backup_carrier: bool

    def payload(self) -> dict[str, object]:
        return asdict(self)


def registered_temporal_case() -> tuple[
    frozenset[str],
    tuple[TemporalTransition, ...],
    TransitionCoverage,
    RSEProtocol,
    tuple[StabilizationControl, ...],
]:
    initial_state = frozenset({"recoverable-backup"})
    transitions = (
        TemporalTransition(
            "backup_restore",
            frozenset({"recoverable-backup"}),
            frozenset({"postgres"}),
        ),
        TemporalTransition(
            "nightly_etl", frozenset({"postgres"}), frozenset({"cache"})
        ),
        TemporalTransition(
            "vector_rebuild", frozenset({"postgres"}), frozenset({"vector-index"})
        ),
        TemporalTransition(
            "model_retrain", frozenset({"vector-index"}), frozenset({"model"})
        ),
    )
    coverage = TransitionCoverage(
        frozenset({"backup-audit", "pipeline-audit"}),
        (
            TransitionObservation(
                "observed-backup-restore", "backup-audit", "backup_restore", True
            ),
            TransitionObservation(
                "observed-etl", "pipeline-audit", "nightly_etl", True
            ),
            TransitionObservation(
                "observed-vector", "pipeline-audit", "vector_rebuild", True
            ),
            TransitionObservation(
                "observed-training", "pipeline-audit", "model_retrain", True
            ),
        ),
    )
    protocol = RSEProtocol(
        "regeneration-safe-erasure-v1",
        frozenset({"postgres", "cache", "vector-index", "model"}),
    )
    controls = (
        StabilizationControl(
            "persistent-subject-tombstone", 7, frozenset({"backup_restore"})
        ),
        StabilizationControl(
            "destroy-recoverable-backup", 40, frozenset({"backup_restore"})
        ),
    )
    return initial_state, transitions, coverage, protocol, controls


def run_temporal_lab_trial(root: str | Path, *, seed: int) -> TemporalLabTrial:
    lab = RegisteredStoreLab(root, commitment_key=bytes([seed % 251 + 1]) * 32)
    subject_id = f"temporal-subject-{seed}"
    vector = np.random.default_rng(seed).normal(size=16).astype(np.float32)
    lab.enroll(subject_id, vector)
    lab.delete_online_keep_recoverable_backup(subject_id)
    snapshot_complete = not any(lab.online_presence(subject_id).values())
    retained_backup = lab.registered_presence(subject_id)["backup"]

    initial, transitions, coverage, protocol, controls = registered_temporal_case()
    report = evaluate_rse(initial, transitions, coverage, protocol)
    plan = exact_stabilization_cut(
        initial, transitions, coverage, protocol, controls
    )

    restored = lab.restore_backup_to_source(subject_id)
    propagated = lab.rebuild_online_derivatives(subject_id)
    regenerated_without = restored and propagated and any(
        lab.online_presence(subject_id).values()
    )

    lab.delete_online_keep_recoverable_backup(subject_id)
    if "persistent-subject-tombstone" in plan.control_ids:
        lab.install_persistent_tombstone(subject_id)
    restored_after = lab.restore_backup_to_source(subject_id)
    lab.rebuild_online_derivatives(subject_id)
    regenerated_after = restored_after or any(lab.online_presence(subject_id).values())

    return TemporalLabTrial(
        seed=seed,
        snapshot_complete=snapshot_complete,
        regenerated_without_control=regenerated_without,
        rse_verdict=report.verdict.value,
        shortest_witness=report.shortest_witness or (),
        coverage_complete=report.coverage.complete,
        selected_controls=plan.control_ids,
        selected_cost=plan.total_cost,
        regenerated_after_control=regenerated_after,
        retained_backup_carrier=retained_backup,
    )
