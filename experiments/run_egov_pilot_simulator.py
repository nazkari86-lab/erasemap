from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from erasemap.receipts import (
    ReceiptLedger,
    generate_keypair,
    issue_receipt,
    receipt_hash,
    verify_receipt,
)
from erasemap.storage_lab import RegisteredStoreLab


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def graph_root(subject_id: str, presence: dict[str, bool]) -> str:
    payload = canonical_json({"presence": presence, "subject_id": subject_id})
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embeddings", default="outputs/lfw-holdout-v1/embeddings.joblib")
    parser.add_argument("--model-audit", default="outputs/task-agnostic-v2-evaluation/result.json")
    parser.add_argument("--output", default="outputs/egov-pilot-simulator-v1")
    parser.add_argument("--subjects", type=int, default=25)
    parser.add_argument("--deletions", type=int, default=5)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise RuntimeError(f"refusing to overwrite pilot simulator: {output}")
    if args.subjects <= args.deletions or args.deletions <= 0:
        raise ValueError("subjects must exceed positive deletions")
    embeddings = np.asarray(joblib.load(args.embeddings), dtype=np.float32)
    if len(embeddings) < args.subjects:
        raise ValueError("not enough embeddings")
    model_audit = Path(args.model_audit)
    model_result = json.loads(model_audit.read_text())
    if not model_result["success"]:
        raise RuntimeError("model audit did not pass its frozen criteria")
    lab = RegisteredStoreLab(output / "registered-stores")
    subject_ids = [f"citizen-{index:04d}" for index in range(args.subjects)]
    for subject_id, embedding in zip(subject_ids, embeddings, strict=False):
        lab.enroll(subject_id, embedding)
    private_key, public_key = generate_keypair()
    ledger = ReceiptLedger()
    previous_receipt = None
    deletion_records: list[dict[str, Any]] = []
    for sequence, subject_id in enumerate(subject_ids[: args.deletions], start=1):
        lab.delete_source_only(subject_id)
        before = lab.audit(subject_id, now_epoch=100 + sequence)
        lab.remediate(subject_id)
        after = lab.audit(subject_id, now_epoch=100 + sequence)
        presence = lab.registered_presence(subject_id)
        receipt = issue_receipt(
            private_key,
            request_id=f"delete-{sequence:04d}",
            graph_root=graph_root(subject_id, presence),
            audit_status=after.result.status,
            issued_epoch=100 + sequence,
            previous_receipt=previous_receipt,
        )
        expected_previous = receipt_hash(previous_receipt) if previous_receipt else None
        verification = verify_receipt(
            public_key,
            receipt,
            ledger,
            now_epoch=100 + sequence,
            expected_previous_hash=expected_previous,
        )
        if verification.valid:
            ledger.record(receipt.nonce)
        deletion_records.append(
            {
                "after_status": after.result.status.value,
                "before_residual_stores": sorted(before.residual_store_ids),
                "before_status": before.result.status.value,
                "receipt_hash": receipt_hash(receipt),
                "receipt_valid": verification.valid,
                "remaining_presence": presence,
                "request_id": receipt.request_id,
            }
        )
        previous_receipt = receipt
    if previous_receipt is None:
        raise RuntimeError("no receipt was issued")
    tampered = replace(previous_receipt, graph_root="sha256:tampered")
    tampered_check = verify_receipt(
        public_key,
        tampered,
        ReceiptLedger(),
        now_epoch=200,
        expected_previous_hash=previous_receipt.previous_receipt_hash,
    )
    retained_presence = {
        subject_id: lab.registered_presence(subject_id)
        for subject_id in subject_ids[args.deletions :]
    }
    deleted_clean = all(
        not any(lab.registered_presence(subject_id).values())
        for subject_id in subject_ids[: args.deletions]
    )
    retained_intact = all(all(values.values()) for values in retained_presence.values())
    success = (
        deleted_clean
        and retained_intact
        and all(record["before_status"] == "INCOMPLETE" for record in deletion_records)
        and all(record["after_status"] == "COMPLETE" for record in deletion_records)
        and all(record["receipt_valid"] for record in deletion_records)
        and not tampered_check.valid
    )
    payload = {
        "claim_boundary": "Production-like local simulator, not an authorized eGov deployment.",
        "deleted_clean": deleted_clean,
        "deletion_records": deletion_records,
        "model_audit_reference": {
            "path": str(model_audit),
            "sha256": sha256_file(model_audit),
        },
        "retained_intact": retained_intact,
        "stores": ["SQLite", "vector index", "cache", "AES-GCM backup", "model lineage"],
        "subjects": args.subjects,
        "success": success,
        "tampered_receipt_rejected": not tampered_check.valid,
    }
    (output / "result.json").write_text(canonical_json(payload) + "\n")
    print(canonical_json({"deletions": args.deletions, "success": success}))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
