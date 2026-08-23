from __future__ import annotations

import json
from pathlib import Path

import pytest

from erasemap.open_transfer_evidence import (
    EvidenceLedger,
    assert_no_secrets,
    canonical_evidence,
    canonical_json,
    sha256_bytes,
    sha256_file,
)


def test_evidence_redacts_credentials_before_hashing() -> None:
    record = canonical_evidence(
        method="post",
        url="http://127.0.0.1/token?access_token=secret&view=full",
        request_headers={
            "Authorization": "Bearer secret",
            "Content-Type": "application/json",
            "Cookie": "session=secret",
        },
        request_body={
            "password": "secret",
            "user": "subject-1",
            "nested": {"client_secret": "secret", "safe": 3},
        },
        status=204,
        response_body={"token": "secret", "kept": True},
    )
    encoded = canonical_json(record)
    assert b'":"secret"' not in encoded
    assert b"Bearer secret" not in encoded
    assert b"session=secret" not in encoded
    assert b"[REDACTED]" in encoded
    assert record["method"] == "POST"
    assert sha256_bytes(encoded).startswith("sha256:")
    assert canonical_json(json.loads(encoded)) == encoded


def test_evidence_rejects_invalid_method_status_and_url() -> None:
    with pytest.raises(ValueError, match="method"):
        canonical_evidence(
            method="TRACE",
            url="http://127.0.0.1/status",
            request_headers={},
            request_body=None,
            status=200,
            response_body={},
        )
    with pytest.raises(ValueError, match="status"):
        canonical_evidence(
            method="GET",
            url="http://127.0.0.1/status",
            request_headers={},
            request_body=None,
            status=700,
            response_body={},
        )
    with pytest.raises(ValueError, match="URL"):
        canonical_evidence(
            method="GET",
            url="file:///etc/passwd",
            request_headers={},
            request_body=None,
            status=200,
            response_body={},
        )


def test_ledger_is_append_only_and_rejects_duplicate_evidence(tmp_path: Path) -> None:
    path = tmp_path / "evidence.jsonl"
    ledger = EvidenceLedger(path)
    record = canonical_evidence(
        method="GET",
        url="http://127.0.0.1/status",
        request_headers={},
        request_body=None,
        status=200,
        response_body={"status": "ok"},
    )
    digest = ledger.append(record)
    assert digest == sha256_bytes(canonical_json(record))
    assert ledger.records() == (record,)
    with pytest.raises(ValueError, match="duplicate evidence"):
        ledger.append(record)


def test_ledger_rejects_existing_invalid_json_or_hash(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.jsonl"
    malformed.write_text("not-json\n")
    with pytest.raises(ValueError, match="invalid evidence JSONL"):
        EvidenceLedger(malformed)

    changed = tmp_path / "changed.jsonl"
    changed.write_text('{"evidence_sha256":"sha256:' + "0" * 64 + '","record":{}}\n')
    with pytest.raises(ValueError, match="evidence hash mismatch"):
        EvidenceLedger(changed)


def test_secret_scan_and_file_hash(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"public artifact")
    assert sha256_file(path) == sha256_bytes(b"public artifact")
    assert_no_secrets({"safe": "value"}, ("hidden",))
    with pytest.raises(ValueError, match="secret value"):
        assert_no_secrets({"leak": "prefix-hidden-suffix"}, ("hidden",))
