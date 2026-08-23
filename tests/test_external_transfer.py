from __future__ import annotations

import json
from pathlib import Path

import pytest

from external_transfer.attest import generate_keypair, sha256_bytes, sign_manifest
from external_transfer.verify import AUTHORSHIP_DECLARATION, verify_submission

IMAGE = "registry.example/service@sha256:" + "a" * 64
CORE = "sha256:" + "b" * 64


def valid_submission(root: Path) -> dict[str, object]:
    result_path = root / "raw" / "result.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text('{"decision":"PASS"}\n')
    result_hash = sha256_bytes(result_path.read_bytes())
    manifest: dict[str, object] = {
        "schema_version": "erasemap-external-transfer-manifest-v1",
        "evaluation_id": "external-001",
        "evaluator_name": "External Evaluator",
        "evaluator_contact": "https://example.org/evaluator",
        "evaluator_status": "independent_person",
        "organization": "",
        "authorship_declaration": AUTHORSHIP_DECLARATION,
        "started_at": "2026-08-23T00:00:00Z",
        "ended_at": "2026-08-23T01:00:00Z",
        "clean_commit": "c" * 40,
        "core_sha256": CORE,
        "service_images": {"external-family": IMAGE},
        "artifacts": {"raw/result.json": result_hash},
        "result_sha256": result_hash,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    private, _ = generate_keypair()
    (root / "attestation.json").write_text(
        json.dumps(sign_manifest(manifest, private), sort_keys=True) + "\n"
    )
    return manifest


def test_signed_external_submission_verifies_but_keeps_identity_review() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        root = Path(directory)
        valid_submission(root)
        result = verify_submission(root)
        assert result["technical_decision"] == "PASS"
        assert result["identity_and_conflict_review"] == "REQUIRED"


def test_missing_authorship_or_identity_is_rejected(tmp_path: Path) -> None:
    manifest = valid_submission(tmp_path)
    manifest.pop("authorship_declaration")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest) + "\n")
    with pytest.raises(ValueError, match="schema mismatch"):
        verify_submission(tmp_path)


def test_tampered_artifact_is_rejected(tmp_path: Path) -> None:
    valid_submission(tmp_path)
    (tmp_path / "raw" / "result.json").write_text('{"decision":"CHANGED"}\n')
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        verify_submission(tmp_path)


def test_results_directory_contains_no_fabricated_submission() -> None:
    files = sorted(path.name for path in Path("external_transfer/results").iterdir())
    assert files == ["README.md"]
