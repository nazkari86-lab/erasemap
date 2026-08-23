from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

from erasemap.open_transfer import PhysicalOutcome
from erasemap.open_transfer_evidence import sha256_bytes
from experiments.open_transfer_services import EvidenceHttpClient, HttpObservation


def _dict_body(observation: HttpObservation, operation: str) -> dict[str, Any]:
    if not isinstance(observation.body, dict):
        raise ValueError(f"{operation} returned a non-object response")
    return cast(dict[str, Any], observation.body)


def _list_body(observation: HttpObservation, operation: str) -> list[dict[str, Any]]:
    if not isinstance(observation.body, list) or not all(
        isinstance(item, dict) for item in observation.body
    ):
        raise ValueError(f"{operation} returned a non-list response")
    return cast(list[dict[str, Any]], observation.body)


@dataclass(frozen=True, slots=True)
class AdapterCaseResult:
    physical: PhysicalOutcome
    post_control_recurrence: bool
    evidence_sha256: str
    remediation_milliseconds: float
    bytes_rewritten: int


class QdrantBiometricAdapter:
    def __init__(self, client: EvidenceHttpClient, *, vector_dimension: int = 4096) -> None:
        if vector_dimension <= 0:
            raise ValueError("Qdrant vector dimension must be positive")
        self.client = client
        self.vector_dimension = vector_dimension
        self._evidence: list[str] = []
        self._base_url = ""

    def _request(self, method: str, url: str, payload: object = None) -> HttpObservation:
        if url.startswith("/"):
            if not self._base_url:
                raise ValueError("Qdrant base URL is not configured")
            url = self._base_url + url
        observation = self.client.request(method, url, payload=payload)
        self._evidence.append(observation.evidence_sha256)
        return observation

    def _points_for_subject(self, collection: str, subject: str) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            f"/collections/{collection}/points/scroll",
            {
                "filter": {"must": [{"key": "subject", "match": {"value": subject}}]},
                "limit": 100,
                "with_payload": True,
                "with_vector": False,
            },
        )
        payload = _dict_body(response, "Qdrant scroll")
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("points"), list):
            raise ValueError("Qdrant scroll response is missing result.points")
        return cast(list[dict[str, Any]], result["points"])

    def _count_retained(self, collection: str) -> int:
        response = self._request(
            "POST",
            f"/collections/{collection}/points/count",
            {
                "filter": {"must": [{"key": "role", "match": {"value": "retained"}}]},
                "exact": True,
            },
        )
        payload = _dict_body(response, "Qdrant count")
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("count"), int):
            raise ValueError("Qdrant count response is missing result.count")
        return int(result["count"])

    def run_case(
        self,
        *,
        base_url: str,
        seed: int,
        fault_state: str,
        vector: np.ndarray[Any, Any],
    ) -> AdapterCaseResult:
        self._evidence.clear()
        self._base_url = base_url.rstrip("/")
        collection = f"open-transfer-{seed}-{fault_state.replace('_', '-')}"
        subject = f"face-subject-{seed}"
        target_vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        if target_vector.shape != (self.vector_dimension,):
            raise ValueError("Qdrant transfer vector has the wrong dimension")

        def url(path: str) -> str:
            return base_url.rstrip("/") + path

        create = self._request(
            "PUT",
            url(f"/collections/{collection}"),
            {"vectors": {"size": self.vector_dimension, "distance": "Cosine"}},
        )
        if create.status not in {200, 201}:
            raise RuntimeError(f"Qdrant collection creation failed: {create.status}")
        points = [
            {
                "id": 1,
                "vector": target_vector.tolist(),
                "payload": {"subject": subject, "role": "target"},
            }
        ]
        for index in range(5):
            retained = np.roll(target_vector, index + 1)
            points.append(
                {
                    "id": index + 2,
                    "vector": retained.tolist(),
                    "payload": {"subject": f"retained-{seed}-{index}", "role": "retained"},
                }
            )
        if fault_state == "surviving_derivative":
            points.append(
                {
                    "id": 1001,
                    "vector": target_vector.tolist(),
                    "payload": {"subject": subject, "role": "materialized-derivative"},
                }
            )
        upsert = self._request(
            "PUT", url(f"/collections/{collection}/points?wait=true"), {"points": points}
        )
        if upsert.status != 200:
            raise RuntimeError(f"Qdrant point upsert failed: {upsert.status}")
        retained_before = self._count_retained(collection)
        snapshot_name: str | None = None
        if fault_state in {"recovery_regeneration", "coverage_fault"}:
            snapshot = self._request(
                "POST", url(f"/collections/{collection}/snapshots"), {}
            )
            snapshot_payload = _dict_body(snapshot, "Qdrant snapshot")
            result = snapshot_payload.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("name"), str):
                raise ValueError("Qdrant snapshot response is missing result.name")
            snapshot_name = str(result["name"])
        native_started = time.perf_counter()
        deleted = self._request(
            "POST",
            url(f"/collections/{collection}/points/delete?wait=true"),
            {"points": [1]},
        )
        if deleted.status != 200:
            raise RuntimeError(f"Qdrant native deletion failed: {deleted.status}")
        primary = self._request("GET", url(f"/collections/{collection}/points/1"))
        primary_absent = primary.status == 404
        if fault_state == "coverage_fault":
            physical = PhysicalOutcome(
                primary_absent, None, None, False, retained_before, retained_before
            )
            recurrence_after_control = False
        else:
            derivative_present = bool(self._points_for_subject(collection, subject))
            recurrence = False
            if fault_state == "recovery_regeneration":
                if snapshot_name is None:
                    raise AssertionError("recovery case is missing its snapshot")
                recovered = self._request(
                    "PUT",
                    url(f"/collections/{collection}/snapshots/recover"),
                    {
                        "location": (
                            f"file:///qdrant/snapshots/{collection}/{snapshot_name}"
                        ),
                        "priority": "snapshot",
                    },
                )
                if recovered.status != 200:
                    raise RuntimeError(f"Qdrant snapshot recovery failed: {recovered.status}")
                recurrence = bool(self._points_for_subject(collection, subject))
            physical = PhysicalOutcome(
                primary_absent,
                derivative_present,
                recurrence,
                True,
                retained_before,
                self._count_retained(collection),
            )
            if derivative_present or recurrence:
                delete_filter = self._request(
                    "POST",
                    url(f"/collections/{collection}/points/delete?wait=true"),
                    {
                        "filter": {
                            "must": [{"key": "subject", "match": {"value": subject}}]
                        }
                    },
                )
                if delete_filter.status != 200:
                    raise RuntimeError("Qdrant subject control failed")
                if snapshot_name is not None:
                    self._request(
                        "DELETE", url(f"/collections/{collection}/snapshots/{snapshot_name}")
                    )
                recurrence_after_control = bool(
                    self._points_for_subject(collection, subject)
                )
            else:
                recurrence_after_control = False
        retained_after = self._count_retained(collection)
        if retained_after < retained_before:
            physical = PhysicalOutcome(
                physical.primary_absent,
                physical.derivative_present,
                physical.recovery_recurrence,
                physical.coverage_complete,
                retained_before,
                retained_after,
            )
        evidence_hash = sha256_bytes("\n".join(self._evidence).encode())
        return AdapterCaseResult(
            physical=physical,
            post_control_recurrence=recurrence_after_control,
            evidence_sha256=evidence_hash,
            remediation_milliseconds=(time.perf_counter() - native_started) * 1000.0,
            bytes_rewritten=len(target_vector.tobytes()),
        )


