from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from external_ghostgraph_challenge.schema import canonical, load_object


def generate_keypair() -> tuple[bytes, bytes]:
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_pem, public_raw


def sign_manifest(manifest: dict[str, object], private_pem: bytes) -> dict[str, str]:
    private = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("attestation key must be Ed25519")
    message = canonical(manifest)
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return {
        "schema_version": "erasemap-external-ghostgraph-attestation-v2",
        "public_key": base64.b64encode(public_raw).decode(),
        "manifest_sha256": "sha256:" + hashlib.sha256(message).hexdigest(),
        "signature": base64.b64encode(private.sign(message)).decode(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--private-key", type=Path, required=True)
    generate.add_argument("--public-key", type=Path, required=True)
    sign = subparsers.add_parser("sign")
    sign.add_argument("--manifest", type=Path, required=True)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        private_pem, public_raw = generate_keypair()
        args.private_key.write_bytes(private_pem)
        args.public_key.write_text(base64.b64encode(public_raw).decode() + "\n")
        return 0
    attestation = sign_manifest(load_object(args.manifest), args.private_key.read_bytes())
    args.output.write_text(json.dumps(attestation, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
