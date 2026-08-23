from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from erasemap.audit import audit_subject
from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    AuditResult,
    Edge,
    EdgeType,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)


@dataclass(frozen=True, slots=True)
class StorageAudit:
    result: AuditResult
    residual_store_ids: frozenset[str]


class RegisteredStoreLab:
    def __init__(self, root: str | Path, *, commitment_key: bytes | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.commitment_key_path = self.root / ".commitment-key"
        if commitment_key is not None:
            if len(commitment_key) < 32:
                raise ValueError("commitment key must contain at least 256 bits")
            self._commitment_key = commitment_key
        elif self.commitment_key_path.exists():
            self._commitment_key = self.commitment_key_path.read_bytes()
        else:
            self._commitment_key = secrets.token_bytes(32)
            self.commitment_key_path.write_bytes(self._commitment_key)
            self.commitment_key_path.chmod(0o600)
        if len(self._commitment_key) < 32:
            raise ValueError("stored commitment key must contain at least 256 bits")
        self.database_path = self.root / "identity.sqlite3"
        self.index_path = self.root / "vector-index.npz"
        self.cache_path = self.root / "cache.json"
        self.backup_directory = self.root / "backups"
        self.backup_directory.mkdir(exist_ok=True)
        self.model_path = self.root / "model-manifest.json"
        self.tombstone_path = self.root / "deletion-tombstones.json"
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS identities "
                "(commitment TEXT PRIMARY KEY, embedding BLOB NOT NULL)"
            )

    def _commitment(self, subject_id: str) -> str:
        if not subject_id:
            raise ValueError("subject id is required")
        message = b"erasemap-subject-commitment-v1\x00" + subject_id.encode()
        return "hmac-sha256:" + hmac.new(
            self._commitment_key, message, hashlib.sha256
        ).hexdigest()

    def _key_name(self, subject_id: str) -> str:
        return self._commitment(subject_id).removeprefix("hmac-sha256:") + ".key"

    def backup_key_path(self, subject_id: str) -> Path:
        return self.root / self._key_name(subject_id)

    def _backup_cipher_path(self, subject_id: str) -> Path:
        return self.backup_directory / (
            self._commitment(subject_id).removeprefix("hmac-sha256:") + ".aesgcm"
        )

    @staticmethod
    def _canonical_json(payload: Any) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _read_json(self, path: Path, default: Any) -> Any:
        return json.loads(path.read_text()) if path.exists() else default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(self._canonical_json(payload) + "\n")

    def _read_index(self) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        if not self.index_path.exists():
            return np.asarray([], dtype="U71"), np.empty((0, 0), dtype=np.float32)
        with np.load(self.index_path, allow_pickle=False) as archive:
            return np.asarray(archive["ids"]), np.asarray(archive["embeddings"])

    def enroll(self, subject_id: str, embedding: np.ndarray[Any, Any]) -> None:
        commitment = self._commitment(subject_id)
        vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if not len(vector):
            raise ValueError("embedding cannot be empty")
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO identities(commitment, embedding) VALUES (?, ?)",
                (commitment, vector.tobytes()),
            )

        ids, embeddings = self._read_index()
        keep = ids != commitment
        retained = embeddings[keep] if len(ids) else np.empty((0, len(vector)), np.float32)
        np.savez_compressed(
            self.index_path,
            ids=np.asarray([*ids[keep].tolist(), commitment]),
            embeddings=np.vstack((retained, vector)),
        )
        cache = self._read_json(self.cache_path, {})
        cache[commitment] = vector.tolist()
        self._write_json(self.cache_path, cache)

        key = AESGCM.generate_key(bit_length=256)
        nonce = hashlib.sha256((commitment + ":backup").encode()).digest()[:12]
        plaintext = self._canonical_json(
            {"commitment": commitment, "embedding": vector.tolist()}
        ).encode()
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, commitment.encode())
        self._backup_cipher_path(subject_id).write_bytes(nonce + ciphertext)
        backup_key_path = self.backup_key_path(subject_id)
        backup_key_path.write_bytes(key)
        backup_key_path.chmod(0o600)

        model = self._read_json(self.model_path, {"training_commitments": []})
        commitments = set(model["training_commitments"])
        commitments.add(commitment)
        self._write_json(
            self.model_path, {"training_commitments": sorted(commitments)}
        )

    def delete_source_only(self, subject_id: str) -> None:
        commitment = self._commitment(subject_id)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "DELETE FROM identities WHERE commitment = ?", (commitment,)
            )

    def delete_online_keep_recoverable_backup(self, subject_id: str) -> None:
        """Delete registered online derivatives while retaining the offline backup carrier."""
        commitment = self._commitment(subject_id)
        self.delete_source_only(subject_id)
        ids, embeddings = self._read_index()
        keep = ids != commitment
        retained = embeddings[keep]
        width = embeddings.shape[1] if embeddings.ndim == 2 else 0
        np.savez_compressed(
            self.index_path,
            ids=ids[keep],
            embeddings=(
                retained
                if len(retained)
                else np.empty((0, width), dtype=np.float32)
            ),
        )
        cache = self._read_json(self.cache_path, {})
        cache.pop(commitment, None)
        self._write_json(self.cache_path, cache)
        model = self._read_json(self.model_path, {"training_commitments": []})
        model["training_commitments"] = sorted(
            value for value in model["training_commitments"] if value != commitment
        )
        self._write_json(self.model_path, model)

    def install_persistent_tombstone(self, subject_id: str) -> None:
        commitment = self._commitment(subject_id)
        tombstones = set(self._read_json(self.tombstone_path, []))
        tombstones.add(commitment)
        self._write_json(self.tombstone_path, sorted(tombstones))

    def restore_backup_to_source(self, subject_id: str) -> bool:
        """Restore one subject unless a durable subject tombstone blocks the transition."""
        commitment = self._commitment(subject_id)
        tombstones = set(self._read_json(self.tombstone_path, []))
        if commitment in tombstones:
            return False
        key_path = self.backup_key_path(subject_id)
        backup_path = self._backup_cipher_path(subject_id)
        if not key_path.exists() or not backup_path.exists():
            return False
        encrypted = backup_path.read_bytes()
        plaintext = AESGCM(key_path.read_bytes()).decrypt(
            encrypted[:12], encrypted[12:], commitment.encode()
        )
        payload = json.loads(plaintext)
        vector = np.asarray(payload["embedding"], dtype=np.float32)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO identities(commitment, embedding) VALUES (?, ?)",
                (commitment, vector.tobytes()),
            )
        return True

    def rebuild_online_derivatives(self, subject_id: str) -> bool:
        """Run the registered source-to-cache/index/model propagation workflow."""
        commitment = self._commitment(subject_id)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            row = connection.execute(
                "SELECT embedding FROM identities WHERE commitment = ?", (commitment,)
            ).fetchone()
        if row is None:
            return False
        vector = np.frombuffer(row[0], dtype=np.float32).copy()
        ids, embeddings = self._read_index()
        keep = ids != commitment
        retained = embeddings[keep] if len(ids) else np.empty((0, len(vector)), np.float32)
        np.savez_compressed(
            self.index_path,
            ids=np.asarray([*ids[keep].tolist(), commitment]),
            embeddings=np.vstack((retained, vector)),
        )
        cache = self._read_json(self.cache_path, {})
        cache[commitment] = vector.tolist()
        self._write_json(self.cache_path, cache)
        model = self._read_json(self.model_path, {"training_commitments": []})
        commitments = set(model["training_commitments"])
        commitments.add(commitment)
        self._write_json(
            self.model_path, {"training_commitments": sorted(commitments)}
        )
        return True

    def online_presence(self, subject_id: str) -> dict[str, bool]:
        presence = self.registered_presence(subject_id)
        return {key: value for key, value in presence.items() if key != "backup"}

    def remediate(self, subject_id: str) -> None:
        commitment = self._commitment(subject_id)
        ids, embeddings = self._read_index()
        keep = ids != commitment
        retained = embeddings[keep]
        if len(retained):
            np.savez_compressed(self.index_path, ids=ids[keep], embeddings=retained)
        else:
            np.savez_compressed(
                self.index_path,
                ids=np.asarray([], dtype="U71"),
                embeddings=np.empty((0, embeddings.shape[1]), dtype=np.float32),
            )
        cache = self._read_json(self.cache_path, {})
        cache.pop(commitment, None)
        self._write_json(self.cache_path, cache)
        self.backup_key_path(subject_id).unlink(missing_ok=True)
        model = self._read_json(self.model_path, {"training_commitments": []})
        model["training_commitments"] = sorted(
            value for value in model["training_commitments"] if value != commitment
        )
        self._write_json(self.model_path, model)

    def _backup_contains(self, subject_id: str) -> bool:
        commitment = self._commitment(subject_id)
        key_path = self.backup_key_path(subject_id)
        backup_path = self._backup_cipher_path(subject_id)
        if not key_path.exists() or not backup_path.exists():
            return False
        encrypted = backup_path.read_bytes()
        plaintext = AESGCM(key_path.read_bytes()).decrypt(
            encrypted[:12], encrypted[12:], commitment.encode()
        )
        return bool(json.loads(plaintext)["commitment"] == commitment)

    def registered_presence(self, subject_id: str) -> dict[str, bool]:
        commitment = self._commitment(subject_id)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            source = connection.execute(
                "SELECT 1 FROM identities WHERE commitment = ?", (commitment,)
            ).fetchone()
        ids, _ = self._read_index()
        cache = self._read_json(self.cache_path, {})
        model = self._read_json(self.model_path, {"training_commitments": []})
        return {
            "backup": self._backup_contains(subject_id),
            "cache": commitment in cache,
            "model": commitment in model["training_commitments"],
            "sqlite-source": source is not None,
            "vector-index": bool(np.any(ids == commitment)),
        }

    def audit(self, subject_id: str, *, now_epoch: int) -> StorageAudit:
        commitment = self._commitment(subject_id)
        presence = self.registered_presence(subject_id)
        types = {
            "sqlite-source": ArtifactType.SOURCE_RECORD,
            "vector-index": ArtifactType.SEARCH_INDEX_ENTRY,
            "cache": ArtifactType.CACHE_ENTRY,
            "backup": ArtifactType.BACKUP_COPY,
            "model": ArtifactType.MODEL_INFLUENCE,
        }
        nodes = {
            store_id: Artifact(
                store_id,
                commitment,
                artifact_type,
                ArtifactState.ACTIVE if presence[store_id] else ArtifactState.ERASED,
                active_sink=presence[store_id],
                commitment=commitment,
            )
            for store_id, artifact_type in types.items()
        }
        edges = (
            Edge("sqlite-source", "vector-index", EdgeType.INDEXED_AS),
            Edge("sqlite-source", "cache", EdgeType.COPIED_TO),
            Edge("sqlite-source", "backup", EdgeType.BACKED_UP_AS),
            Edge("sqlite-source", "model", EdgeType.USED_TO_TRAIN),
        )
        evidence: dict[str, Evidence] = {}
        for store_id in ("sqlite-source", "vector-index"):
            if not presence[store_id]:
                evidence[store_id] = Evidence(
                    f"evidence-{store_id}",
                    store_id,
                    EvidenceKind.ABSENCE_CHECK,
                    commitment=commitment,
                    observed_absent=True,
                    issued_epoch=now_epoch,
                )
        if not presence["cache"]:
            evidence["cache"] = Evidence(
                "evidence-cache",
                "cache",
                EvidenceKind.CACHE_INVALIDATION,
                observed_absent=True,
                issued_epoch=now_epoch,
                metadata=(("propagation_deadline", str(now_epoch)),),
            )
        if not presence["backup"]:
            evidence["backup"] = Evidence(
                "evidence-backup",
                "backup",
                EvidenceKind.CRYPTO_ERASURE,
                valid_signature=True,
                issued_epoch=now_epoch,
                metadata=(("key_destroyed", "true"),),
            )
        if not presence["model"]:
            evidence["model"] = Evidence(
                "evidence-model",
                "model",
                EvidenceKind.MODEL_AUDIT,
                issued_epoch=now_epoch,
                metadata=(
                    ("pass", "true"),
                    ("protocol_id", "registered-storage-lab-v1"),
                    ("reference_id", commitment),
                ),
            )
        result = audit_subject(
            ErasureGraph(nodes, edges), evidence, commitment, now_epoch
        )
        return StorageAudit(
            result,
            frozenset(store_id for store_id, present in presence.items() if present),
        )