class KeycloakIdentityAdapter:
    def __init__(self, client: EvidenceHttpClient, base_url: str) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    def admin_token(self, username: str, password: str) -> str:
        response = self.client.request(
            "POST",
            f"{self.base_url}/realms/master/protocol/openid-connect/token",
            form={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            timeout=60.0,
        )
        payload = _dict_body(response, "Keycloak token")
        token = payload.get("access_token")
        if response.status != 200 or not isinstance(token, str):
            raise RuntimeError("Keycloak bootstrap token acquisition failed")
        return token

    def create_realm(self, token: str, realm: str) -> None:
        response = self.client.request(
            "POST",
            f"{self.base_url}/admin/realms",
            headers={"Authorization": f"Bearer {token}"},
            payload={"realm": realm, "enabled": True},
            timeout=60.0,
        )
        if response.status not in {201, 409}:
            raise RuntimeError(f"Keycloak realm creation failed: {response.status}")

    def create_user(self, token: str, realm: str, username: str) -> str:
        response = self.client.request(
            "POST",
            f"{self.base_url}/admin/realms/{realm}/users",
            headers={"Authorization": f"Bearer {token}"},
            payload={"username": username, "enabled": True},
            timeout=60.0,
        )
        if response.status != 201:
            raise RuntimeError(f"Keycloak user creation failed: {response.status}")
        users = self.search_users(token, realm, username)
        if len(users) != 1 or not isinstance(users[0].get("id"), str):
            raise ValueError("Keycloak user lookup did not return one stable id")
        return str(users[0]["id"])

    def search_users(self, token: str, realm: str, username: str) -> list[dict[str, Any]]:
        response = self.client.request(
            "GET",
            f"{self.base_url}/admin/realms/{realm}/users?username={username}&exact=true",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        if response.status != 200:
            raise RuntimeError(f"Keycloak user search failed: {response.status}")
        return _list_body(response, "Keycloak user search")

    def delete_user(self, token: str, realm: str, user_id: str) -> None:
        response = self.client.request(
            "DELETE",
            f"{self.base_url}/admin/realms/{realm}/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        if response.status != 204:
            raise RuntimeError(f"Keycloak user deletion failed: {response.status}")

    @staticmethod
    def export_contains_username(export_root: Path, username: str) -> bool:
        return any(
            username in path.read_text(errors="replace")
            for path in export_root.glob("*.json")
        )


class MLflowLineageAdapter:
    def __init__(self, client: EvidenceHttpClient, base_url: str) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    def create_experiment(self, name: str, artifact_location: str) -> str:
        response = self.client.request(
            "POST",
            f"{self.base_url}/api/2.0/mlflow/experiments/create",
            payload={"name": name, "artifact_location": artifact_location},
        )
        payload = _dict_body(response, "MLflow experiment creation")
        experiment_id = payload.get("experiment_id")
        if response.status != 200 or not isinstance(experiment_id, str):
            raise RuntimeError("MLflow experiment creation failed")
        return experiment_id

    def create_run(self, experiment_id: str, subject_commitment: str) -> str:
        response = self.client.request(
            "POST",
            f"{self.base_url}/api/2.0/mlflow/runs/create",
            payload={
                "experiment_id": experiment_id,
                "start_time": 0,
                "tags": [
                    {"key": "erasemap.subject_commitment", "value": subject_commitment}
                ],
            },
        )
        payload = _dict_body(response, "MLflow run creation")
        run = payload.get("run")
        info = run.get("info") if isinstance(run, dict) else None
        run_id = info.get("run_id") if isinstance(info, dict) else None
        if response.status != 200 or not isinstance(run_id, str):
            raise RuntimeError("MLflow run creation failed")
        return run_id

    def delete_run(self, run_id: str) -> None:
        response = self.client.request(
            "POST",
            f"{self.base_url}/api/2.0/mlflow/runs/delete",
            payload={"run_id": run_id},
        )
        if response.status != 200:
            raise RuntimeError(f"MLflow run deletion failed: {response.status}")

    def restore_run(self, run_id: str) -> None:
        response = self.client.request(
            "POST",
            f"{self.base_url}/api/2.0/mlflow/runs/restore",
            payload={"run_id": run_id},
        )
        if response.status != 200:
            raise RuntimeError(f"MLflow run restore failed: {response.status}")

    def get_run(self, run_id: str) -> dict[str, Any]:
        response = self.client.request(
            "GET", f"{self.base_url}/api/2.0/mlflow/runs/get?run_id={run_id}"
        )
        if response.status != 200:
            raise RuntimeError(f"MLflow run lookup failed: {response.status}")
        return _dict_body(response, "MLflow run lookup")

    @staticmethod
    def artifact_contains_subject(artifact_root: Path, commitment: str) -> bool | None:
        if not artifact_root.exists():
            return None
        return any(
            commitment.encode() in path.read_bytes()
            for path in artifact_root.rglob("*")
            if path.is_file()
        )
