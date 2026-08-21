from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, replace
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from erasemap.domain import AuditStatus

SCHEMA_VERSION = "erasemap-receipt-v1"


@dataclass(frozen=True, slots=True)
class ErasureReceipt:
    schema_version: str
    request_id: str
    graph_root: str
    audit_status: AuditStatus
    issued_epoch: int
    nonce: str
    previous_receipt_hash: str | None
    signature: bytes

    def payload(self) -> dict[str, str | int | None]:
        return {
            "audit_status": self.audit_status.value,
            "graph_root": self.graph_root,
            "issued_epoch": self.issued_epoch,
            "nonce": self.nonce,
            "previous_receipt_hash": self.previous_receipt_hash,
            "request_id": self.request_id,
            "schema_version": self.schema_version,
        }

    def with_graph_root(self, graph_root: str) -> ErasureReceipt:
        return replace(self, graph_root=graph_root)


@dataclass(frozen=True, slots=True)
class ReceiptVerification:
    valid: bool
    reason: str


class ReceiptLedger:
    def __init__(self) -> None:
        self._nonces: set[str] = set()

    def contains(self, nonce: str) -> bool:
        return nonce in self._nonces

    def record(self, nonce: str) -> None:
        if not nonce:
            raise ValueError("nonce is required")
        self._nonces.add(nonce)


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _signed_payload(receipt: ErasureReceipt) -> bytes:
    return _canonical_json(receipt.payload())


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def receipt_hash(receipt: ErasureReceipt) -> str:
    envelope = {
        "payload": receipt.payload(),
        "signature": receipt.signature.hex(),
    }
    return "sha256:" + hashlib.sha256(_canonical_json(envelope)).hexdigest()


def issue_receipt(
    private_key: Ed25519PrivateKey,
    request_id: str,
    graph_root: str,
    audit_status: str | AuditStatus,
    issued_epoch: int,
    *,
    previous_receipt: ErasureReceipt | None = None,
    nonce: str | None = None,
) -> ErasureReceipt:
    if not request_id or not graph_root:
        raise ValueError("request id and graph root are required")
    if issued_epoch < 0:
        raise ValueError("issued epoch cannot be negative")
    status = AuditStatus(audit_status)
    receipt = ErasureReceipt(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        graph_root=graph_root,
        audit_status=status,
        issued_epoch=issued_epoch,
        nonce=nonce or secrets.token_hex(16),
        previous_receipt_hash=(
            receipt_hash(previous_receipt) if previous_receipt is not None else None
        ),
        signature=b"",
    )
    return replace(receipt, signature=private_key.sign(_signed_payload(receipt)))


def verify_receipt(
    public_key: Ed25519PublicKey,
    receipt: ErasureReceipt,
    ledger: ReceiptLedger,
    *,
    now_epoch: int | None = None,
    max_age_seconds: int | None = None,
    expected_previous_hash: str | None = None,
) -> ReceiptVerification:
    if receipt.schema_version != SCHEMA_VERSION:
        return ReceiptVerification(False, "unsupported schema version")
    if receipt.previous_receipt_hash != expected_previous_hash:
        return ReceiptVerification(False, "invalid chain link")
    if ledger.contains(receipt.nonce):
        return ReceiptVerification(False, "replayed nonce")
    effective_now = receipt.issued_epoch if now_epoch is None else now_epoch
    if receipt.issued_epoch > effective_now:
        return ReceiptVerification(False, "receipt timestamp is in the future")
    if max_age_seconds is not None:
        if max_age_seconds < 0:
            raise ValueError("max age cannot be negative")
        if effective_now - receipt.issued_epoch > max_age_seconds:
            return ReceiptVerification(False, "receipt is too old")
    try:
        public_key.verify(receipt.signature, _signed_payload(receipt))
    except InvalidSignature:
        return ReceiptVerification(False, "invalid signature")
    return ReceiptVerification(True, "valid signature and receipt envelope")
