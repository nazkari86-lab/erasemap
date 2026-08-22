from __future__ import annotations

import json
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from erasemap.audit import audit_subject
from erasemap.domain import AuditResult, ErasureGraph, Evidence, EvidenceKind

SCHEMA_VERSION = "erasemap-evidence-envelope-v1"


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _evidence_payload(evidence: Evidence) -> dict[str, Any]:
    return {
        "artifact_id": evidence.artifact_id,
        "commitment": evidence.commitment,
        "expires_epoch": evidence.expires_epoch,
        "id": evidence.id,
        "issued_epoch": evidence.issued_epoch,
        "kind": evidence.kind.value,
        "metadata": [list(item) for item in evidence.metadata],
        "observed_absent": evidence.observed_absent,
    }


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    schema_version: str
    key_id: str
    nonce: str
    evidence: Evidence
    signature: bytes

    def payload(self) -> dict[str, Any]:
        return {
            "evidence": _evidence_payload(self.evidence),
            "key_id": self.key_id,
            "nonce": self.nonce,
            "schema_version": self.schema_version,
        }

    def serialized(self) -> dict[str, Any]:
        return {**self.payload(), "signature": self.signature.hex()}


@dataclass(frozen=True, slots=True)
class EvidenceEnvelopeVerification:
    valid: bool
    reason: str
    evidence: Evidence | None = None


class EvidenceEnvelopeLedger:
    def __init__(self, entries: Iterable[tuple[str, str]] = ()) -> None:
        self._nonces: set[tuple[str, str]] = set(entries)

    def contains(self, key_id: str, nonce: str) -> bool:
        return (key_id, nonce) in self._nonces

    def record(self, key_id: str, nonce: str) -> None:
        if not key_id or not nonce:
            raise ValueError("key id and nonce are required")
        self._nonces.add((key_id, nonce))

    def entries(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._nonces))


def evidence_envelope_from_payload(payload: Any) -> EvidenceEnvelope:
    if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), dict):
        raise ValueError("evidence envelope must be an object")
    raw = payload["evidence"]
    metadata = raw.get("metadata", [])
    return EvidenceEnvelope(
        schema_version=str(payload["schema_version"]),
        key_id=str(payload["key_id"]),
        nonce=str(payload["nonce"]),
        evidence=Evidence(
            id=str(raw["id"]),
            artifact_id=str(raw["artifact_id"]),
            kind=EvidenceKind(str(raw["kind"])),
            commitment=str(raw.get("commitment", "")),
            observed_absent=bool(raw.get("observed_absent", False)),
            issued_epoch=int(raw.get("issued_epoch", 0)),
            expires_epoch=(
                int(raw["expires_epoch"])
                if raw.get("expires_epoch") is not None
                else None
            ),
            metadata=tuple((str(key), str(value)) for key, value in metadata),
        ),
        signature=bytes.fromhex(str(payload["signature"])),
    )


def issue_evidence_envelope(
    private_key: Ed25519PrivateKey,
    key_id: str,
    evidence: Evidence,
    *,
    nonce: str | None = None,
) -> EvidenceEnvelope:
    if not key_id:
        raise ValueError("key id is required")
    envelope = EvidenceEnvelope(
        schema_version=SCHEMA_VERSION,
        key_id=key_id,
        nonce=nonce or secrets.token_hex(16),
        evidence=replace(evidence, valid_signature=False),
        signature=b"",
    )
    return replace(
        envelope,
        signature=private_key.sign(_canonical_json(envelope.payload())),
    )


def verify_evidence_envelope(
    trust_store: Mapping[str, Ed25519PublicKey],
    envelope: EvidenceEnvelope,
    ledger: EvidenceEnvelopeLedger,
    *,
    now_epoch: int,
    max_age_seconds: int | None = None,
) -> EvidenceEnvelopeVerification:
    if envelope.schema_version != SCHEMA_VERSION:
        return EvidenceEnvelopeVerification(False, "unsupported schema version")
    public_key = trust_store.get(envelope.key_id)
    if public_key is None:
        return EvidenceEnvelopeVerification(False, "untrusted key id")
    if ledger.contains(envelope.key_id, envelope.nonce):
        return EvidenceEnvelopeVerification(False, "replayed nonce")
    if envelope.evidence.issued_epoch > now_epoch:
        return EvidenceEnvelopeVerification(False, "evidence timestamp is in the future")
    if max_age_seconds is not None:
        if max_age_seconds < 0:
            raise ValueError("max age cannot be negative")
        if now_epoch - envelope.evidence.issued_epoch > max_age_seconds:
            return EvidenceEnvelopeVerification(False, "evidence is too old")
    try:
        public_key.verify(envelope.signature, _canonical_json(envelope.payload()))
    except InvalidSignature:
        return EvidenceEnvelopeVerification(False, "invalid signature")
    ledger.record(envelope.key_id, envelope.nonce)
    return EvidenceEnvelopeVerification(
        True,
        "valid signature and evidence envelope",
        replace(envelope.evidence, valid_signature=True),
    )


def audit_signed_subject(
    graph: ErasureGraph,
    envelopes_by_artifact: Mapping[str, EvidenceEnvelope],
    trust_store: Mapping[str, Ed25519PublicKey],
    subject_id: str,
    now_epoch: int,
    *,
    ledger: EvidenceEnvelopeLedger | None = None,
    max_age_seconds: int | None = None,
) -> AuditResult:
    active_ledger = ledger or EvidenceEnvelopeLedger()
    verified: dict[str, Evidence] = {}
    for artifact_id, envelope in envelopes_by_artifact.items():
        result = verify_evidence_envelope(
            trust_store,
            envelope,
            active_ledger,
            now_epoch=now_epoch,
            max_age_seconds=max_age_seconds,
        )
        if result.valid and result.evidence is not None:
            verified[artifact_id] = result.evidence
    return audit_subject(graph, verified, subject_id, now_epoch)
