from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np

from erasemap.storage_lab import RegisteredStoreLab


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--embeddings", default="outputs/advanced-face-unlearning-v1/embeddings.joblib"
    )
    parser.add_argument("--output", default="outputs/registered-storage-lab-v1")
    args = parser.parse_args()
    root = Path(args.output)
    if root.exists():
        raise RuntimeError(f"refusing to overwrite existing storage lab: {root}")
    embeddings = np.asarray(joblib.load(args.embeddings), dtype=np.float32)
    subject_id = "olivetti-subject-0"
    lab = RegisteredStoreLab(root)
    lab.enroll(subject_id, embeddings[0])
    lab.delete_source_only(subject_id)
    before = lab.audit(subject_id, now_epoch=100)
    before_presence = lab.registered_presence(subject_id)
    lab.remediate(subject_id)
    after = lab.audit(subject_id, now_epoch=100)
    after_presence = lab.registered_presence(subject_id)
    backup_files = list(lab.backup_directory.glob("*.aesgcm"))
    payload = {
        "after_remediation": {
            "presence": after_presence,
            "residual_store_ids": sorted(after.residual_store_ids),
            "status": after.result.status.value,
        },
        "before_remediation": {
            "presence": before_presence,
            "residual_store_ids": sorted(before.residual_store_ids),
            "shortest_path": list(before.result.shortest_path.node_ids)
            if before.result.shortest_path
            else None,
            "status": before.result.status.value,
        },
        "crypto_erasure": {
            "ciphertext_files_remaining": len(backup_files),
            "decryption_key_present": lab.backup_key_path(subject_id).exists(),
        },
        "stores": ["SQLite", "NumPy vector index", "JSON cache", "AES-GCM backup", "model"],
    }
    result_path = root / "result.json"
    result_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    print(result_path.read_text(), end="")
    return 0 if after.result.status.value == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
