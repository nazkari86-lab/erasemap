import pytest

from erasemap.domain import ArtifactState, ArtifactType, Evidence, EvidenceKind
from erasemap.evidence import validate_evidence
from tests.factories import artifact


def test_signed_statement_does_not_prove_template_absence() -> None:
    node = artifact(type=ArtifactType.BIOMETRIC_TEMPLATE, state=ArtifactState.ERASED)
    evidence = Evidence("ev", node.id, EvidenceKind.SIGNED_STATEMENT, valid_signature=True)
    result = validate_evidence(node, evidence, now_epoch=100)
    assert not result.valid
    assert result.reason == "template requires committed absence evidence"


def test_pending_backup_is_not_erased() -> None:
    node = artifact(type=ArtifactType.BACKUP_COPY, state=ArtifactState.WAITING_EXPIRY)
    evidence = Evidence(
        "ev",
        node.id,
        EvidenceKind.EXPIRY_SCHEDULE,
        issued_epoch=50,
        expires_epoch=200,
    )
    result = validate_evidence(node, evidence, now_epoch=100)
    assert result.valid
    assert result.effective_state is ArtifactState.WAITING_EXPIRY


def test_absence_check_must_bind_commitment_and_observe_absence() -> None:
    node = artifact(state=ArtifactState.ERASED, commitment="sha256:expected")
    evidence = Evidence(
        "ev",
        node.id,
        EvidenceKind.ABSENCE_CHECK,
        commitment="sha256:wrong",
        observed_absent=True,
    )
    assert validate_evidence(node, evidence, now_epoch=100).reason == "commitment mismatch"


def test_model_audit_requires_frozen_protocol_reference_and_pass() -> None:
    node = artifact(type=ArtifactType.MODEL_INFLUENCE, state=ArtifactState.ERASED)
    evidence = Evidence(
        "ev",
        node.id,
        EvidenceKind.MODEL_AUDIT,
        metadata=(("protocol_id", "v1"), ("reference_id", "retrain-1"), ("pass", "true")),
    )
    assert validate_evidence(node, evidence, now_epoch=100).valid


def test_negative_clock_is_programmer_error() -> None:
    node = artifact()
    evidence = Evidence("ev", node.id, EvidenceKind.SIGNED_STATEMENT)
    with pytest.raises(ValueError, match="now_epoch"):
        validate_evidence(node, evidence, now_epoch=-1)
