from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlencode

from erasemap.open_transfer_evidence import (
    EvidenceLedger,
    assert_no_secrets,
    canonical_evidence,
    canonical_json,
)

_IMAGE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_CONTAINER = re.compile(r"^[a-z0-9][a-z0-9_.-]+$")


def require_transfer_container_name(name: str) -> str:
    if not name.startswith("erasemap-transfer-"):
        raise ValueError("refusing to manage a non-transfer container")
    if _CONTAINER.fullmatch(name) is None:
        raise ValueError("invalid transfer container name")
    return name


def require_digest_image(image: str) -> str:
    if _IMAGE.fullmatch(image) is None:
        raise ValueError("container image must use an immutable sha256 digest")
    return image


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def run_command(
    args: list[str], *, input_bytes: bytes | None = None, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, input=input_bytes, capture_output=True, check=check)


CommandRunner = Callable[
    [list[str]],
    subprocess.CompletedProcess[bytes],
]


@dataclass(frozen=True, slots=True)
class HttpObservation:
    status: int
    body: object
    evidence_sha256: str


class DockerService(AbstractContextManager["DockerService"]):
    def __init__(
        self,
        *,
        family: str,
        image: str,
        internal_port: int,
        root: Path,
        command_runner: Any = run_command,
        nonce: str | None = None,
    ) -> None:
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", family) is None:
            raise ValueError("invalid service family name")
        if internal_port < 1 or internal_port > 65535:
            raise ValueError("invalid internal service port")
        self.image = require_digest_image(image)
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.internal_port = internal_port
        self.host_port = free_port()
        selected_nonce = nonce or os.urandom(4).hex()
        self.container_name = require_transfer_container_name(
            f"erasemap-transfer-{family}-{os.getpid()}-{selected_nonce}"
        )
        self.command_runner = command_runner
        self._running = False

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.host_port}"

    def start(
        self,
        *,
        env: Mapping[str, str],
        mounts: tuple[tuple[Path, str, bool], ...],
        args: tuple[str, ...],
    ) -> None:
        if self._running:
            raise ValueError("service is already running")
        command = [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            self.container_name,
            "-p",
            f"127.0.0.1:{self.host_port}:{self.internal_port}",
        ]
        for key, value in sorted(env.items()):
            if re.fullmatch(r"[A-Z_][A-Z0-9_]*", key) is None:
                raise ValueError("invalid container environment key")
            command.extend(("-e", f"{key}={value}"))
        for source, target, read_only in mounts:
            resolved = source.resolve()
            if not resolved.is_relative_to(self.root):
                raise ValueError("container mount must stay inside the runner root")
            container_path = PurePosixPath(target)
            if not container_path.is_absolute() or ".." in container_path.parts:
                raise ValueError("container mount target must be an absolute safe path")
            suffix = ":ro" if read_only else ""
            command.extend(("-v", f"{resolved}:{target}{suffix}"))
        command.extend((self.image, *args))
        self.command_runner(command, check=True)
        self._running = True

    def inspect_digest(self) -> str:
        result = self.command_runner(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{json .RepoDigests}}",
                self.image,
            ],
            check=True,
        )
        try:
            repo_digests = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid docker image inspection response") from exc
        if not isinstance(repo_digests, list) or self.image not in repo_digests:
            raise ValueError("container image digest drift")
        return self.image

    def stop(self) -> None:
        if not self._running:
            return
        name = require_transfer_container_name(self.container_name)
        self.command_runner(["docker", "rm", "-f", name], check=False)
        self._running = False

    def stop_gracefully(self, *, timeout_seconds: int = 30) -> None:
        if not self._running:
            return
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise ValueError("graceful stop timeout must be between 1 and 120 seconds")
        name = require_transfer_container_name(self.container_name)
        self.command_runner(
            ["docker", "stop", "--time", str(timeout_seconds), name], check=False
        )
        self.command_runner(["docker", "rm", "-f", name], check=False)
        self._running = False

    def __exit__(self, *args: object) -> None:
        self.stop()


class EvidenceHttpClient:
    def __init__(self, ledger: EvidenceLedger, *, secret_values: tuple[str, ...] = ()) -> None:
        self.ledger = ledger
        self.secret_values = secret_values
        self._sequence = len(ledger.records())

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: object = None,
        form: Mapping[str, str] | None = None,
        timeout: float = 15.0,
    ) -> HttpObservation:
        if payload is not None and form is not None:
            raise ValueError("HTTP request cannot contain both JSON and form bodies")
        selected_headers = dict(headers or {})
        body: bytes | None
        if form is not None:
            body = urlencode(form).encode()
            evidence_body: object = dict(form)
            selected_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = canonical_json(payload) if payload is not None else None
            evidence_body = payload
        if payload is not None:
            selected_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(
            url,
            data=body,
            headers=selected_headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(response.status)
                raw_response = response.read()
        except urllib.error.HTTPError as error:
            status = int(error.code)
            raw_response = error.read()
        if raw_response:
            try:
                response_body: object = json.loads(raw_response)
            except json.JSONDecodeError:
                response_body = {"text": raw_response.decode(errors="replace")}
        else:
            response_body = {}
        evidence = canonical_evidence(
            method=method,
            url=url,
            request_headers=selected_headers,
            request_body=evidence_body,
            status=status,
            response_body=response_body,
        )
        evidence["sequence"] = self._sequence
        self._sequence += 1
        assert_no_secrets(evidence, self.secret_values)
        digest = self.ledger.append(evidence)
        return HttpObservation(status, response_body, digest)


def wait_for_http(
    client: EvidenceHttpClient,
    url: str,
    *,
    accepted_statuses: frozenset[int] = frozenset({200}),
    timeout: float = 60.0,
) -> HttpObservation:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            observation = client.request("GET", url, timeout=min(2.0, timeout))
            if observation.status in accepted_statuses:
                return observation
        except OSError as exc:
            last_error = exc
        time.sleep(0.2)
    message = f"service readiness timeout for {url}"
    if last_error is not None:
        raise TimeoutError(message) from last_error
    raise TimeoutError(message)
