from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    AuditStatus,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)
from erasemap.evidence_envelopes import (
    EvidenceEnvelopeLedger,
    audit_signed_subject,
    evidence_envelope_from_payload,
    issue_evidence_envelope,
    verify_evidence_envelope,
)


def _evidence() -> Evidence:
    return Evidence(
        "evidence-1",
        "artifact-1",
        EvidenceKind.SIGNED_STATEMENT,
        issued_epoch=100,
        metadata=(("control_id", "deny-1"), ("enforced", "true")),
    )


def test_verified_envelope_sets_signature_fact_only_after_crypto_verification() -> None:
    private_key = Ed25519PrivateKey.generate()
    envelope = issue_evidence_envelope(private_key, "issuer-1", _evidence(), nonce="n-1")

    result = verify_evidence_envelope(
        {"issuer-1": private_key.public_key()},
        envelope,
        EvidenceEnvelopeLedger(),
        now_epoch=100,
    )

    assert result.valid
    assert result.evidence is not None
    assert result.evidence.valid_signature
    round_trip = evidence_envelope_from_payload(envelope.serialized())
    assert round_trip == envelope


def test_payload_mutation_and_wrong_key_are_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    wrong_key = Ed25519PrivateKey.generate()
    envelope = issue_evidence_envelope(private_key, "issuer-1", _evidence(), nonce="n-1")
    changed = replace(envelope, evidence=replace(envelope.evidence, artifact_id="other"))

    assert not verify_evidence_envelope(
        {"issuer-1": private_key.public_key()},
        changed,
        EvidenceEnvelopeLedger(),
        now_epoch=100,
    ).valid
    assert not verify_evidence_envelope(
        {"issuer-1": wrong_key.public_key()},
        envelope,
        EvidenceEnvelopeLedger(),
        now_epoch=100,
    ).valid


def test_verified_nonce_is_consumed_and_cannot_be_replayed() -> None:
    private_key = Ed25519PrivateKey.generate()
    envelope = issue_evidence_envelope(private_key, "issuer-1", _evidence(), nonce="n-1")
    ledger = EvidenceEnvelopeLedger()
    trust_store = {"issuer-1": private_key.public_key()}

    assert verify_evidence_envelope(
        trust_store, envelope, ledger, now_epoch=100
    ).valid
    assert verify_evidence_envelope(
        trust_store, envelope, ledger, now_epoch=100
    ).reason == "replayed nonce"


def test_untrusted_or_stale_envelope_fails_closed() -> None:
    private_key = Ed25519PrivateKey.generate()
    envelope = issue_evidence_envelope(private_key, "issuer-1", _evidence())

    assert verify_evidence_envelope(
        {}, envelope, EvidenceEnvelopeLedger(), now_epoch=100
    ).reason == "untrusted key id"
    assert verify_evidence_envelope(
        {"issuer-1": private_key.public_key()},
        envelope,
        EvidenceEnvelopeLedger(),
        now_epoch=201,
        max_age_seconds=100,
    ).reason == "evidence is too old"


def test_signed_audit_fails_closed_when_envelope_is_tampered() -> None:
    private_key = Ed25519PrivateKey.generate()
    artifact = Artifact(
        "artifact-1",
        "subject-1",
        ArtifactType.CACHE_ENTRY,
        ArtifactState.BLOCKED,
    )
    graph = ErasureGraph({artifact.id: artifact}, ())
    envelope = issue_evidence_envelope(private_key, "issuer-1", _evidence())
    trust_store = {"issuer-1": private_key.public_key()}

    valid = audit_signed_subject(
        graph,
        {artifact.id: envelope},
        trust_store,
        artifact.subject_id,
        100,
    )
    tampered = audit_signed_subject(
        graph,
        {artifact.id: replace(envelope, nonce="changed")},
        trust_store,
        artifact.subject_id,
        100,
    )

    assert valid.status is AuditStatus.COMPLETE
    assert tampered.status is AuditStatus.UNVERIFIED
