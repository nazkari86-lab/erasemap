from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def generate_keypair() -> tuple[bytes, bytes]:
    private = Ed25519PrivateKey.generate()
    return (
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ),
    )


def sign_manifest(manifest: dict[str, Any], private_pem: bytes) -> dict[str, str]:
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("an Ed25519 private key is required")
    commitment = sha256_bytes(canonical(manifest))
    statement = canonical(
        {
            "manifest_sha256": commitment,
            "statement": (
                "I attest that I authored or independently operated this hidden transfer "
                "evaluation and that the manifest accurately binds its raw evidence and result."
            ),
        }
    )
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return {
        "schema_version": "erasemap-external-transfer-attestation-v1",
        "manifest_sha256": commitment,
        "public_key": base64.b64encode(public).decode(),
        "signature": base64.b64encode(private.sign(statement)).decode(),
        "statement": json.loads(statement),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "sign"))
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--public-key", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--attestation", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        if args.public_key is None:
            raise ValueError("--public-key is required for key generation")
        private, public = generate_keypair()
        args.private_key.write_bytes(private)
        args.public_key.write_text(base64.b64encode(public).decode() + "\n")
        return 0
    if args.manifest is None or args.attestation is None:
        raise ValueError("--manifest and --attestation are required for signing")
    manifest = json.loads(args.manifest.read_text())
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    signed = sign_manifest(manifest, args.private_key.read_bytes())
    args.attestation.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
