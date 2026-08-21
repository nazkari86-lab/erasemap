import hashlib
from pathlib import Path

import numpy as np

from erasemap.domain import AuditStatus
from erasemap.storage_lab import RegisteredStoreLab


def test_source_only_deletion_leaves_four_real_residual_stores(tmp_path: Path) -> None:
    lab = RegisteredStoreLab(tmp_path)
    lab.enroll("person-1", np.array([0.1, 0.2, 0.3], dtype=np.float32))

    lab.delete_source_only("person-1")
    audit = lab.audit("person-1", now_epoch=100)

    assert audit.result.status is AuditStatus.INCOMPLETE
    assert audit.residual_store_ids == frozenset(
        {"backup", "cache", "model", "vector-index"}
    )
    assert audit.result.shortest_path is not None
    assert audit.result.shortest_path.node_ids[0] == "sqlite-source"


def test_remediation_physically_clears_or_crypto_erases_registered_stores(
    tmp_path: Path,
) -> None:
    lab = RegisteredStoreLab(tmp_path)
    lab.enroll("person-1", np.array([0.1, 0.2, 0.3], dtype=np.float32))
    lab.delete_source_only("person-1")

    lab.remediate("person-1")
    audit = lab.audit("person-1", now_epoch=100)

    assert audit.result.status is AuditStatus.COMPLETE
    assert not audit.residual_store_ids
    assert not lab.backup_key_path("person-1").exists()
    assert lab.registered_presence("person-1") == {
        "backup": False,
        "cache": False,
        "model": False,
        "sqlite-source": False,
        "vector-index": False,
    }


def test_audit_is_reproducible_without_exposing_subject_in_json_files(
    tmp_path: Path,
) -> None:
    lab = RegisteredStoreLab(tmp_path)
    lab.enroll("sensitive-name", np.array([1.0, 0.0], dtype=np.float32))

    first = lab.registered_presence("sensitive-name")
    second = lab.registered_presence("sensitive-name")

    assert first == second
    for path in tmp_path.glob("*.json"):
        assert "sensitive-name" not in path.read_text()
    plain_digest = hashlib.sha256(b"sensitive-name").hexdigest()
    assert plain_digest.encode() not in lab.database_path.read_bytes()
    assert lab.commitment_key_path.stat().st_mode & 0o777 == 0o600
    assert lab.backup_key_path("sensitive-name").stat().st_mode & 0o777 == 0o600


def test_commitment_key_must_be_256_bits(tmp_path: Path) -> None:
    try:
        RegisteredStoreLab(tmp_path, commitment_key=b"short")
    except ValueError as error:
        assert "256 bits" in str(error)
    else:
        raise AssertionError("short commitment key was accepted")
