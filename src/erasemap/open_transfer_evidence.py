from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "client_secret",
        "cookie",
        "password",
        "refresh_token",
        "secret",
        "set-cookie",
        "token",
    }
)
ALLOWED_METHODS = frozenset({"DELETE", "GET", "PATCH", "POST", "PUT"})
REDACTED = "[REDACTED]"


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            redacted[key] = REDACTED if key.casefold() in SENSITIVE_KEYS else _redact(item)
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _redact_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("evidence URL must use HTTP or HTTPS")
    query = urlencode(
        [
            (key, REDACTED if key.casefold() in SENSITIVE_KEYS else value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def canonical_evidence(
    *,
    method: str,
    url: str,
    request_headers: Mapping[str, object],
    request_body: object,
    status: int,
    response_body: object,
) -> dict[str, object]:
    normalized_method = method.upper()
    if normalized_method not in ALLOWED_METHODS:
        raise ValueError("unsupported evidence HTTP method")
    if status < 100 or status > 599:
        raise ValueError("evidence HTTP status must be between 100 and 599")
    return {
        "method": normalized_method,
        "url": _redact_url(url),
        "request_headers": _redact(request_headers),
        "request_body": _redact(request_body),
        "status": status,
        "response_body": _redact(response_body),
    }


def assert_no_secrets(value: object, secret_values: Sequence[str]) -> None:
    encoded = canonical_json(value)
    for secret in secret_values:
        if secret and secret.encode() in encoded:
            raise ValueError("raw secret value remains in evidence")


class EvidenceLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: list[dict[str, object]] = []
        self._digests: set[str] = set()
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            lines = self.path.read_text().splitlines()
            entries = [json.loads(line) for line in lines if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("invalid evidence JSONL") from exc
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                raise ValueError("invalid evidence JSONL entry")
            entry = cast(dict[str, Any], raw_entry)
            record_raw = entry.get("record")
            digest_raw = entry.get("evidence_sha256")
            if not isinstance(record_raw, dict) or not isinstance(digest_raw, str):
                raise ValueError("invalid evidence JSONL entry")
            record = cast(dict[str, object], record_raw)
            expected = sha256_bytes(canonical_json(record))
            if digest_raw != expected:
                raise ValueError("evidence hash mismatch")
            if digest_raw in self._digests:
                raise ValueError("duplicate evidence in existing ledger")
            self._digests.add(digest_raw)
            self._records.append(record)

    def append(self, record: Mapping[str, object]) -> str:
        canonical_record = dict(record)
        digest = sha256_bytes(canonical_json(canonical_record))
        if digest in self._digests:
            raise ValueError("duplicate evidence")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"evidence_sha256": digest, "record": canonical_record}
        with self.path.open("ab") as stream:
            stream.write(canonical_json(entry) + b"\n")
        self._digests.add(digest)
        self._records.append(canonical_record)
        return digest

    def records(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(item) for item in self._records)
