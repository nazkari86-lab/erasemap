from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from external_ghostgraph_challenge.schema import (
    canonical,
    load_object,
    public_suite,
    public_suite_v2,
    validate_suite,
    validate_suite_v2,
)


def seal_suite(suite: dict[str, object], key: bytes) -> tuple[bytes, dict[str, object]]:
    if suite.get("schema_version") == "erasemap-external-ghostgraph-suite-v2":
        validate_suite_v2(suite)
        public = public_suite_v2(suite)
        commitment_schema = "erasemap-external-ghostgraph-commitment-v2"
    else:
        validate_suite(suite)
        public = public_suite(suite)
        commitment_schema = "erasemap-external-ghostgraph-commitment-v1"
    plaintext = canonical(suite)
    ciphertext = Fernet(key).encrypt(plaintext)
    commitment = {
        "schema_version": commitment_schema,
        "truth_sha256": "sha256:" + hashlib.sha256(plaintext).hexdigest(),
        "sealed_sha256": "sha256:" + hashlib.sha256(ciphertext).hexdigest(),
        "public_sha256": "sha256:" + hashlib.sha256(canonical(public)).hexdigest(),
        "case_count": len(suite["cases"]),  # type: ignore[arg-type]
    }
    return ciphertext, commitment


def unseal_suite(ciphertext: bytes, key: bytes, expected_truth_sha256: str) -> dict[str, object]:
    try:
        plaintext = Fernet(key).decrypt(ciphertext)
    except InvalidToken as exc:
        raise ValueError("external GhostGraph sealed truth cannot be decrypted") from exc
    observed = "sha256:" + hashlib.sha256(plaintext).hexdigest()
    if observed != expected_truth_sha256:
        raise ValueError("external GhostGraph unsealed truth commitment mismatch")
    payload = json.loads(plaintext)
    if not isinstance(payload, dict):
        raise ValueError("external GhostGraph unsealed truth must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seal", "unseal"), nargs="?", default="seal")
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--sealed", type=Path, required=True)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "unseal":
        commitment = load_object(args.commitment)
        key = args.key.read_text().strip().encode()
        payload = unseal_suite(args.sealed.read_bytes(), key, str(commitment["truth_sha256"]))
        if args.suite is None:
            raise ValueError("--suite output is required for unseal")
        args.suite.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        return 0
    if args.suite is None or args.public is None:
        raise ValueError("--suite and --public are required for seal")
    suite = load_object(args.suite)
    key = Fernet.generate_key()
    sealed, commitment = seal_suite(suite, key)
    args.sealed.write_bytes(sealed)
    public = (
        public_suite_v2(suite)
        if suite.get("schema_version") == "erasemap-external-ghostgraph-suite-v2"
        else public_suite(suite)
    )
    args.public.write_text(json.dumps(public, sort_keys=True, indent=2) + "\n")
    args.commitment.write_text(json.dumps(commitment, sort_keys=True, indent=2) + "\n")
    args.key.write_text(key.decode() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
