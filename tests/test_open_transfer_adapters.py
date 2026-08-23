from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from erasemap.open_transfer_evidence import EvidenceLedger
from experiments.open_transfer_adapters import (
    KeycloakIdentityAdapter,
    MLflowLineageAdapter,
    QdrantBiometricAdapter,
)
from experiments.open_transfer_services import (
    DockerService,
    EvidenceHttpClient,
    HttpObservation,
    free_port,
    require_digest_image,
    require_transfer_container_name,
)
from experiments.prepare_open_transfer_assets import build_vector_asset, write_deterministic_npz

IMAGE = "registry.example/service@sha256:" + "a" * 64


class FakeHttpClient:
    def __init__(self, responses: list[HttpObservation]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> HttpObservation:
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)


def observation(status: int, body: object, index: int = 0) -> HttpObservation:
    return HttpObservation(status, body, "sha256:" + f"{index:064x}")


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], bool]] = []

    def __call__(
        self,
        args: list[str],
        *,
        input_bytes: bytes | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        del input_bytes
        self.calls.append((tuple(args), check))
        if args[:3] == ["docker", "image", "inspect"]:
            output = json.dumps([IMAGE]).encode()
        elif args[:2] == ["docker", "run"]:
            output = b"container-id\n"
        else:
            output = b""
        return subprocess.CompletedProcess(args, 0, output, b"")


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/missing"):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","token":"server-secret"}')

    def do_DELETE(self) -> None:
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        del format, args


@pytest.fixture
def http_server() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_name_image_and_port_validation() -> None:
    assert require_transfer_container_name("erasemap-transfer-keycloak-123")
    assert require_digest_image(IMAGE) == IMAGE
    assert free_port() > 0
    with pytest.raises(ValueError, match="non-transfer"):
        require_transfer_container_name("postgres-production")
    with pytest.raises(ValueError, match="invalid transfer"):
        require_transfer_container_name("erasemap-transfer-BAD SPACE")
    with pytest.raises(ValueError, match="immutable"):
        require_digest_image("registry.example/service:latest")


def test_docker_service_builds_scoped_command_and_tears_down(tmp_path: Path) -> None:
    runner = FakeRunner()
    mount = tmp_path / "data"
    mount.mkdir()
    service = DockerService(
        family="keycloak",
        image=IMAGE,
        internal_port=8080,
        root=tmp_path,
        command_runner=runner,
        nonce="abc123",
    )
    service.start(
        env={"SAFE": "value"},
        mounts=((mount, "/opt/service/data", False),),
        args=("start-dev",),
    )
    assert service.container_name.startswith("erasemap-transfer-keycloak-")
    assert service.base_url.startswith("http://127.0.0.1:")
    assert service.inspect_digest() == IMAGE
    service.stop()
    run_args = runner.calls[0][0]
    assert run_args[:3] == ("docker", "run", "--detach")
    assert ("-p", f"127.0.0.1:{service.host_port}:8080") == (
        run_args[run_args.index("-p")],
        run_args[run_args.index("-p") + 1],
    )
    assert runner.calls[-1][0][:3] == ("docker", "rm", "-f")


def test_docker_service_graceful_stop_flushes_before_cleanup(tmp_path: Path) -> None:
    runner = FakeRunner()
    service = DockerService(
        family="keycloak",
        image=IMAGE,
        internal_port=8080,
        root=tmp_path,
        command_runner=runner,
        nonce="graceful",
    )
    service.start(env={}, mounts=(), args=("start-dev",))
    service.stop_gracefully(timeout_seconds=20)
    assert runner.calls[-2][0][:4] == ("docker", "stop", "--time", "20")
    assert runner.calls[-1][0][:3] == ("docker", "rm", "-f")
    with pytest.raises(ValueError, match="between 1 and 120"):
        service._running = True
        service.stop_gracefully(timeout_seconds=0)


