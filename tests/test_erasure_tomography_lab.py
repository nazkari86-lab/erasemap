from __future__ import annotations

from pathlib import Path

from erasemap.erasure_tomography import TomographyVerdict
from erasemap.erasure_tomography_lab import (
    default_probe_design,
    run_tomography_and_stabilize,
    run_tomography_round,
)


def test_coded_probe_localizes_backup_with_fewer_than_four_workflows(
    tmp_path: Path,
) -> None:
    trial = run_tomography_round(
        tmp_path,
        active_ids=("backup_restore",),
        seed=71,
    )

    assert trial.report.verdict is TomographyVerdict.LOCALIZED
    assert trial.report.support == ("backup_restore",)
    assert all(trial.workflow_evidence_complete)
    assert len(trial.observations) == 3
    assert len(trial.design.mechanism_ids) == 4
    assert len(set(trial.subject_commitments)) == len(trial.subject_commitments)


def test_each_registered_mechanism_is_exactly_localized(tmp_path: Path) -> None:
    for mechanism_id in default_probe_design().mechanism_ids:
        trial = run_tomography_round(
            tmp_path / mechanism_id,
            active_ids=(mechanism_id,),
            seed=100,
        )
        assert trial.report.verdict is TomographyVerdict.LOCALIZED
        assert trial.report.support == (mechanism_id,)


def test_localization_translates_to_robust_controls(tmp_path: Path) -> None:
    trial = run_tomography_and_stabilize(
        tmp_path,
        active_ids=("backup_restore",),
        seed=91,
    )

    assert trial.round.report.verdict is TomographyVerdict.LOCALIZED
    assert trial.transition_ids == ("backup_restore",)
    assert trial.plan is not None
    assert trial.plan.complete
    assert trial.plan.control_ids == ("backup_restore_filter",)
    assert trial.post_control_recurrence is False


def test_multiple_active_mechanisms_exceed_bound_and_fail_closed(
    tmp_path: Path,
) -> None:
    trial = run_tomography_round(
        tmp_path,
        active_ids=("backup_restore", "retry_queue_replay"),
        seed=123,
    )

    assert trial.report.verdict is TomographyVerdict.UNVERIFIED


def test_unknown_mechanism_forces_unverified(tmp_path: Path) -> None:
    trial = run_tomography_round(
        tmp_path,
        active_ids=("undocumented_restore",),
        seed=19,
    )

    assert trial.report.verdict is TomographyVerdict.UNVERIFIED


def test_skipped_workflow_forces_unverified(tmp_path: Path) -> None:
    trial = run_tomography_round(
        tmp_path,
        active_ids=("backup_restore",),
        seed=7,
        skipped_probe_index=1,
    )

    assert trial.report.verdict is TomographyVerdict.UNVERIFIED
    assert not all(trial.workflow_evidence_complete)


def test_subject_cross_contamination_forces_unverified(tmp_path: Path) -> None:
    trial = run_tomography_round(
        tmp_path,
        active_ids=("backup_restore",),
        seed=7,
        contaminate_subjects=True,
    )

    assert trial.report.verdict is TomographyVerdict.UNVERIFIED
    assert len(set(trial.subject_commitments)) == 1
