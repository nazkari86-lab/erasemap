from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from erasemap.open_transfer import (
    ControlCandidate,
    PhysicalOutcome,
    TransferCaseRecord,
    decide_physical_outcome,
    expected_case_id,
    summarize_transfer,
)

PROTOCOL = json.loads(Path("benchmark/open-transfer-v1.json").read_text())
CORE_HASH = "sha256:" + "a" * 64
EVIDENCE_HASH = "sha256:" + "b" * 64


def record(family: str, seed: int, fault: str) -> TransferCaseRecord:
    truth = PROTOCOL["truth_by_fault_state"][fault]
    complete = truth == "COMPLETE"
    verdict = "UNVERIFIED" if fault == "coverage_fault" else truth
    selected = () if complete else ("subject-tombstone",)
    return TransferCaseRecord(
        case_id=expected_case_id(family, seed, fault),
        family=family,
        seed=seed,
        fault_state=fault,
        truth=truth,
        native_complete=True,
        typed_complete=complete or fault == "recovery_regeneration",
        erasemap_verdict=verdict,
        shortest_witness=None if complete or fault == "coverage_fault" else ("source", "sink"),
        selected_control_ids=selected,
        selected_cost=0 if complete else 7,
        oracle_control_ids=selected,
        oracle_cost=0 if complete else 7,
        post_control_recurrence=False,
        retained_loss=False,
        core_sha256=CORE_HASH,
        service_image=str(
            next(item["image"] for item in PROTOCOL["families"] if item["id"] == family)
        ),
        service_version=str(
            next(item["version"] for item in PROTOCOL["families"] if item["id"] == family)
        ),
        evidence_sha256=EVIDENCE_HASH,
        process_observed=True,
        remediation_milliseconds=1.0,
        bytes_rewritten=10,
    )


def frozen_passing_records() -> tuple[TransferCaseRecord, ...]:
    return tuple(
        record(family["id"], seed, fault)
        for family in PROTOCOL["families"]
        for seed in PROTOCOL["seeds"]
        for fault in PROTOCOL["fault_states"]
    )


def test_transfer_summary_passes_only_all_frozen_gates() -> None:
    summary = summarize_transfer(frozen_passing_records(), PROTOCOL, CORE_HASH)
    assert summary.decision == "PASS"
    assert summary.case_count == 60
    assert summary.family_count == 3
    assert summary.erasemap_false_complete_count == 0
    assert summary.post_control_recurrence_count == 0
    assert summary.core_diff_count == 0
    assert summary.coverage_fail_closed_count == 15
    assert summary.rotation_count == 3
    assert all(item.passed for item in summary.gates)


def test_one_false_complete_fails_the_entire_result() -> None:
    records = list(frozen_passing_records())
    records[1] = replace(records[1], erasemap_verdict="COMPLETE")
    summary = summarize_transfer(tuple(records), PROTOCOL, CORE_HASH)
    assert summary.decision == "FAIL"
    assert summary.erasemap_false_complete_count == 1
    assert not next(item for item in summary.gates if item.id == "erasemap_false_complete").passed


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("case_id", "wrong", "case id"),
        ("family", "unknown", "unknown family"),
        ("fault_state", "unknown", "unknown fault state"),
        ("erasemap_verdict", "RISK", "unknown EraSeMap verdict"),
        ("core_sha256", "bad", "core_sha256"),
        ("evidence_sha256", "bad", "evidence_sha256"),
        ("service_image", "qdrant/qdrant:latest", "immutable service image"),
        ("selected_cost", -1, "selected cost"),
        ("remediation_milliseconds", -1.0, "remediation time"),
        ("bytes_rewritten", -1, "bytes rewritten"),
    ],
)
def test_record_validation_rejects_invalid_fields(
    field: str, value: Any, message: str
) -> None:
    item = record("keycloak-identity", 3101, "safe_native")
    with pytest.raises(ValueError, match=message):
        replace(item, **{field: value})


def test_record_validation_rejects_truth_or_witness_inconsistency() -> None:
    item = record("keycloak-identity", 3101, "surviving_derivative")
    with pytest.raises(ValueError, match="truth does not match"):
        replace(item, truth="COMPLETE")
    with pytest.raises(ValueError, match="witness"):
        replace(item, shortest_witness=None)
    with pytest.raises(ValueError, match="oracle"):
        replace(item, oracle_cost=9)


