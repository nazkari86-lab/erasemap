from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from external_challenge.seal import canonical, sha256


def generate_keypair() -> tuple[bytes, bytes]:
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return private_pem, public_raw


def sign_score(
    score: dict[str, Any], private_pem: bytes, evaluator: str, affiliation: str
) -> dict[str, object]:
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("an Ed25519 private key is required")
    score_bytes = canonical(score)
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    statement = {
        "affiliation": affiliation,
        "evaluator": evaluator,
        "score_commitment": sha256(score_bytes),
        "statement": (
            "I controlled case authorship, hidden labels, reveal timing, and final scoring; "
            "the project author had no label access before predictions were frozen."
        ),
    }
    signature = private.sign(canonical(statement))
    return {
        "public_key": base64.b64encode(public_raw).decode(),
        "signature": base64.b64encode(signature).decode(),
        "statement": statement,
        "schema_version": "erasemap-external-attestation-v1",
    }


def sign_submission(
    score: dict[str, Any], private_pem: bytes, manifest: dict[str, Any]
) -> dict[str, object]:
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("an Ed25519 private key is required")
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    statement = {
        "manifest": manifest,
        "score_commitment": sha256(canonical(score)),
        "statement": (
            "I controlled external case authorship, hidden labels, reveal timing, and final "
            "scoring; the EraSeMap author had no label access before predictions were frozen."
        ),
    }
    return {
        "public_key": base64.b64encode(public_raw).decode(),
        "signature": base64.b64encode(private.sign(canonical(statement))).decode(),
        "statement": statement,
        "schema_version": "erasemap-external-submission-attestation-v2",
    }


def verify_submission_attestation(
    score: dict[str, Any], manifest: dict[str, Any], attestation: dict[str, Any]
) -> bool:
    if attestation.get("schema_version") != "erasemap-external-submission-attestation-v2":
        return False
    statement = attestation.get("statement")
    if not isinstance(statement, dict):
        return False
    if statement.get("manifest") != manifest or statement.get("score_commitment") != sha256(
        canonical(score)
    ):
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(attestation["public_key"]))
        public.verify(base64.b64decode(attestation["signature"]), canonical(statement))
    except (InvalidSignature, TypeError, ValueError):
        return False
    return True


def verify_attestation(score: dict[str, Any], attestation: dict[str, Any]) -> bool:
    if attestation.get("schema_version") != "erasemap-external-attestation-v1":
        return False
    statement = attestation.get("statement")
    if not isinstance(statement, dict) or statement.get("score_commitment") != sha256(
        canonical(score)
    ):
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(attestation["public_key"]))
        public.verify(base64.b64decode(attestation["signature"]), canonical(statement))
    except (InvalidSignature, TypeError, ValueError):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign or verify an external challenge score")
    parser.add_argument("command", choices=("generate", "sign", "verify", "sign-submission"))
    parser.add_argument("--affiliation")
    parser.add_argument("--attestation")
    parser.add_argument("--evaluator")
    parser.add_argument("--private-key")
    parser.add_argument("--public-key")
    parser.add_argument("--score")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if args.command == "generate":
        if not args.private_key or not args.public_key:
            raise ValueError("--private-key and --public-key are required")
        private_pem, public_raw = generate_keypair()
        Path(args.private_key).write_bytes(private_pem)
        Path(args.public_key).write_text(base64.b64encode(public_raw).decode() + "\n")
        return 0
    if not args.score or not args.attestation:
        raise ValueError("--score and --attestation are required")
    score = json.loads(Path(args.score).read_text())
    if args.command == "sign-submission":
        if not args.private_key or not args.manifest:
            raise ValueError("--private-key and --manifest are required")
        manifest = json.loads(Path(args.manifest).read_text())
        signed = sign_submission(score, Path(args.private_key).read_bytes(), manifest)
        Path(args.attestation).write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
        return 0
    if args.command == "sign":
        if not args.private_key or not args.evaluator or not args.affiliation:
            raise ValueError("private key and evaluator identity fields are required")
        signed = sign_score(
            score,
            Path(args.private_key).read_bytes(),
            args.evaluator,
            args.affiliation,
        )
        Path(args.attestation).write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
        return 0
    attestation = json.loads(Path(args.attestation).read_text())
    if not verify_attestation(score, attestation):
        raise ValueError("attestation verification failed")
    print("attestation verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
