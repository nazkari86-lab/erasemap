from __future__ import annotations

import json
from pathlib import Path

import pytest

from erasemap.open_transfer import (
    TransferCaseRecord,
    expected_case_id,
    transfer_record_from_payload,
)
from erasemap.open_transfer_evidence import canonical_json, sha256_bytes
from experiments.run_open_transfer_v1 import core_sha256, write_result_bundle
from scripts.verify_open_transfer_v1 import core_sha256 as verifier_core_sha256
from scripts.verify_open_transfer_v1 import verify_result

PROTOCOL_PATH = Path("benchmark/open-transfer-v1.json")


def test_offline_verifier_recomputes_core_without_runner_import() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    assert verifier_core_sha256(protocol) == core_sha256(protocol)


PROTOCOL = json.loads(PROTOCOL_PATH.read_text())


def passing_records() -> tuple[TransferCaseRecord, ...]:
    core_hash = core_sha256(PROTOCOL)
    records = []
    for family in PROTOCOL["families"]:
        for seed in PROTOCOL["seeds"]:
            for fault in PROTOCOL["fault_states"]:
                truth = PROTOCOL["truth_by_fault_state"][fault]
                complete = truth == "COMPLETE"
                selected = () if complete or fault == "coverage_fault" else ("control",)
                records.append(
                    TransferCaseRecord(
                        case_id=expected_case_id(family["id"], seed, fault),
                        family=family["id"],
                        seed=seed,
                        fault_state=fault,
                        truth=truth,
                        native_complete=True,
                        typed_complete=complete or fault == "recovery_regeneration",
                        erasemap_verdict=("UNVERIFIED" if fault == "coverage_fault" else truth),
                        shortest_witness=(("source", "sink") if truth == "INCOMPLETE" else None),
                        selected_control_ids=selected,
                        selected_cost=0 if not selected else 3,
                        oracle_control_ids=selected,
                        oracle_cost=0 if not selected else 3,
                        post_control_recurrence=False,
                        retained_loss=False,
                        core_sha256=core_hash,
                        service_image=family["image"],
                        service_version=family["version"],
                        evidence_sha256="sha256:" + "c" * 64,
                        process_observed=True,
                        remediation_milliseconds=1.0,
                        bytes_rewritten=10,
                    )
                )
    return tuple(records)


def support_files(root: Path) -> tuple[Path, ...]:
    files = (
        root / "assets" / "olivetti-transfer-v1.npz",
        root / "assets" / "PROVENANCE.json",
        root / "evidence" / "keycloak-identity.jsonl",
        root / "evidence" / "mlflow-lineage.jsonl",
        root / "evidence" / "qdrant-biometric.jsonl",
    )
    for index, path in enumerate(files):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json({"fixture": index}) + b"\n")
    return files


def test_result_bundle_round_trips_and_is_offline_verifiable(tmp_path: Path) -> None:
    files = support_files(tmp_path)
    result = write_result_bundle(
        passing_records(),
        PROTOCOL,
        PROTOCOL_PATH,
        tmp_path,
        support_artifacts=files,
        run_kind="TEST_FIXTURE",
    )
    assert result["summary"]["decision"] == "PASS"
    verified = verify_result(tmp_path / "result.json")
    assert verified["passed"] is True
    assert verified["case_count"] == 60
    assert len((tmp_path / "trials.jsonl").read_text().splitlines()) == 60


def test_verifier_rejects_tampered_trial_and_extra_artifact(tmp_path: Path) -> None:
    files = support_files(tmp_path)
    write_result_bundle(
        passing_records(), PROTOCOL, PROTOCOL_PATH, tmp_path, support_artifacts=files
    )
    trials = tmp_path / "trials.jsonl"
    trials.write_bytes(trials.read_bytes() + canonical_json({"tampered": True}) + b"\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_result(tmp_path / "result.json")

    clean = tmp_path / "clean"
    clean_files = support_files(clean)
    write_result_bundle(
        passing_records(), PROTOCOL, PROTOCOL_PATH, clean, support_artifacts=clean_files
    )
    (clean / "unexpected.txt").write_text("extra")
    with pytest.raises(ValueError, match="unexpected result artifact"):
        verify_result(clean / "result.json")


def test_result_writer_is_non_overwriting_and_deterministic(tmp_path: Path) -> None:
    files = support_files(tmp_path)
    records = passing_records()
    write_result_bundle(records, PROTOCOL, PROTOCOL_PATH, tmp_path, support_artifacts=files)
    first_trials = (tmp_path / "trials.jsonl").read_bytes()
    assert sha256_bytes(first_trials).startswith("sha256:")
    with pytest.raises(FileExistsError, match="result output"):
        write_result_bundle(records, PROTOCOL, PROTOCOL_PATH, tmp_path, support_artifacts=files)


def test_trial_parser_rejects_coerced_boolean() -> None:
    payload = passing_records()[0].payload()
    payload["native_complete"] = "false"
    with pytest.raises(ValueError, match="boolean field"):
        transfer_record_from_payload(payload)
