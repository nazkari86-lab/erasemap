from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SCHEMA_VERSION = "erasemap-temporal-erasure-certificate-v1"
_FIELDS = frozenset(
    {
        "action_signature_hash",
        "declared_verdict",
        "envelope_hash",
        "invalidation_conditions",
        "issued_epoch",
        "key_id",
        "model_set_hash",
        "not_after_epoch",
        "observations_hash",
        "policy_certificate_hash",
        "producer_revision",
        "proof_bundle_hash",
        "request_id",
        "schema_version",
        "signature",
        "topology_hash",
    }
)


class TemporalVerdict(StrEnum):
    COMPLETE_WITHIN_ENVELOPE = "COMPLETE_WITHIN_ENVELOPE"
    INCOMPLETE = "INCOMPLETE"
    OUT_OF_HYPOTHESIS = "OUT_OF_HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"


class CertificateStatus(StrEnum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class TemporalCertificate:
    schema_version: str
    key_id: str
    request_id: str
    issued_epoch: int
    not_after_epoch: int
    topology_hash: str
    envelope_hash: str
    model_set_hash: str
    observations_hash: str
    policy_certificate_hash: str
    proof_bundle_hash: str
    action_signature_hash: str
    declared_verdict: TemporalVerdict
    invalidation_conditions: tuple[str, ...]
    producer_revision: str
    signature: bytes


@dataclass(frozen=True, slots=True)
class TemporalVerificationContext:
    topology_hash: str
    envelope_hash: str
    model_set_hash: str
    observations_hash: str
    policy_certificate_hash: str
    proof_bundle_hash: str
    action_signature_hash: str
    replayed_verdict: TemporalVerdict
    topology_coverage_complete: bool
    observations_sound: bool
    controls_replayed: bool
    mandatory_channels_passed: bool


@dataclass(frozen=True, slots=True)
class TemporalCertificateCheck:
    status: CertificateStatus
    reason: str


def commitment(payload: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def issue_temporal_certificate(
    private_key: Ed25519PrivateKey,
    *,
    key_id: str,
    request_id: str,
    issued_epoch: int,
    not_after_epoch: int,
    context: TemporalVerificationContext,
    invalidation_conditions: tuple[str, ...],
    producer_revision: str,
    declared_verdict: TemporalVerdict | None = None,
) -> TemporalCertificate:
    if not key_id or not request_id or not producer_revision:
        raise ValueError("key, request, and producer revision are required")
    if issued_epoch < 0 or not_after_epoch <= issued_epoch:
        raise ValueError("certificate validity interval must be positive")
    if not invalidation_conditions:
        raise ValueError("at least one invalidation condition is required")
    if invalidation_conditions != tuple(sorted(set(invalidation_conditions))):
        raise ValueError("invalidation conditions must be sorted and unique")
    certificate = TemporalCertificate(
        schema_version=SCHEMA_VERSION,
        key_id=key_id,
        request_id=request_id,
        issued_epoch=issued_epoch,
        not_after_epoch=not_after_epoch,
        topology_hash=context.topology_hash,
        envelope_hash=context.envelope_hash,
        model_set_hash=context.model_set_hash,
        observations_hash=context.observations_hash,
        policy_certificate_hash=context.policy_certificate_hash,
        proof_bundle_hash=context.proof_bundle_hash,
        action_signature_hash=context.action_signature_hash,
        declared_verdict=declared_verdict or context.replayed_verdict,
        invalidation_conditions=invalidation_conditions,
        producer_revision=producer_revision,
        signature=b"",
    )
    return replace(certificate, signature=private_key.sign(_signed_payload(certificate)))


def check_temporal_certificate(
    certificate: TemporalCertificate,
    public_keys: dict[str, Ed25519PublicKey],
    context: TemporalVerificationContext,
    *,
    now_epoch: int,
) -> TemporalCertificateCheck:
    if certificate.schema_version != SCHEMA_VERSION:
        return TemporalCertificateCheck(CertificateStatus.INVALID, "unsupported schema version")
    public_key = public_keys.get(certificate.key_id)
    if public_key is None:
        return TemporalCertificateCheck(CertificateStatus.INVALID, "unknown signing key")
    try:
        public_key.verify(certificate.signature, _signed_payload(certificate))
    except InvalidSignature:
        return TemporalCertificateCheck(CertificateStatus.INVALID, "invalid signature")
    if now_epoch < certificate.issued_epoch:
        return TemporalCertificateCheck(CertificateStatus.INVALID, "certificate is not active")
    if now_epoch > certificate.not_after_epoch:
        return TemporalCertificateCheck(CertificateStatus.EXPIRED, "time window expired")

    commitments = (
        ("topology", certificate.topology_hash, context.topology_hash),
        ("envelope", certificate.envelope_hash, context.envelope_hash),
        ("model set", certificate.model_set_hash, context.model_set_hash),
        ("observations", certificate.observations_hash, context.observations_hash),
        (
            "policy certificate",
            certificate.policy_certificate_hash,
            context.policy_certificate_hash,
        ),
        ("proof bundle", certificate.proof_bundle_hash, context.proof_bundle_hash),
        (
            "action signature",
            certificate.action_signature_hash,
            context.action_signature_hash,
        ),
    )
    for label, declared, actual in commitments:
        if declared != actual:
            return TemporalCertificateCheck(
                CertificateStatus.EXPIRED,
                f"{label} commitment changed",
            )
    if certificate.declared_verdict is not context.replayed_verdict:
        return TemporalCertificateCheck(
            CertificateStatus.INVALID,
            "declared verdict differs from independent replay",
        )
    if certificate.declared_verdict is TemporalVerdict.COMPLETE_WITHIN_ENVELOPE:
        obligations = (
            context.topology_coverage_complete,
            context.observations_sound,
            context.controls_replayed,
            context.mandatory_channels_passed,
        )
        if not all(obligations):
            return TemporalCertificateCheck(
                CertificateStatus.INVALID,
                "complete verdict has an undischarged obligation",
            )
    return TemporalCertificateCheck(
        CertificateStatus.VALID,
        "signature, replay, commitments, and time window are valid",
    )


def encode_temporal_certificate(certificate: TemporalCertificate) -> str:
    payload = _payload(certificate)
    payload["signature"] = certificate.signature.hex()
    return _canonical(payload).decode()


def decode_temporal_certificate(encoded: str) -> TemporalCertificate:
    payload = json.loads(encoded)
    if not isinstance(payload, dict):
        raise ValueError("temporal certificate must be an object")
    extras = set(payload) - _FIELDS
    missing = _FIELDS - set(payload)
    if extras:
        raise ValueError(f"unknown temporal certificate field: {min(extras)}")
    if missing:
        raise ValueError(f"missing temporal certificate field: {min(missing)}")
    try:
        return TemporalCertificate(
            schema_version=str(payload["schema_version"]),
            key_id=str(payload["key_id"]),
            request_id=str(payload["request_id"]),
            issued_epoch=int(payload["issued_epoch"]),
            not_after_epoch=int(payload["not_after_epoch"]),
            topology_hash=str(payload["topology_hash"]),
            envelope_hash=str(payload["envelope_hash"]),
            model_set_hash=str(payload["model_set_hash"]),
            observations_hash=str(payload["observations_hash"]),
            policy_certificate_hash=str(payload["policy_certificate_hash"]),
            proof_bundle_hash=str(payload["proof_bundle_hash"]),
            action_signature_hash=str(payload["action_signature_hash"]),
            declared_verdict=TemporalVerdict(str(payload["declared_verdict"])),
            invalidation_conditions=tuple(str(item) for item in payload["invalidation_conditions"]),
            producer_revision=str(payload["producer_revision"]),
            signature=bytes.fromhex(str(payload["signature"])),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid temporal certificate payload") from exc


def _payload(certificate: TemporalCertificate) -> dict[str, Any]:
    return {
        "action_signature_hash": certificate.action_signature_hash,
        "declared_verdict": certificate.declared_verdict.value,
        "envelope_hash": certificate.envelope_hash,
        "invalidation_conditions": list(certificate.invalidation_conditions),
        "issued_epoch": certificate.issued_epoch,
        "key_id": certificate.key_id,
        "model_set_hash": certificate.model_set_hash,
        "not_after_epoch": certificate.not_after_epoch,
        "observations_hash": certificate.observations_hash,
        "policy_certificate_hash": certificate.policy_certificate_hash,
        "producer_revision": certificate.producer_revision,
        "proof_bundle_hash": certificate.proof_bundle_hash,
        "request_id": certificate.request_id,
        "schema_version": certificate.schema_version,
        "topology_hash": certificate.topology_hash,
    }


def _signed_payload(certificate: TemporalCertificate) -> bytes:
    return _canonical(_payload(certificate))


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
