from __future__ import annotations

from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    Evidence,
    EvidenceCheck,
    EvidenceKind,
)

_ABSENCE_TYPES = {
    ArtifactType.SOURCE_RECORD,
    ArtifactType.BIOMETRIC_TEMPLATE,
    ArtifactType.SEARCH_INDEX_ENTRY,
}


def _failed(reason: str, state: ArtifactState = ArtifactState.UNVERIFIED) -> EvidenceCheck:
    return EvidenceCheck(valid=False, reason=reason, effective_state=state)


def _valid(reason: str, state: ArtifactState) -> EvidenceCheck:
    return EvidenceCheck(valid=True, reason=reason, effective_state=state)


def _metadata(evidence: Evidence) -> dict[str, str]:
    return dict(evidence.metadata)


def _validate_common(
    artifact: Artifact,
    evidence: Evidence,
    now_epoch: int,
) -> EvidenceCheck | None:
    if evidence.artifact_id != artifact.id:
        return _failed("evidence belongs to a different artifact")
    if evidence.expires_epoch is not None and evidence.expires_epoch <= now_epoch:
        if not (
            artifact.type is ArtifactType.BACKUP_COPY
            and artifact.state is ArtifactState.ERASED
            and evidence.kind is EvidenceKind.CRYPTO_ERASURE
        ):
            return _failed("evidence expired")
    if artifact.state is ArtifactState.ACTIVE:
        return _failed("artifact remains active", ArtifactState.ACTIVE)
    if artifact.state is ArtifactState.UNVERIFIED:
        return _failed("artifact state is unverified")
    return None


def _validate_absence(artifact: Artifact, evidence: Evidence) -> EvidenceCheck:
    label = {
        ArtifactType.SOURCE_RECORD: "source record",
        ArtifactType.BIOMETRIC_TEMPLATE: "template",
        ArtifactType.SEARCH_INDEX_ENTRY: "index entry",
    }[artifact.type]
    if evidence.kind is not EvidenceKind.ABSENCE_CHECK:
        return _failed(f"{label} requires committed absence evidence")
    if not artifact.commitment:
        return _failed("artifact has no pre-deletion commitment")
    if evidence.commitment != artifact.commitment:
        return _failed("commitment mismatch")
    if not evidence.observed_absent:
        return _failed("absence was not observed")
    return _valid("committed artifact is absent", artifact.state)


def _validate_cache(artifact: Artifact, evidence: Evidence, now_epoch: int) -> EvidenceCheck:
    if evidence.kind is not EvidenceKind.CACHE_INVALIDATION:
        return _failed("cache requires invalidation evidence")
    deadline_raw = _metadata(evidence).get("propagation_deadline")
    if deadline_raw is None or not deadline_raw.isdigit():
        return _failed("cache evidence lacks a propagation deadline")
    if now_epoch < int(deadline_raw):
        return _failed("cache invalidation is still propagating", ArtifactState.WAITING_EXPIRY)
    if not evidence.observed_absent:
        return _failed("cache absence was not observed")
    return _valid("cache invalidation propagated", artifact.state)


def _validate_backup(artifact: Artifact, evidence: Evidence, now_epoch: int) -> EvidenceCheck:
    if artifact.state is ArtifactState.WAITING_EXPIRY:
        if evidence.kind is not EvidenceKind.EXPIRY_SCHEDULE:
            return _failed("pending backup requires an expiry schedule")
        if evidence.expires_epoch is None:
            return _failed("backup schedule lacks an expiry time")
        if evidence.expires_epoch <= now_epoch:
            return _failed("backup expiry deadline passed")
        return _valid("backup has a future expiry schedule", ArtifactState.WAITING_EXPIRY)
    if evidence.kind is not EvidenceKind.CRYPTO_ERASURE:
        return _failed("erased backup requires cryptographic-erasure evidence")
    metadata = _metadata(evidence)
    if not evidence.valid_signature or metadata.get("key_destroyed") != "true":
        return _failed("backup key destruction is not attested")
    return _valid("backup encryption key destruction is attested", artifact.state)


def _validate_model(artifact: Artifact, evidence: Evidence) -> EvidenceCheck:
    if evidence.kind is not EvidenceKind.MODEL_AUDIT:
        return _failed("model influence requires a frozen model audit")
    metadata = _metadata(evidence)
    if not metadata.get("protocol_id"):
        return _failed("model audit lacks a frozen protocol id")
    if not metadata.get("reference_id"):
        return _failed("model audit lacks an exact-retraining reference")
    if metadata.get("pass") != "true":
        return _failed("model audit did not pass")
    return _valid("model audit passed against exact retraining", artifact.state)


def validate_evidence(
    artifact: Artifact,
    evidence: Evidence,
    now_epoch: int,
) -> EvidenceCheck:
    if now_epoch < 0:
        raise ValueError("now_epoch cannot be negative")

    common = _validate_common(artifact, evidence, now_epoch)
    if common is not None:
        return common

    if artifact.state is ArtifactState.BLOCKED:
        metadata = _metadata(evidence)
        if (
            evidence.kind is EvidenceKind.SIGNED_STATEMENT
            and evidence.valid_signature
            and metadata.get("enforced") == "true"
            and metadata.get("control_id")
        ):
            return _valid("processing restriction is attested", ArtifactState.BLOCKED)
        return _failed("blocked artifact requires an enforced signed control")

    if artifact.type in _ABSENCE_TYPES:
        return _validate_absence(artifact, evidence)
    if artifact.type is ArtifactType.CACHE_ENTRY:
        return _validate_cache(artifact, evidence, now_epoch)
    if artifact.type is ArtifactType.BACKUP_COPY:
        return _validate_backup(artifact, evidence, now_epoch)
    if artifact.type is ArtifactType.MODEL_INFLUENCE:
        return _validate_model(artifact, evidence)
    if artifact.type is ArtifactType.AUDIT_RECEIPT:
        metadata = _metadata(evidence)
        if evidence.kind is not EvidenceKind.SIGNED_STATEMENT or not evidence.valid_signature:
            return _failed("audit receipt requires a valid signature")
        if metadata.get("replayed") == "true":
            return _failed("audit receipt nonce was replayed")
        graph_root = metadata.get("graph_root")
        expected_root = metadata.get("expected_graph_root")
        if not graph_root or not expected_root or graph_root != expected_root:
            return _failed("audit receipt graph root does not match")
        return _valid("receipt envelope is valid", artifact.state)
    return _failed("unsupported artifact type")
