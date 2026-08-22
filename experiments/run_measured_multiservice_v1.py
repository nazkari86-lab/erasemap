from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import AbstractContextManager
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from erasemap.cdc import evaluate_actions, exact_cdc
from erasemap.measured_systems import StrategyMeasurement, paired_summary
from erasemap.multiview_verifier import unknown_channel, upper_bound_channel
from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    Transition,
    TransitionTarget,
)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def command(
    args: list[str], *, input_bytes: bytes | None = None, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        input=input_bytes,
        capture_output=True,
        check=check,
    )


def http_json(method: str, url: str, payload: object | None = None) -> dict[str, Any]:
    body = canonical(payload) if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            decoded = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {"status": "not_found"}
        raise
    return cast(dict[str, Any], decoded)


class Services(AbstractContextManager["Services"]):
    def __init__(self, root: Path, qdrant_image: str) -> None:
        self.root = root
        self.postgres_port = free_port()
        self.redis_port = free_port()
        self.qdrant_port = free_port()
        self.qdrant_image = qdrant_image
        self.container = f"erasemap-qdrant-{os.getpid()}"
        self.processes: list[subprocess.Popen[bytes]] = []

    def __enter__(self) -> Services:
        pgdata = self.root / "postgres"
        socket_dir = self.root / "pgsocket"
        redis_dir = self.root / "redis"
        socket_dir.mkdir()
        redis_dir.mkdir()
        command(
            [
                "/opt/homebrew/bin/initdb",
                "-D",
                str(pgdata),
                "-A",
                "trust",
                "--no-locale",
            ]
        )
        self.processes.append(
            subprocess.Popen(
                [
                    "/opt/homebrew/bin/postgres",
                    "-D",
                    str(pgdata),
                    "-p",
                    str(self.postgres_port),
                    "-k",
                    str(socket_dir),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        self.processes.append(
            subprocess.Popen(
                [
                    "/opt/homebrew/bin/redis-server",
                    "--port",
                    str(self.redis_port),
                    "--bind",
                    "127.0.0.1",
                    "--protected-mode",
                    "yes",
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                    "--dir",
                    str(redis_dir),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        command(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                self.container,
                "-p",
                f"127.0.0.1:{self.qdrant_port}:6333",
                self.qdrant_image,
            ]
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            pg = command(self.psql_args("SELECT 1"), check=False).returncode == 0
            redis = command(self.redis_args("PING"), check=False).stdout.strip() == b"PONG"
            try:
                qdrant = (
                    http_json("GET", f"http://127.0.0.1:{self.qdrant_port}/collections").get(
                        "status"
                    )
                    == "ok"
                )
            except (OSError, ValueError):
                qdrant = False
            if pg and redis and qdrant:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("multi-service startup timeout")
        command(
            self.psql_args(
                "CREATE TABLE subjects (id integer PRIMARY KEY, label double precision NOT NULL, "
                "embedding text NOT NULL);"
            )
        )
        return self

    def __exit__(self, *args: object) -> None:
        command(["docker", "rm", "-f", self.container], check=False)
        for process in reversed(self.processes):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    def psql_args(self, sql: str | None = None) -> list[str]:
        args = [
            "/opt/homebrew/bin/psql",
            "-h",
            "127.0.0.1",
            "-p",
            str(self.postgres_port),
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-qAt",
        ]
        return [*args, "-c", sql] if sql is not None else args

    def redis_args(self, *parts: str) -> list[str]:
        return [
            "/opt/homebrew/bin/redis-cli",
            "-h",
            "127.0.0.1",
            "-p",
            str(self.redis_port),
            *parts,
        ]


def vectors(
    seed: int, subjects: int, dimension: int
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    rng = np.random.default_rng(seed)
    features = rng.normal(size=(subjects, dimension)).astype(np.float64)
    teacher = rng.normal(size=dimension)
    labels = features @ teacher + rng.normal(scale=0.05, size=subjects)
    return features, labels


def load_source(
    services: Services, features: np.ndarray[Any, Any], labels: np.ndarray[Any, Any]
) -> None:
    command(services.psql_args("TRUNCATE subjects"))
    stream = io.StringIO()
    writer = csv.writer(stream)
    for subject_id, (vector, label) in enumerate(zip(features, labels, strict=True)):
        writer.writerow((subject_id, float(label), ";".join(map(str, vector.tolist()))))
    sql = "COPY subjects(id,label,embedding) FROM STDIN WITH (FORMAT csv)"
    command([*services.psql_args(), "-c", sql], input_bytes=stream.getvalue().encode())


def retained_source(
    services: Services,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], list[int]]:
    sql = "COPY (SELECT id,label,embedding FROM subjects ORDER BY id) TO STDOUT WITH (FORMAT csv)"
    raw = command([*services.psql_args(), "-c", sql]).stdout.decode()
    rows = list(csv.reader(io.StringIO(raw)))
    ids = [int(row[0]) for row in rows]
    labels = np.asarray([float(row[1]) for row in rows], dtype=np.float64)
    features = np.asarray([[float(item) for item in row[2].split(";")] for row in rows])
    return features, labels, ids


def redis_protocol(commands: list[tuple[bytes, ...]]) -> bytes:
    payload = bytearray()
    for parts in commands:
        payload.extend(f"*{len(parts)}\r\n".encode())
        for part in parts:
            payload.extend(f"${len(part)}\r\n".encode())
            payload.extend(part + b"\r\n")
    return bytes(payload)


def redis_pipe(services: Services, commands: list[tuple[bytes, ...]]) -> int:
    payload = redis_protocol(commands)
    result = command([*services.redis_args(), "--pipe"], input_bytes=payload)
    if b"errors: 0" not in result.stdout:
        raise RuntimeError("Redis pipeline failed")
    return len(payload)


def qdrant_collection(services: Services, name: str, dimension: int) -> int:
    payload = {"vectors": {"distance": "Cosine", "size": dimension}}
    http_json("PUT", f"http://127.0.0.1:{services.qdrant_port}/collections/{name}", payload)
    return len(canonical(payload))


def qdrant_upsert(
    services: Services, name: str, ids: list[int], features: np.ndarray[Any, Any]
) -> int:
    payload = {
        "points": [
            {"id": subject_id, "vector": vector.tolist()}
            for subject_id, vector in zip(ids, features, strict=True)
        ]
    }
    http_json(
        "PUT",
        f"http://127.0.0.1:{services.qdrant_port}/collections/{name}/points?wait=true",
        payload,
    )
    return len(canonical(payload))


def model_state(
    features: np.ndarray[Any, Any], labels: np.ndarray[Any, Any]
) -> dict[str, np.ndarray[Any, Any]]:
    regularization = np.eye(features.shape[1], dtype=np.float64)
    xtx = features.T @ features
    xty = features.T @ labels
    weights = np.linalg.solve(xtx + regularization, xty)
    return {"weights": weights, "xtx": xtx, "xty": xty}


def write_model(path: Path, state: dict[str, np.ndarray[Any, Any]]) -> int:
    np.savez(path, **state)
    return path.stat().st_size


def setup_backups(root: Path, seed: int, features: np.ndarray[Any, Any]) -> None:
    root.mkdir(parents=True)
    for subject_id, vector in enumerate(features):
        key = hashlib.sha256(f"{seed}:{subject_id}:key".encode()).digest()
        nonce = hashlib.sha256(f"{seed}:{subject_id}:nonce".encode()).digest()[:12]
        ciphertext = AESGCM(key).encrypt(nonce, vector.tobytes(), str(subject_id).encode())
        (root / f"{subject_id}.aesgcm").write_bytes(nonce + ciphertext)
        (root / f"{subject_id}.key").write_bytes(key)


def setup_derivatives(
    services: Services,
    root: Path,
    prefix: str,
    features: np.ndarray[Any, Any],
    labels: np.ndarray[Any, Any],
) -> None:
    ids = list(range(len(features)))
    qdrant_collection(services, prefix, features.shape[1])
    qdrant_upsert(services, prefix, ids, features)
    redis_pipe(
        services,
        [
            (b"SET", f"{prefix}:{subject_id}".encode(), vector.tobytes())
            for subject_id, vector in zip(ids, features, strict=True)
        ],
    )
    setup_backups(root / "backups", int(prefix.split("-")[-1]), features)
    write_model(root / "model.npz", model_state(features, labels))


def targeted_remediation(
    services: Services,
    root: Path,
    prefix: str,
    target: int,
    target_vector: np.ndarray[Any, Any],
    target_label: float,
) -> tuple[float, int, dict[str, float]]:
    started = time.perf_counter()
    components: dict[str, float] = {}
    bytes_written = 0
    mark = time.perf_counter()
    payload = {"points": [target]}
    http_json(
        "POST",
        f"http://127.0.0.1:{services.qdrant_port}/collections/{prefix}/points/delete?wait=true",
        payload,
    )
    bytes_written += len(canonical(payload))
    components["vector_seconds"] = time.perf_counter() - mark
    mark = time.perf_counter()
    redis_payload = redis_protocol(((b"DEL", f"{prefix}:{target}".encode()),))
    command([*services.redis_args(), "--pipe"], input_bytes=redis_payload)
    bytes_written += len(redis_payload)
    components["cache_seconds"] = time.perf_counter() - mark
    mark = time.perf_counter()
    (root / "backups" / f"{target}.key").unlink()
    components["backup_seconds"] = time.perf_counter() - mark
    mark = time.perf_counter()
    with np.load(root / "model.npz") as archive:
        xtx = np.asarray(archive["xtx"])
        xty = np.asarray(archive["xty"])
    xtx = xtx - np.outer(target_vector, target_vector)
    xty = xty - target_vector * target_label
    weights = np.linalg.solve(xtx + np.eye(len(target_vector)), xty)
    bytes_written += write_model(root / "model.npz", {"weights": weights, "xtx": xtx, "xty": xty})
    components["model_seconds"] = time.perf_counter() - mark
    return time.perf_counter() - started, bytes_written, components


def rebuild_remediation(
    services: Services,
    root: Path,
    prefix: str,
    original_subjects: int,
    retained_features: np.ndarray[Any, Any],
    retained_labels: np.ndarray[Any, Any],
    retained_ids: list[int],
) -> tuple[float, int, dict[str, float]]:
    started = time.perf_counter()
    components: dict[str, float] = {}
    bytes_written = 0
    mark = time.perf_counter()
    http_json("DELETE", f"http://127.0.0.1:{services.qdrant_port}/collections/{prefix}")
    bytes_written += qdrant_collection(services, prefix, retained_features.shape[1])
    bytes_written += qdrant_upsert(services, prefix, retained_ids, retained_features)
    components["vector_seconds"] = time.perf_counter() - mark
    mark = time.perf_counter()
    commands = [
        (b"DEL", f"{prefix}:{subject_id}".encode()) for subject_id in range(original_subjects)
    ]
    commands.extend(
        (b"SET", f"{prefix}:{subject_id}".encode(), vector.tobytes())
        for subject_id, vector in zip(retained_ids, retained_features, strict=True)
    )
    bytes_written += redis_pipe(services, commands)
    components["cache_seconds"] = time.perf_counter() - mark
    mark = time.perf_counter()
    old = root / "backups"
    staging = root / "backups-rebuilt"
    staging.mkdir()
    for subject_id in retained_ids:
        for suffix in ("aesgcm", "key"):
            source = old / f"{subject_id}.{suffix}"
            destination = staging / source.name
            shutil.copyfile(source, destination)
            bytes_written += destination.stat().st_size
    shutil.rmtree(old)
    staging.rename(old)
    components["backup_seconds"] = time.perf_counter() - mark
    mark = time.perf_counter()
    bytes_written += write_model(
        root / "model.npz", model_state(retained_features, retained_labels)
    )
    components["model_seconds"] = time.perf_counter() - mark
    return time.perf_counter() - started, bytes_written, components


def qdrant_count(services: Services, prefix: str) -> int:
    response = http_json(
        "POST",
        f"http://127.0.0.1:{services.qdrant_port}/collections/{prefix}/points/count",
        {"exact": True},
    )
    return int(response["result"]["count"])


def pcug_verdict(model_delta: float, all_absent: bool) -> str:
    subject = "pilot-subject"
    node_state = EdgeState.CLOSED if all_absent else EdgeState.ACTIVE
    nodes = (
        PCUGNode("subject", "SUBJECT", subject, EdgeState.CLOSED, evidence_id="source-delete"),
        PCUGNode("vector", "VECTOR", subject, node_state, active_sink=not all_absent),
        PCUGNode("cache", "CACHE", subject, node_state, active_sink=not all_absent),
        PCUGNode("backup", "BACKUP", subject, node_state, active_sink=not all_absent),
        PCUGNode("model", "SHARED_MODEL", "shared"),
    )
    edges = (
        PCUGEdge("subject", "vector", EdgeKind.MATERIAL, node_state, True, subject),
        PCUGEdge("subject", "cache", EdgeKind.MATERIAL, node_state, True, subject),
        PCUGEdge("subject", "backup", EdgeKind.MATERIAL, node_state, True, subject),
        PCUGEdge("subject", "model", EdgeKind.INFLUENCE, node_state, True, subject),
    )
    channel = upper_bound_channel(
        "model_weight_equivalence",
        value=model_delta,
        upper_bound=model_delta,
        threshold=1e-8,
        evidence_id="exact-ridge-reference",
    )
    graph = PCUGGraph(nodes, edges, (channel,))
    protocol = CDCProtocol(
        "measured-delete",
        subject,
        frozenset({"subject"}),
        frozenset({"vector", "cache", "backup"}),
        frozenset({"model_weight_equivalence"}),
    )
    return evaluate_actions(graph, protocol, ()).verdict.value


def audit_strategy(
    services: Services,
    root: Path,
    prefix: str,
    target: int,
    retained_ids: list[int],
    exact_weights: np.ndarray[Any, Any],
) -> tuple[str, int, float]:
    vector_absent = (
        http_json(
            "GET", f"http://127.0.0.1:{services.qdrant_port}/collections/{prefix}/points/{target}"
        ).get("status")
        == "not_found"
    )
    vector_count = qdrant_count(services, prefix)
    cache_absent = (
        command(services.redis_args("EXISTS", f"{prefix}:{target}")).stdout.strip() == b"0"
    )
    retained_cache = sum(
        command(services.redis_args("EXISTS", f"{prefix}:{subject_id}")).stdout.strip() == b"1"
        for subject_id in retained_ids
    )
    backups = root / "backups"
    backup_absent = not (backups / f"{target}.key").exists()
    retained_backups = sum((backups / f"{subject_id}.key").exists() for subject_id in retained_ids)
    with np.load(root / "model.npz") as archive:
        weights = np.asarray(archive["weights"])
    model_delta = float(np.max(np.abs(weights - exact_weights)))
    retained = min(vector_count, retained_cache, retained_backups)
    all_absent = vector_absent and cache_absent and backup_absent
    return pcug_verdict(model_delta, all_absent), retained, model_delta


def planner_from_calibration(records: list[dict[str, Any]]) -> dict[str, object]:
    targeted = [item for item in records if item["strategy"] == "targeted_exact_cdc"]
    rebuild = [item for item in records if item["strategy"] == "rebuild_all"]
    component_names = ("vector", "cache", "backup", "model")
    costs = {
        name: max(
            1,
            round(
                1_000_000
                * float(np.median([item["components"][f"{name}_seconds"] for item in targeted]))
            ),
        )
        for name in component_names
    }
    rebuild_cost = max(
        1,
        round(1_000_000 * float(np.median([item["seconds"] for item in rebuild]))),
    )
    subject = "pilot-subject"
    nodes = (
        PCUGNode("subject", "SUBJECT", subject),
        *(PCUGNode(name, name.upper(), subject, active_sink=True) for name in component_names),
    )
    edges = (
        *(
            PCUGEdge("subject", name, EdgeKind.MATERIAL, EdgeState.ACTIVE, True, subject)
            for name in component_names[:-1]
        ),
        PCUGEdge("subject", "model", EdgeKind.INFLUENCE, EdgeState.ACTIVE, True, subject),
    )
    graph = PCUGGraph(nodes, edges, (unknown_channel("model_weight_equivalence", threshold=1e-8),))
    protocol = CDCProtocol(
        "calibrated-plan",
        subject,
        frozenset({"subject"}),
        frozenset(component_names[:-1]),
        frozenset({"model_weight_equivalence"}),
    )
    actions: list[CDCAction] = []
    for name in component_names[:-1]:
        actions.append(
            CDCAction(
                f"target-{name}",
                costs[name],
                (Transition(name, EdgeState.CLOSED, f"measured-{name}", TransitionTarget.NODE),),
            )
        )
    model_edge = next(edge.id for edge in edges if edge.target_id == "model")
    actions.append(
        CDCAction(
            "target-model",
            costs["model"],
            (Transition(model_edge, EdgeState.CLOSED, "exact-ridge-reference"),),
            result_channels=(
                upper_bound_channel(
                    "model_weight_equivalence", value=0, upper_bound=0, threshold=1e-8
                ),
            ),
        )
    )
    actions.append(
        CDCAction(
            "rebuild-all",
            rebuild_cost,
            (
                *(
                    Transition(name, EdgeState.CLOSED, "measured-rebuild", TransitionTarget.NODE)
                    for name in component_names[:-1]
                ),
                Transition(model_edge, EdgeState.CLOSED, "exact-ridge-reference"),
            ),
            result_channels=(
                upper_bound_channel(
                    "model_weight_equivalence", value=0, upper_bound=0, threshold=1e-8
                ),
            ),
        )
    )
    plan = exact_cdc(graph, protocol, tuple(actions))
    return {
        "action_cost_microseconds": {**costs, "rebuild_all": rebuild_cost},
        "selected_actions": list(plan.action_ids),
        "selected_cost_microseconds": plan.total_cost,
        "solver_status": plan.solver_status.value,
        "verdict": plan.verdict.value,
    }


def run_trial(
    services: Services, root: Path, seed: int, subjects: int, dimension: int
) -> list[dict[str, Any]]:
    features, labels = vectors(seed, subjects, dimension)
    target = seed % subjects
    load_source(services, features, labels)
    trial_root = root / f"trial-{seed}"
    trial_root.mkdir()
    prefixes = {
        "targeted_exact_cdc": f"targeted-{seed}",
        "rebuild_all": f"rebuild-{seed}",
    }
    roots = {strategy: trial_root / strategy for strategy in prefixes}
    for strategy in prefixes:
        roots[strategy].mkdir()
        setup_derivatives(services, roots[strategy], prefixes[strategy], features, labels)
    command(services.psql_args(f"DELETE FROM subjects WHERE id={target}"))
    retained_features, retained_labels, retained_ids = retained_source(services)
    exact_weights = model_state(retained_features, retained_labels)["weights"]
    records: list[dict[str, Any]] = []
    order = list(prefixes) if seed % 2 else list(reversed(prefixes))
    for strategy in order:
        if strategy == "targeted_exact_cdc":
            seconds, written, components = targeted_remediation(
                services,
                roots[strategy],
                prefixes[strategy],
                target,
                features[target],
                float(labels[target]),
            )
        else:
            seconds, written, components = rebuild_remediation(
                services,
                roots[strategy],
                prefixes[strategy],
                subjects,
                retained_features,
                retained_labels,
                retained_ids,
            )
        verdict, retained, delta = audit_strategy(
            services,
            roots[strategy],
            prefixes[strategy],
            target,
            retained_ids,
            exact_weights,
        )
        measurement = StrategyMeasurement(
            seed,
            strategy,
            seconds,
            written,
            verdict,
            retained,
            subjects - 1,
            delta,
        )
        records.append({**asdict(measurement), "components": components, "target": target})
    for prefix in prefixes.values():
        http_json("DELETE", f"http://127.0.0.1:{services.qdrant_port}/collections/{prefix}")
        redis_pipe(
            services,
            [(b"DEL", f"{prefix}:{subject_id}".encode()) for subject_id in range(subjects)],
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the preregistered real-process systems study")
    parser.add_argument("--protocol", default="benchmark/measured-multiservice-v1.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--calibration-only", action="store_true")
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    image = str(protocol["qdrant_image"])
    subjects = int(protocol["subject_count"])
    dimension = int(protocol["vector_dimension"])
    with tempfile.TemporaryDirectory(prefix="erasemap-multiservice-") as temporary:
        with Services(Path(temporary), image) as services:
            calibration = [
                record
                for seed in protocol["calibration_seeds"]
                for record in run_trial(services, Path(temporary), int(seed), subjects, dimension)
            ]
            planner = planner_from_calibration(calibration)
            if args.calibration_only:
                result = {
                    "calibration_records": calibration,
                    "claim_boundary": "Calibration only; no confirmatory claim.",
                    "planner": planner,
                    "protocol_commitment": sha256_file(protocol_path),
                    "schema_version": "erasemap-measured-multiservice-calibration-v1",
                }
                (output / "calibration.json").write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n"
                )
                print(json.dumps({"calibration": "PASS", "planner": planner}, sort_keys=True))
                return 0
            holdout = [
                record
                for seed in protocol["holdout_seeds"]
                for record in run_trial(services, Path(temporary), int(seed), subjects, dimension)
            ]
    measurements = [
        StrategyMeasurement(
            int(item["seed"]),
            str(item["strategy"]),
            float(item["seconds"]),
            int(item["bytes_rewritten"]),
            str(item["verdict"]),
            int(item["retained_count"]),
            int(item["expected_retained_count"]),
            float(item["model_weight_delta"]),
        )
        for item in holdout
    ]
    summary = paired_summary(
        measurements,
        bootstrap_seed=int(protocol["bootstrap_seed"]),
        bootstrap_samples=int(protocol["bootstrap_samples"]),
    )
    gates = protocol["gates"]
    gate_results = {
        "bytes_reduction": float(summary["bytes_reduction"])
        >= float(gates["minimum_bytes_reduction"]),
        "complete_rate": float(summary["complete_rate"]) >= float(gates["complete_rate"]),
        "model_weight_delta": float(summary["maximum_model_weight_delta"])
        <= float(gates["maximum_model_weight_delta"]),
        "retained_data_loss": float(summary["maximum_retained_data_loss_rate"])
        <= float(gates["maximum_retained_data_loss_rate"]),
        "speedup_ci95_lower": float(summary["paired_speedup"]["bootstrap_ci95"][0])
        >= float(gates["minimum_speedup_ci95_lower"]),
    }
    result = {
        "calibration_records": calibration,
        "claim_boundary": protocol["claim_boundary"],
        "decision": "PASS" if all(gate_results.values()) else "FAIL",
        "gate_results": gate_results,
        "holdout_records": holdout,
        "planner": planner,
        "protocol_commitment": sha256_file(protocol_path),
        "schema_version": "erasemap-measured-multiservice-result-v1",
        "services": {
            "postgres": "15.18",
            "qdrant": image,
            "redis": "8.8.0",
        },
        "summary": summary,
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"], "summary": summary}, sort_keys=True))
    return 0 if result["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