def test_docker_service_rejects_mount_outside_root_and_digest_drift(tmp_path: Path) -> None:
    runner = FakeRunner()
    service = DockerService(
        family="qdrant",
        image=IMAGE,
        internal_port=6333,
        root=tmp_path,
        command_runner=runner,
        nonce="abc123",
    )
    with pytest.raises(ValueError, match="runner root"):
        service.start(env={}, mounts=((tmp_path.parent, "/outside", False),), args=())
    service.start(env={}, mounts=(), args=())
    runner.calls.clear()
    runner_image = "registry.example/service@sha256:" + "c" * 64

    def drift_runner(
        args: list[str], *, input_bytes: bytes | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        del input_bytes, check
        return subprocess.CompletedProcess(args, 0, json.dumps([runner_image]).encode(), b"")

    service.command_runner = drift_runner
    with pytest.raises(ValueError, match="digest drift"):
        service.inspect_digest()


def test_http_client_records_json_empty_and_404_without_secrets(
    tmp_path: Path, http_server: str
) -> None:
    ledger = EvidenceLedger(tmp_path / "evidence.jsonl")
    client = EvidenceHttpClient(ledger, secret_values=("client-secret", "server-secret"))
    ok = client.request(
        "GET",
        f"{http_server}/status?token=client-secret",
        headers={"Authorization": "Bearer client-secret"},
    )
    assert ok.status == 200
    assert ok.body == {"status": "ok", "token": "server-secret"}
    assert ok.evidence_sha256.startswith("sha256:")
    missing = client.request("GET", f"{http_server}/missing")
    assert missing.status == 404
    assert missing.body == {}
    empty = client.request("DELETE", f"{http_server}/object")
    assert empty.status == 204
    assert empty.body == {}
    persisted = (tmp_path / "evidence.jsonl").read_text()
    assert "client-secret" not in persisted
    assert "server-secret" not in persisted


def test_public_face_asset_is_subject_disjoint_and_deterministic(tmp_path: Path) -> None:
    faces = np.arange(400 * 4096, dtype=np.float32).reshape(400, 4096)
    faces /= float(faces.max())
    targets = np.repeat(np.arange(40, dtype=np.int64), 10)
    asset = build_vector_asset(
        faces,
        targets,
        development_subject_ids=(35, 36, 37, 38, 39),
        confirmatory_subject_ids=(0, 1, 2, 3, 4),
        sample_offset=0,
    )
    assert asset.development_vectors.shape == (5, 4096)
    assert asset.confirmatory_vectors.shape == (5, 4096)
    assert tuple(asset.development_subject_ids) == (35, 36, 37, 38, 39)
    assert tuple(asset.confirmatory_subject_ids) == (0, 1, 2, 3, 4)
    assert not set(asset.development_subject_ids) & set(asset.confirmatory_subject_ids)
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    write_deterministic_npz(first, asset.arrays())
    write_deterministic_npz(second, asset.arrays())
    assert first.read_bytes() == second.read_bytes()


def test_qdrant_safe_workflow_uses_stock_endpoints() -> None:
    responses = [
        observation(200, {}),
        observation(200, {}),
        observation(200, {"result": {"count": 5}}),
        observation(200, {}),
        observation(404, {}),
        observation(200, {"result": {"points": []}}),
        observation(200, {"result": {"count": 5}}),
        observation(200, {"result": {"count": 5}}),
    ]
    client = FakeHttpClient(responses)
    adapter = QdrantBiometricAdapter(client)  # type: ignore[arg-type]
    result = adapter.run_case(
        base_url="http://127.0.0.1:6333",
        seed=3101,
        fault_state="safe_native",
        vector=np.ones(4096, dtype=np.float32),
    )
    assert result.physical.primary_absent
    assert result.physical.derivative_present is False
    assert result.physical.recovery_recurrence is False
    assert not result.post_control_recurrence
    assert client.calls[0][1].startswith("http://127.0.0.1:6333/collections/")
    assert client.calls[3][1].endswith("/points/delete?wait=true")


def test_keycloak_admin_workflow_uses_form_token_and_rest_endpoints(tmp_path: Path) -> None:
    client = FakeHttpClient(
        [
            observation(200, {"access_token": "token"}),
            observation(201, {}),
            observation(201, {}),
            observation(200, [{"id": "user-id", "username": "subject"}]),
            observation(204, {}),
            observation(200, []),
        ]
    )
    adapter = KeycloakIdentityAdapter(client, "http://127.0.0.1:8080")  # type: ignore[arg-type]
    token = adapter.admin_token("admin", "password")
    adapter.create_realm(token, "transfer")
    user_id = adapter.create_user(token, "transfer", "subject")
    adapter.delete_user(token, "transfer", user_id)
    assert adapter.search_users(token, "transfer", "subject") == []
    assert client.calls[0][2]["form"]["grant_type"] == "password"
    export = tmp_path / "export"
    export.mkdir()
    (export / "transfer-users-0.json").write_text('{"username":"subject"}')
    assert adapter.export_contains_username(export, "subject")


def test_mlflow_soft_delete_restore_and_artifact_observation(tmp_path: Path) -> None:
    client = FakeHttpClient(
        [
            observation(200, {"experiment_id": "7"}),
            observation(200, {"run": {"info": {"run_id": "run-1"}}}),
            observation(200, {}),
            observation(200, {"run": {"info": {"lifecycle_stage": "deleted"}}}),
            observation(200, {}),
        ]
    )
    adapter = MLflowLineageAdapter(client, "http://127.0.0.1:5000")  # type: ignore[arg-type]
    experiment = adapter.create_experiment("transfer", "file:///artifacts")
    run_id = adapter.create_run(experiment, "subject-hash")
    adapter.delete_run(run_id)
    assert adapter.get_run(run_id)["run"]["info"]["lifecycle_stage"] == "deleted"
    adapter.restore_run(run_id)
    artifact = tmp_path / "artifacts" / "record.json"
    artifact.parent.mkdir()
    artifact.write_text('{"subject":"subject-hash"}')
    assert adapter.artifact_contains_subject(tmp_path / "artifacts", "subject-hash") is True
    assert adapter.artifact_contains_subject(tmp_path / "missing", "subject-hash") is None
