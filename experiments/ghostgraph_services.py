from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IMAGE_PATTERN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
NAME_PATTERN = re.compile(r"^erasemap-ghostgraph-[a-z0-9-]+$")


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def require_image(image: str) -> str:
    if IMAGE_PATTERN.fullmatch(image) is None:
        raise ValueError("GhostGraph image must be pinned by sha256 digest")
    return image


def require_name(name: str) -> str:
    if NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("refusing to manage a non-GhostGraph container")
    return name


def run_command(
    args: list[str], *, check: bool = True, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args, check=check, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"GhostGraph command timed out: {' '.join(args[:3])}") from exc


def _request(
    method: str,
    url: str,
    *,
    payload: object | None = None,
    form: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
) -> tuple[int, object]:
    selected_headers = dict(headers or {})
    if payload is not None and form is not None:
        raise ValueError("request cannot contain JSON and form data")
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        selected_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif payload is not None:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        selected_headers["Content-Type"] = "application/json"
    else:
        data = None
    request = urllib.request.Request(url, data=data, headers=selected_headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw.decode(errors="replace")


def _wait(url: str, *, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            status, _ = _request("GET", url, timeout=3)
            if status < 500:
                return
            last = f"HTTP {status}"
        except (OSError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"service readiness timed out for {url}: {last}")


@dataclass(frozen=True, slots=True)
class NativeObservation:
    node_id: str
    subject_sha256: str
    present: bool


class GhostGraphServices:
    def __init__(self, images: dict[str, str], root: Path, *, timeout: int = 120) -> None:
        if set(images) != {"identity", "lineage", "source", "vector"}:
            raise ValueError("four frozen GhostGraph service images are required")
        self.images = {key: require_image(value) for key, value in images.items()}
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        nonce = f"{os.getpid()}-{os.urandom(3).hex()}"
        self.names = {
            node: require_name(f"erasemap-ghostgraph-{node}-{nonce}") for node in images
        }
        self.ports = {node: free_port() for node in images}
        self._started: list[str] = []
        self._keycloak_token = ""
        self._mlflow_experiment_id = ""
        self._qdrant_collection = "ghostgraph"

    def _docker_run(
        self,
        node: str,
        internal_port: int,
        *,
        args: tuple[str, ...],
        env: dict[str, str] | None = None,
    ) -> None:
        command = [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            self.names[node],
            "-p",
            f"127.0.0.1:{self.ports[node]}:{internal_port}",
        ]
        for key, value in sorted((env or {}).items()):
            command.extend(("-e", f"{key}={value}"))
        command.extend((self.images[node], *args))
        run_command(command)
        self._started.append(node)

    def _inspect_images(self) -> None:
        for image in self.images.values():
            result = run_command(
                ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image]
            )
            digests = json.loads(result.stdout)
            if not isinstance(digests, list) or image not in digests:
                raise ValueError(f"GhostGraph image digest drift: {image}")

    def start(self) -> None:
        self._inspect_images()
        try:
            self._docker_run(
                "source", 6379, args=("redis-server", "--save", "", "--appendonly", "no")
            )
            self._docker_run("vector", 6333, args=())
            self._docker_run(
                "lineage",
                5000,
                args=(
                    "mlflow",
                    "server",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "5000",
                    "--backend-store-uri",
                    "sqlite:////tmp/ghostgraph-mlflow.db",
                ),
            )
            self._docker_run(
                "identity",
                8080,
                args=("start-dev", "--http-port", "8080", "--hostname-strict", "false"),
                env={
                    "KC_BOOTSTRAP_ADMIN_USERNAME": "admin",
                    "KC_BOOTSTRAP_ADMIN_PASSWORD": "ghostgraph-local-only",
                },
            )
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                if self._redis("PING") == "PONG":
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("Redis readiness timed out")
            _wait(self.url("vector") + "/collections", timeout=self.timeout)
            _wait(self.url("lineage") + "/health", timeout=self.timeout)
            _wait(self.url("identity") + "/realms/master", timeout=self.timeout)
            self._initialize_keycloak()
            self._initialize_mlflow()
            self._initialize_qdrant()
        except BaseException:
            self.stop()
            raise

    def url(self, node: str) -> str:
        if node == "source":
            return f"http://127.0.0.1:{self.ports[node]}"
        return f"http://127.0.0.1:{self.ports[node]}"

    def _initialize_keycloak(self) -> None:
        status, payload = _request(
            "POST",
            self.url("identity") + "/realms/master/protocol/openid-connect/token",
            form={
                "client_id": "admin-cli",
                "username": "admin",
                "password": "ghostgraph-local-only",
                "grant_type": "password",
            },
        )
        if status != 200 or not isinstance(payload, dict) or not payload.get("access_token"):
            raise RuntimeError("Keycloak admin authentication failed")
        self._keycloak_token = str(payload["access_token"])
        status, _ = _request(
            "POST",
            self.url("identity") + "/admin/realms",
            payload={"realm": "ghostgraph", "enabled": True},
            headers={"Authorization": f"Bearer {self._keycloak_token}"},
        )
        if status not in {201, 409}:
            raise RuntimeError(f"Keycloak realm initialization failed: {status}")

    def _initialize_mlflow(self) -> None:
        status, payload = _request(
            "POST",
            self.url("lineage") + "/api/2.0/mlflow/experiments/create",
            payload={"name": "ghostgraph"},
        )
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"MLflow experiment creation failed: {status}")
        self._mlflow_experiment_id = str(payload["experiment_id"])

    def _initialize_qdrant(self) -> None:
        status, _ = _request(
            "PUT",
            self.url("vector") + f"/collections/{self._qdrant_collection}",
            payload={"vectors": {"size": 1, "distance": "Cosine"}},
        )
        if status not in {200, 201}:
            raise RuntimeError(f"Qdrant collection creation failed: {status}")

    @staticmethod
    def _subject_hash(subject: str) -> str:
        return "sha256:" + hashlib.sha256(subject.encode()).hexdigest()

    def _redis(self, *args: str) -> str:
        result = run_command(
            ["docker", "exec", self.names["source"], "redis-cli", "--raw", *args]
        )
        return result.stdout.strip()

    def put(self, node: str, subject: str) -> None:
        if node == "source":
            if self._redis("SET", f"ghostgraph:{subject}", "1") != "OK":
                raise RuntimeError("Redis seed failed")
        elif node == "identity":
            status, _ = _request(
                "POST",
                self.url("identity") + "/admin/realms/ghostgraph/users",
                payload={"username": subject, "enabled": True},
                headers={"Authorization": f"Bearer {self._keycloak_token}"},
            )
            if status not in {201, 409}:
                raise RuntimeError(f"Keycloak subject seed failed: {status}")
        elif node == "lineage":
            status, _ = _request(
                "POST",
                self.url("lineage") + "/api/2.0/mlflow/runs/create",
                payload={
                    "experiment_id": self._mlflow_experiment_id,
                    "start_time": int(time.time() * 1000),
                    "tags": [{"key": "ghostgraph_subject", "value": subject}],
                },
            )
            if status != 200:
                raise RuntimeError(f"MLflow subject seed failed: {status}")
        elif node == "vector":
            point_id = int(hashlib.sha256(subject.encode()).hexdigest()[:15], 16)
            status, _ = _request(
                "PUT",
                self.url("vector")
                + f"/collections/{self._qdrant_collection}/points?wait=true",
                payload={
                    "points": [
                        {
                            "id": point_id,
                            "vector": [1.0],
                            "payload": {"ghostgraph_subject": subject},
                        }
                    ]
                },
            )
            if status != 200:
                raise RuntimeError(f"Qdrant subject seed failed: {status}")
        else:
            raise ValueError(f"unknown GhostGraph service node: {node}")

    def has(self, node: str, subject: str) -> NativeObservation:
        if node == "source":
            present = self._redis("EXISTS", f"ghostgraph:{subject}") == "1"
        elif node == "identity":
            query = urllib.parse.urlencode({"username": subject, "exact": "true"})
            status, payload = _request(
                "GET",
                self.url("identity") + f"/admin/realms/ghostgraph/users?{query}",
                headers={"Authorization": f"Bearer {self._keycloak_token}"},
            )
            present = status == 200 and isinstance(payload, list) and bool(payload)
        elif node == "lineage":
            status, payload = _request(
                "POST",
                self.url("lineage") + "/api/2.0/mlflow/runs/search",
                payload={
                    "experiment_ids": [self._mlflow_experiment_id],
                    "filter": f"tags.ghostgraph_subject = '{subject}'",
                    "run_view_type": "ACTIVE_ONLY",
                    "max_results": 1,
                },
            )
            runs = payload.get("runs", []) if isinstance(payload, dict) else []
            present = status == 200 and isinstance(runs, list) and bool(runs)
        elif node == "vector":
            status, payload = _request(
                "POST",
                self.url("vector")
                + f"/collections/{self._qdrant_collection}/points/scroll",
                payload={
                    "filter": {
                        "must": [
                            {
                                "key": "ghostgraph_subject",
                                "match": {"value": subject},
                            }
                        ]
                    },
                    "limit": 1,
                    "with_payload": False,
                    "with_vector": False,
                },
            )
            result = payload.get("result", {}) if isinstance(payload, dict) else {}
            points = result.get("points", []) if isinstance(result, dict) else []
            present = status == 200 and isinstance(points, list) and bool(points)
        else:
            raise ValueError(f"unknown GhostGraph service node: {node}")
        return NativeObservation(node, self._subject_hash(subject), present)

    def execute_trace(
        self,
        graph: Any,
        experiment: Any,
        subject: str,
    ) -> tuple[tuple[bool, ...], tuple[NativeObservation, ...]]:
        self.put("source", subject)
        evidence: list[NativeObservation] = []
        bits: list[bool] = []
        enabled = frozenset(experiment.enabled_operation_ids)
        for _ in range(experiment.time_buckets):
            before = {node.node_id: self.has(node.node_id, subject).present for node in graph.nodes}
            for edge in graph.edges:
                if edge.operation_id in enabled and before[edge.source_id]:
                    self.put(edge.target_id, subject)
            for node_id in experiment.checkpoint_node_ids:
                observation = self.has(node_id, subject)
                evidence.append(observation)
                bits.append(observation.present)
        return tuple(bits), tuple(evidence)

    def retained_present_everywhere(self, retained: str) -> bool:
        return all(self.has(node, retained).present for node in self.images)

    def seed_retained(self, retained: str) -> None:
        for node in self.images:
            self.put(node, retained)

    def stop(self) -> None:
        for node in reversed(self._started):
            name = require_name(self.names[node])
            run_command(["docker", "rm", "-f", name], check=False, timeout=30)
        self._started.clear()

    def cleanup_complete(self) -> bool:
        result = run_command(
            [
                "docker",
                "ps",
                "--all",
                "--format",
                "{{.Names}}",
                "--filter",
                "name=erasemap-ghostgraph-",
            ],
            check=False,
        )
        return not result.stdout.strip()

    def __enter__(self) -> GhostGraphServices:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
