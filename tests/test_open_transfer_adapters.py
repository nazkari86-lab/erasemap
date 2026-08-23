from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from erasemap.open_transfer_evidence import EvidenceLedger
from experiments.open_transfer_services import (
    DockerService,
    EvidenceHttpClient,
    free_port,
    require_digest_image,
    require_transfer_container_name,
)

IMAGE = "registry.example/service@sha256:" + "a" * 64


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
