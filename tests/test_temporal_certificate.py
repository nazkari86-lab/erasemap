from __future__ import annotations

from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from erasemap.temporal_certificate import (
    CertificateStatus,
    TemporalVerdict,
    TemporalVerificationContext,
    check_temporal_certificate,
    decode_temporal_certificate,
    encode_temporal_certificate,
    issue_temporal_certificate,
)


def context(**changes: object) -> TemporalVerificationContext:
    values = {
        "topology_hash": "sha256:topology",
        "envelope_hash": "sha256:envelope",
        "model_set_hash": "sha256:models",
        "observations_hash": "sha256:observations",
        "policy_certificate_hash": "sha256:policy",
        "proof_bundle_hash": "sha256:proof",
        "action_signature_hash": "sha256:action",
        "replayed_verdict": TemporalVerdict.COMPLETE_WITHIN_ENVELOPE,
        "topology_coverage_complete": True,
        "observations_sound": True,
        "controls_replayed": True,
        "mandatory_channels_passed": True,
    }
    values.update(changes)
    return TemporalVerificationContext(**values)  # type: ignore[arg-type]


def certificate() -> tuple[object, object, TemporalVerificationContext]:
    private = Ed25519PrivateKey.generate()
    verification_context = context()
    item = issue_temporal_certificate(
        private,
        key_id="lab-key",
        request_id="delete-1",
        issued_epoch=100,
        not_after_epoch=200,
        context=verification_context,
        invalidation_conditions=("model-set-change", "topology-change"),
        producer_revision="6aaaf73",
    )
    return item, private.public_key(), verification_context


def test_independent_context_accepts_bounded_complete_certificate() -> None:
    item, public, verification_context = certificate()

    result = check_temporal_certificate(
        item,
        {"lab-key": public},
        verification_context,
        now_epoch=150,
    )

    assert result.status is CertificateStatus.VALID
    encoded = encode_temporal_certificate(item)
    assert "COMPLETE_WITHIN_ENVELOPE" in encoded
    assert decode_temporal_certificate(encoded) == item


@pytest.mark.parametrize(
    ("change", "reason"),
    (
        ({"topology_hash": "sha256:new"}, "topology commitment changed"),
        ({"model_set_hash": "sha256:new"}, "model set commitment changed"),
    ),
)
def test_context_drift_expires_certificate(change: dict[str, object], reason: str) -> None:
    item, public, verification_context = certificate()
    changed = replace(verification_context, **change)

    result = check_temporal_certificate(item, {"lab-key": public}, changed, now_epoch=150)

    assert result.status is CertificateStatus.EXPIRED
    assert result.reason == reason


def test_time_expiry_is_distinct_from_invalid_signature() -> None:
    item, public, verification_context = certificate()
    assert check_temporal_certificate(
        item, {"lab-key": public}, verification_context, now_epoch=201
    ).status is CertificateStatus.EXPIRED
    assert check_temporal_certificate(
        replace(item, signature=b"0" * 64),
        {"lab-key": public},
        verification_context,
        now_epoch=150,
    ).status is CertificateStatus.INVALID


def test_signed_complete_claim_fails_when_replay_obligation_is_missing() -> None:
    private = Ed25519PrivateKey.generate()
    incomplete_context = context(topology_coverage_complete=False)
    item = issue_temporal_certificate(
        private,
        key_id="lab-key",
        request_id="delete-2",
        issued_epoch=100,
        not_after_epoch=200,
        context=incomplete_context,
        invalidation_conditions=("topology-change",),
        producer_revision="6aaaf73",
    )

    result = check_temporal_certificate(
        item,
        {"lab-key": private.public_key()},
        incomplete_context,
        now_epoch=150,
    )

    assert result.status is CertificateStatus.INVALID
    assert result.reason == "complete verdict has an undischarged obligation"
