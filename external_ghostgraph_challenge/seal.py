from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet

from external_ghostgraph_challenge.schema import (
    canonical,
    load_object,
    public_suite,
    validate_suite,
)


def seal_suite(suite: dict[str, object], key: bytes) -> tuple[bytes, dict[str, object]]:
    validate_suite(suite)
    plaintext = canonical(suite)
    ciphertext = Fernet(key).encrypt(plaintext)
    commitment = {
        "schema_version": "erasemap-external-ghostgraph-commitment-v1",
        "truth_sha256": "sha256:" + hashlib.sha256(plaintext).hexdigest(),
        "sealed_sha256": "sha256:" + hashlib.sha256(ciphertext).hexdigest(),
        "public_sha256": "sha256:" + hashlib.sha256(canonical(public_suite(suite))).hexdigest(),
        "case_count": len(suite["cases"]),  # type: ignore[arg-type]
    }
    return ciphertext, commitment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--sealed", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--commitment", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    suite = load_object(args.suite)
    key = Fernet.generate_key()
    sealed, commitment = seal_suite(suite, key)
    args.sealed.write_bytes(sealed)
    args.public.write_text(json.dumps(public_suite(suite), sort_keys=True, indent=2) + "\n")
    args.commitment.write_text(json.dumps(commitment, sort_keys=True, indent=2) + "\n")
    args.key.write_text(base64.b64encode(key).decode() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
