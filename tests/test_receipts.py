from dataclasses import replace

from erasemap.receipts import (
    ReceiptLedger,
    generate_keypair,
    issue_receipt,
    receipt_hash,
    verify_receipt,
)


def test_receipt_binds_request_and_graph_root() -> None:
    private_key, public_key = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "graph-root-1", "INCOMPLETE", 100)
    assert verify_receipt(public_key, receipt, ReceiptLedger()).valid
    altered = receipt.with_graph_root("graph-root-2")
    assert not verify_receipt(public_key, altered, ReceiptLedger()).valid


def test_receipt_nonce_cannot_be_replayed() -> None:
    private_key, public_key = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "root", "COMPLETE", 100)
    ledger = ReceiptLedger()
    assert verify_receipt(public_key, receipt, ledger).valid
    ledger.record(receipt.nonce)
    assert verify_receipt(public_key, receipt, ledger).reason == "replayed nonce"


def test_one_bit_signature_mutation_is_rejected() -> None:
    private_key, public_key = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "root", "UNVERIFIED", 100)
    changed = bytes([receipt.signature[0] ^ 1]) + receipt.signature[1:]

    result = verify_receipt(
        public_key, replace(receipt, signature=changed), ReceiptLedger()
    )

    assert not result.valid
    assert result.reason == "invalid signature"


def test_chain_link_mutation_is_rejected() -> None:
    private_key, public_key = generate_keypair()
    first = issue_receipt(private_key, "request-1", "root-1", "COMPLETE", 100)
    second = issue_receipt(
        private_key,
        "request-2",
        "root-2",
        "COMPLETE",
        110,
        previous_receipt=first,
    )

    assert verify_receipt(
        public_key,
        second,
        ReceiptLedger(),
        expected_previous_hash=receipt_hash(first),
    ).valid
    altered = replace(second, previous_receipt_hash="sha256:" + "0" * 64)
    assert verify_receipt(
        public_key,
        altered,
        ReceiptLedger(),
        expected_previous_hash=receipt_hash(first),
    ).reason == "invalid chain link"


def test_timestamp_bounds_are_checked() -> None:
    private_key, public_key = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "root", "COMPLETE", 100)

    assert verify_receipt(
        public_key, receipt, ReceiptLedger(), now_epoch=50
    ).reason == "receipt timestamp is in the future"
    assert verify_receipt(
        public_key, receipt, ReceiptLedger(), now_epoch=1_000, max_age_seconds=100
    ).reason == "receipt is too old"


def test_receipt_payload_contains_only_fixed_privacy_minimized_fields() -> None:
    private_key, _ = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "root", "COMPLETE", 100)

    assert set(receipt.payload()) == {
        "audit_status",
        "graph_root",
        "issued_epoch",
        "nonce",
        "previous_receipt_hash",
        "request_id",
        "schema_version",
    }
