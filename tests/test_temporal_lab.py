from erasemap.temporal_lab import run_temporal_lab_trial


def test_real_storage_workflow_regenerates_then_tombstone_blocks(tmp_path) -> None:
    trial = run_temporal_lab_trial(tmp_path / "lab", seed=17)

    assert trial.snapshot_complete
    assert trial.retained_backup_carrier
    assert trial.regenerated_without_control
    assert trial.rse_verdict == "REGENERATION_RISK"
    assert trial.shortest_witness == ("backup_restore",)
    assert trial.coverage_complete
    assert trial.selected_controls == ("persistent-subject-tombstone",)
    assert trial.selected_cost == 7
    assert not trial.regenerated_after_control
