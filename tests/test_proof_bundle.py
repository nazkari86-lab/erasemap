import json
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from erasemap.pcug_domain import PCUGVerdict
from erasemap.proof_bundle import (
    challenge_commitment,
    check_bundle,
    decode_bundle,
    encode_bundle,
    issue_bundle,
)
from tests.pcug_factories import forked_pcug_case


def _complete_bundle() -> tuple[object, object]:
    graph, protocol, actions = forked_pcug_case()
    private_key = Ed25519PrivateKey.generate()
    bundle = issue_bundle(
        private_key,
        key_id="lab-key",
        nonce="nonce-1",
        graph=graph,
        protocol=protocol,
        actions=(actions["purge-derived"], actions["unlearn-model"]),
        challenge_opening=("probe-03", "probe-08"),
        producer_revision="8c48a3a",
    )
    return bundle, private_key.public_key()


def test_bundle_encoding_is_canonical_and_round_trips() -> None:
    bundle, _ = _complete_bundle()
    encoded = encode_bundle(bundle)
    assert encoded == encode_bundle(decode_bundle(encoded))
    assert " " not in encoded


def test_checker_independently_accepts_complete_bundle() -> None:
    bundle, public_key = _complete_bundle()
    result = check_bundle(bundle, {"lab-key": public_key})
    assert result.valid
    assert result.replayed_report is not None
    assert result.replayed_report.verdict is PCUGVerdict.COMPLETE


def test_checker_rejects_validly_signed_forged_complete_verdict() -> None:
    graph, protocol, _ = forked_pcug_case()
    private_key = Ed25519PrivateKey.generate()
    bundle = issue_bundle(
        private_key,
        key_id="lab-key",
        nonce="nonce-2",
        graph=graph,
        protocol=protocol,
        actions=(),
        challenge_opening=("probe-03",),
        producer_revision="8c48a3a",
        declared_verdict=PCUGVerdict.COMPLETE,
    )
    result = check_bundle(bundle, {"lab-key": private_key.public_key()})
    assert not result.valid
    assert result.reason == "declared verdict differs from replayed verdict"


def test_checker_rejects_challenge_commitment_mismatch() -> None:
    bundle, public_key = _complete_bundle()
    private_key = Ed25519PrivateKey.generate()
    mismatched = issue_bundle(
        private_key,
        key_id="other-key",
        nonce="nonce-3",
        graph=bundle.pre_graph,
        protocol=bundle.protocol,
        actions=bundle.selected_actions,
        challenge_opening=bundle.challenge_opening,
        challenge_commitment_override=challenge_commitment(("different",)),
        producer_revision=bundle.producer_revision,
    )
    result = check_bundle(mismatched, {"other-key": private_key.public_key()})
    assert not result.valid
    assert result.reason == "challenge commitment mismatch"
    assert public_key is not None


def test_checker_rejects_signature_tamper() -> None:
    bundle, public_key = _complete_bundle()
    tampered = replace(bundle, signature=b"\x00" * 64)
    assert check_bundle(tampered, {"lab-key": public_key}).reason == "invalid signature"


def test_decoder_rejects_unknown_field() -> None:
    bundle, _ = _complete_bundle()
    payload = json.loads(encode_bundle(bundle))
    payload["surprise"] = True
    with pytest.raises(ValueError, match="unknown field"):
        decode_bundle(json.dumps(payload))


def test_public_encoding_contains_no_raw_subject_biometrics() -> None:
    bundle, _ = _complete_bundle()
    encoded = encode_bundle(bundle)
    assert "embedding_vector" not in encoded
    assert "raw_image" not in encoded