def test_summary_rejects_duplicate_or_incomplete_matrix() -> None:
    records = frozen_passing_records()
    with pytest.raises(ValueError, match="duplicate case id"):
        summarize_transfer((*records, records[0]), PROTOCOL, CORE_HASH)
    with pytest.raises(ValueError, match="case matrix"):
        summarize_transfer(records[:-1], PROTOCOL, CORE_HASH)


def test_summary_fails_changed_core_retained_loss_recurrence_and_oracle() -> None:
    records = list(frozen_passing_records())
    records[0] = replace(records[0], core_sha256="sha256:" + "c" * 64)
    records[1] = replace(records[1], retained_loss=True)
    records[2] = replace(records[2], post_control_recurrence=True)
    records[3] = replace(
        records[3], oracle_control_ids=("different",), oracle_cost=7
    )
    summary = summarize_transfer(tuple(records), PROTOCOL, CORE_HASH)
    assert summary.decision == "FAIL"
    assert summary.core_diff_count == 1
    assert summary.retained_loss_count == 1
    assert summary.post_control_recurrence_count == 1
    assert summary.oracle_mismatch_count == 1


def test_summary_fails_specificity_drop_and_missing_process_observation() -> None:
    records = list(frozen_passing_records())
    records[0] = replace(records[0], erasemap_verdict="UNVERIFIED")
    records[4] = replace(records[4], process_observed=False)
    summary = summarize_transfer(tuple(records), PROTOCOL, CORE_HASH)
    assert summary.decision == "FAIL"
    assert summary.specificity_drop > 0
    assert summary.unobserved_process_count == 1


CONTROLS = (
    ControlCandidate("block-recovery", 3, frozenset({"recovery"})),
    ControlCandidate("delete-primary", 1, frozenset({"primary"})),
    ControlCandidate("erase-derivative", 3, frozenset({"derivative"})),
    ControlCandidate(
        "persistent-tombstone", 7, frozenset({"primary", "derivative", "recovery"})
    ),
)


@pytest.mark.parametrize(
    ("outcome", "verdict", "typed", "selected", "witness"),
    [
        (
            PhysicalOutcome(True, False, False, True, 10, 10),
            "COMPLETE",
            True,
            (),
            None,
        ),
        (
            PhysicalOutcome(True, True, False, True, 10, 10),
            "INCOMPLETE",
            False,
            ("erase-derivative",),
            ("materialized-derivative",),
        ),
        (
            PhysicalOutcome(True, False, True, True, 10, 10),
            "INCOMPLETE",
            True,
            ("block-recovery",),
            ("recovery-carrier", "replay", "primary-object"),
        ),
        (
            PhysicalOutcome(True, None, None, False, 10, 10),
            "UNVERIFIED",
            False,
            (),
            None,
        ),
    ],
)
def test_physical_outcome_decision_is_family_neutral_and_exact(
    outcome: PhysicalOutcome,
    verdict: str,
    typed: bool,
    selected: tuple[str, ...],
    witness: tuple[str, ...] | None,
) -> None:
    decision = decide_physical_outcome(outcome, CONTROLS)
    assert decision.erasemap_verdict == verdict
    assert decision.native_complete is True
    assert decision.typed_complete is typed
    assert decision.selected_control_ids == selected
    assert decision.oracle_control_ids == selected
    assert decision.shortest_witness == witness


def test_physical_outcome_selects_single_tombstone_on_three_way_tie() -> None:
    decision = decide_physical_outcome(
        PhysicalOutcome(False, True, True, True, 10, 10), CONTROLS
    )
    assert decision.selected_control_ids == ("persistent-tombstone",)
    assert decision.selected_cost == 7
    assert decision.oracle_control_ids == decision.selected_control_ids


def test_physical_outcome_rejects_invalid_counts_and_controls() -> None:
    with pytest.raises(ValueError, match="retained"):
        PhysicalOutcome(True, False, False, True, -1, 0)
    with pytest.raises(ValueError, match="control id"):
        decide_physical_outcome(
            PhysicalOutcome(True, True, False, True, 1, 1),
            (*CONTROLS, CONTROLS[0]),
        )
