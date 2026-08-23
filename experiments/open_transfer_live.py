from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any, cast

import numpy as np

from erasemap.open_transfer import (
    ControlCandidate,
    PhysicalOutcome,
    TransferCaseRecord,
    decide_physical_outcome,
    expected_case_id,
)
from erasemap.open_transfer_evidence import (
    EvidenceLedger,
    canonical_json,
    sha256_bytes,
)
from experiments.open_transfer_adapters import (
    AdapterCaseResult,
    KeycloakIdentityAdapter,
    MLflowLineageAdapter,
    QdrantBiometricAdapter,
)
from experiments.open_transfer_services import (
    DockerService,
    EvidenceHttpClient,
    require_transfer_container_name,
    run_command,
    wait_for_http,
)

CONTROLS = (
    ControlCandidate("block-recovery", 3, frozenset({"recovery"})),
    ControlCandidate("delete-primary", 1, frozenset({"primary"})),
    ControlCandidate("erase-derivative", 3, frozenset({"derivative"})),
    ControlCandidate(
        "persistent-tombstone", 7, frozenset({"primary", "derivative", "recovery"})
    ),
)


def _family(protocol: dict[str, Any], family_id: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        next(item for item in protocol["families"] if item["id"] == family_id),
    )


def _ledger_slice_hash(ledger: EvidenceLedger, start: int) -> str:
    records = ledger.records()[start:]
    return sha256_bytes(b"".join(canonical_json(item) + b"\n" for item in records))


def _record(
    *,
    protocol: dict[str, Any],
    family_id: str,
    seed: int,
    fault_state: str,
    core_hash: str,
    result: AdapterCaseResult,
) -> TransferCaseRecord:
    decision = decide_physical_outcome(result.physical, CONTROLS)
    family = _family(protocol, family_id)
    return TransferCaseRecord(
        case_id=expected_case_id(family_id, seed, fault_state),
        family=family_id,
        seed=seed,
        fault_state=fault_state,
        truth=str(protocol["truth_by_fault_state"][fault_state]),
        native_complete=decision.native_complete,
        typed_complete=decision.typed_complete,
        erasemap_verdict=decision.erasemap_verdict,
        shortest_witness=decision.shortest_witness,
        selected_control_ids=decision.selected_control_ids,
        selected_cost=decision.selected_cost,
        oracle_control_ids=decision.oracle_control_ids,
        oracle_cost=decision.oracle_cost,
        post_control_recurrence=result.post_control_recurrence,
        retained_loss=decision.retained_loss,
        core_sha256=core_hash,
        service_image=str(family["image"]),
        service_version=str(family["version"]),
        evidence_sha256=result.evidence_sha256,
        process_observed=True,
        remediation_milliseconds=result.remediation_milliseconds,
        bytes_rewritten=result.bytes_rewritten,
    )


def _load_vectors(
    asset_path: Path, split: str
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    if split not in {"development", "confirmatory"}:
        raise ValueError("unknown transfer asset split")
    with np.load(asset_path, allow_pickle=False) as payload:
        vectors = np.asarray(payload[f"{split}_vectors"], dtype=np.float32)
        subjects = np.asarray(payload[f"{split}_subject_ids"], dtype=np.int64)
    if vectors.shape != (5, 4096) or subjects.shape != (5,):
        raise ValueError("transfer vector asset shape drift")
    return vectors, subjects


def run_qdrant_family(
    protocol: dict[str, Any],
    *,
    core_hash: str,
    asset_path: Path,
    evidence_path: Path,
    service_root: Path,
    smoke: bool,
) -> tuple[TransferCaseRecord, ...]:
    family_id = "qdrant-biometric"
    family = _family(protocol, family_id)
    vectors, _ = _load_vectors(asset_path, "development" if smoke else "confirmatory")
    storage = service_root / "storage"
    snapshots = service_root / "snapshots"
    storage.mkdir(parents=True)
    snapshots.mkdir(parents=True)
    ledger = EvidenceLedger(evidence_path)
    service = DockerService(
        family="qdrant",
        image=str(family["image"]),
        internal_port=6333,
        root=service_root,
    )
    service.inspect_digest()
    service.start(
        env={},
        mounts=(
            (storage, "/qdrant/storage", False),
            (snapshots, "/qdrant/snapshots", False),
        ),
        args=(),
    )
    try:
        client = EvidenceHttpClient(ledger)
        wait_for_http(client, f"{service.base_url}/collections", timeout=90)
        adapter = QdrantBiometricAdapter(client)
        seeds = tuple(protocol["seeds"][:1] if smoke else protocol["seeds"])
        faults = (
            ("recovery_regeneration",) if smoke else tuple(protocol["fault_states"])
        )
        records = []
        for seed_index, seed in enumerate(seeds):
            for fault in faults:
                outcome = adapter.run_case(
                    base_url=service.base_url,
                    seed=int(seed),
                    fault_state=str(fault),
                    vector=vectors[seed_index],
                )
                records.append(
                    _record(
                        protocol=protocol,
                        family_id=family_id,
                        seed=int(seed),
                        fault_state=str(fault),
                        core_hash=core_hash,
                        result=outcome,
                    )
                )
        return tuple(records)
    finally:
        service.stop()


def _one_shot_container(
    *,
    name: str,
    image: str,
    root: Path,
    mounts: tuple[tuple[Path, str, bool], ...],
    args: tuple[str, ...],
    env: dict[str, str] | None = None,
) -> None:
    safe_name = require_transfer_container_name(name)
    command = ["docker", "run", "--rm", "--name", safe_name]
    for key, value in sorted((env or {}).items()):
        command.extend(("-e", f"{key}={value}"))
    for source, target, read_only in mounts:
        resolved = source.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError("one-shot mount must stay inside the case root")
        suffix = ":ro" if read_only else ""
        command.extend(("-v", f"{resolved}:{target}{suffix}"))
    command.extend((image, *args))
    run_command(command, check=True)


def _start_keycloak(
    *,
    image: str,
    root: Path,
    data: Path,
    ledger: EvidenceLedger,
    password: str,
    nonce: str,
) -> tuple[DockerService, EvidenceHttpClient, KeycloakIdentityAdapter, str]:
    data.mkdir(parents=True, exist_ok=True)
    service = DockerService(
        family="keycloak",
        image=image,
        internal_port=8080,
        root=root,
        nonce=nonce,
    )
    service.inspect_digest()
    service.start(
        env={
            "KC_BOOTSTRAP_ADMIN_USERNAME": "admin",
            "KC_BOOTSTRAP_ADMIN_PASSWORD": password,
        },
        mounts=((data, "/opt/keycloak/data", False),),
        args=("start-dev",),
    )
    client = EvidenceHttpClient(ledger, secret_values=(password,))
    wait_for_http(client, f"{service.base_url}/realms/master", timeout=120)
    adapter = KeycloakIdentityAdapter(client, service.base_url)
    token = adapter.admin_token("admin", password)
    return service, client, adapter, token


def _keycloak_case(
    protocol: dict[str, Any],
    *,
    core_hash: str,
    ledger: EvidenceLedger,
    service_root: Path,
    seed: int,
    fault_state: str,
) -> TransferCaseRecord:
    family_id = "keycloak-identity"
    image = str(_family(protocol, family_id)["image"])
    case_root = service_root / f"{seed}-{fault_state}"
    source_data = case_root / "source-data"
    export_root = case_root / "export"
    restore_data = case_root / "restore-data"
    export_root.mkdir(parents=True)
    password = secrets.token_urlsafe(24)
    realm = f"transfer-{seed}-{fault_state.replace('_', '-')}"
    username = f"subject-{seed}"
    retained_username = f"retained-{seed}"
    evidence_start = len(ledger.records())
    source_service, _, source_adapter, token = _start_keycloak(
        image=image,
        root=case_root,
        data=source_data,
        ledger=ledger,
        password=password,
        nonce=f"source-{seed}-{fault_state.replace('_', '-')}",
    )
    restore_service: DockerService | None = None
    try:
        source_adapter.create_realm(token, realm)
        target_id = source_adapter.create_user(token, realm, username)
        source_adapter.create_user(token, realm, retained_username)
        retained_before = int(bool(source_adapter.search_users(token, realm, retained_username)))
        has_export = fault_state in {
            "surviving_derivative",
            "recovery_regeneration",
            "coverage_fault",
        }
        if has_export:
            source_service.stop()
            _one_shot_container(
                name=require_transfer_container_name(
                    f"erasemap-transfer-keycloak-export-{os.getpid()}-{seed}"
                ),
                image=image,
                root=case_root,
                mounts=(
                    (source_data, "/opt/keycloak/data", False),
                    (export_root, "/opt/keycloak/export", False),
                ),
                args=("export", "--dir", "/opt/keycloak/export", "--realm", realm),
            )
            source_service, _, source_adapter, token = _start_keycloak(
                image=image,
                root=case_root,
                data=source_data,
                ledger=ledger,
                password=password,
                nonce=f"resume-{seed}-{fault_state.replace('_', '-')}",
            )
            users = source_adapter.search_users(token, realm, username)
            if len(users) != 1:
                raise ValueError("Keycloak source user disappeared during export")
            target_id = str(users[0]["id"])
        native_started = time.perf_counter()
        source_adapter.delete_user(token, realm, target_id)
        primary_absent = not source_adapter.search_users(token, realm, username)
        if fault_state == "coverage_fault":
            physical = PhysicalOutcome(
                primary_absent, None, None, False, retained_before, retained_before
            )
            post_control_recurrence = False
        else:
            derivative_present = (
                source_adapter.export_contains_username(export_root, username)
                if has_export
                else False
            )
            recurrence = False
            active_adapter = source_adapter
            active_token = token
            if fault_state == "recovery_regeneration":
                source_service.stop()
                restore_data.mkdir()
                _one_shot_container(
                    name=require_transfer_container_name(
                        f"erasemap-transfer-keycloak-import-{os.getpid()}-{seed}"
                    ),
                    image=image,
                    root=case_root,
                    mounts=(
                        (restore_data, "/opt/keycloak/data", False),
                        (export_root, "/opt/keycloak/import", True),
                    ),
                    args=("import", "--dir", "/opt/keycloak/import", "--override", "true"),
                )
                _one_shot_container(
                    name=require_transfer_container_name(
                        f"erasemap-transfer-keycloak-bootstrap-{os.getpid()}-{seed}"
                    ),
                    image=image,
                    root=case_root,
                    mounts=((restore_data, "/opt/keycloak/data", False),),
                    env={"KC_BOOTSTRAP_ADMIN_PASSWORD": password},
                    args=(
                        "bootstrap-admin",
                        "user",
                        "--no-prompt",
                        "--username",
                        "admin",
                        "--password:env",
                        "KC_BOOTSTRAP_ADMIN_PASSWORD",
                    ),
                )
                restore_service, _, active_adapter, active_token = _start_keycloak(
                    image=image,
                    root=case_root,
                    data=restore_data,
                    ledger=ledger,
                    password=password,
                    nonce=f"restore-{seed}",
                )
                recurrence = bool(active_adapter.search_users(active_token, realm, username))
            retained_after = int(
                bool(active_adapter.search_users(active_token, realm, retained_username))
            )
            physical = PhysicalOutcome(
                primary_absent,
                derivative_present,
                recurrence,
                True,
                retained_before,
                retained_after,
            )
            if recurrence:
                restored_users = active_adapter.search_users(active_token, realm, username)
                if restored_users:
                    active_adapter.delete_user(
                        active_token, realm, str(restored_users[0]["id"])
                    )
            bytes_rewritten = sum(
                path.stat().st_size for path in export_root.glob("*") if path.is_file()
            )
            if derivative_present or recurrence:
                for path in export_root.glob("*.json"):
                    path.unlink()
            post_control_recurrence = bool(
                active_adapter.search_users(active_token, realm, username)
            )
        if fault_state == "coverage_fault":
            bytes_rewritten = sum(
                path.stat().st_size for path in export_root.glob("*") if path.is_file()
            )
        evidence_hash = _ledger_slice_hash(ledger, evidence_start)
        result = AdapterCaseResult(
            physical=physical,
            post_control_recurrence=post_control_recurrence,
            evidence_sha256=evidence_hash,
            remediation_milliseconds=(time.perf_counter() - native_started) * 1000.0,
            bytes_rewritten=bytes_rewritten,
        )
        return _record(
            protocol=protocol,
            family_id=family_id,
            seed=seed,
            fault_state=fault_state,
            core_hash=core_hash,
            result=result,
        )
    finally:
        if restore_service is not None:
            restore_service.stop()
        source_service.stop()


def run_keycloak_family(
    protocol: dict[str, Any],
    *,
    core_hash: str,
    evidence_path: Path,
    service_root: Path,
    smoke: bool,
) -> tuple[TransferCaseRecord, ...]:
    ledger = EvidenceLedger(evidence_path)
    seeds = tuple(protocol["seeds"][:1] if smoke else protocol["seeds"])
    faults = ("recovery_regeneration",) if smoke else tuple(protocol["fault_states"])
    return tuple(
        _keycloak_case(
            protocol,
            core_hash=core_hash,
            ledger=ledger,
            service_root=service_root,
            seed=int(seed),
            fault_state=str(fault),
        )
        for seed in seeds
        for fault in faults
    )


def _mlflow_log_artifact(
    service: DockerService, run_id: str, content: str, artifact_name: str
) -> None:
    script = (
        "import mlflow,sys;"
        "mlflow.set_tracking_uri('http://127.0.0.1:5000');"
        "mlflow.log_text(sys.argv[2],sys.argv[3],run_id=sys.argv[1])"
    )
    run_command(
        [
            "docker",
            "exec",
            require_transfer_container_name(service.container_name),
            "python",
            "-c",
            script,
            run_id,
            content,
            artifact_name,
        ],
        check=True,
    )


def _mlflow_gc(service: DockerService, run_id: str) -> None:
    run_command(
        [
            "docker",
            "exec",
            require_transfer_container_name(service.container_name),
            "mlflow",
            "gc",
            "--backend-store-uri",
            "sqlite:////mlflow/db/mlflow.db",
            "--run-ids",
            run_id,
        ],
        check=True,
    )


def run_mlflow_family(
    protocol: dict[str, Any],
    *,
    core_hash: str,
    evidence_path: Path,
    service_root: Path,
    smoke: bool,
) -> tuple[TransferCaseRecord, ...]:
    family_id = "mlflow-lineage"
    family = _family(protocol, family_id)
    database = service_root / "db"
    artifacts = service_root / "artifacts"
    database.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    ledger = EvidenceLedger(evidence_path)
    service = DockerService(
        family="mlflow",
        image=str(family["image"]),
        internal_port=5000,
        root=service_root,
    )
    service.inspect_digest()
    service.start(
        env={},
        mounts=(
            (database, "/mlflow/db", False),
            (artifacts, "/mlflow/artifacts", False),
        ),
        args=(
            "mlflow",
            "server",
            "--host",
            "0.0.0.0",
            "--port",
            "5000",
            "--backend-store-uri",
            "sqlite:////mlflow/db/mlflow.db",
            "--default-artifact-root",
            "file:///mlflow/artifacts",
            "--allowed-hosts",
            "*",
        ),
    )
    try:
        client = EvidenceHttpClient(ledger)
        wait_for_http(client, f"{service.base_url}/health", timeout=120)
        adapter = MLflowLineageAdapter(client, service.base_url)
        seeds = tuple(protocol["seeds"][:1] if smoke else protocol["seeds"])
        faults = ("recovery_regeneration",) if smoke else tuple(protocol["fault_states"])
        records = []
        for seed in seeds:
            for fault in faults:
                evidence_start = len(ledger.records())
                commitment = sha256_bytes(f"mlflow-subject-{seed}".encode())
                experiment_id = adapter.create_experiment(
                    f"open-transfer-{seed}-{fault}", "file:///mlflow/artifacts"
                )
                run_id = adapter.create_run(experiment_id, commitment)
                artifact_content = (
                    "public-control-artifact"
                    if fault == "safe_native"
                    else canonical_json({"subject_commitment": commitment}).decode()
                )
                _mlflow_log_artifact(
                    service, run_id, artifact_content, "subject-record.json"
                )
                retained_before = 1
                native_started = time.perf_counter()
                adapter.delete_run(run_id)
                deleted_run = adapter.get_run(run_id)
                run_payload = deleted_run.get("run")
                info = run_payload.get("info") if isinstance(run_payload, dict) else None
                primary_absent = (
                    isinstance(info, dict) and info.get("lifecycle_stage") == "deleted"
                )
                if fault == "coverage_fault":
                    physical = PhysicalOutcome(
                        primary_absent, None, None, False, retained_before, retained_before
                    )
                    post_control_recurrence = False
                else:
                    derivative_present = adapter.artifact_contains_subject(
                        artifacts, commitment
                    )
                    if derivative_present is None:
                        raise RuntimeError("MLflow artifact root became unavailable")
                    recurrence = False
                    if fault == "recovery_regeneration":
                        adapter.restore_run(run_id)
                        restored = adapter.get_run(run_id)
                        restored_run = restored.get("run")
                        restored_info = (
                            restored_run.get("info")
                            if isinstance(restored_run, dict)
                            else None
                        )
                        recurrence = (
                            isinstance(restored_info, dict)
                            and restored_info.get("lifecycle_stage") == "active"
                        )
                    physical = PhysicalOutcome(
                        primary_absent,
                        derivative_present,
                        recurrence,
                        True,
                        retained_before,
                        retained_before,
                    )
                    if recurrence:
                        adapter.delete_run(run_id)
                    if derivative_present or recurrence:
                        _mlflow_gc(service, run_id)
                    post_control_recurrence = (
                        adapter.artifact_contains_subject(artifacts, commitment) is True
                    )
                result = AdapterCaseResult(
                    physical=physical,
                    post_control_recurrence=post_control_recurrence,
                    evidence_sha256=_ledger_slice_hash(ledger, evidence_start),
                    remediation_milliseconds=(time.perf_counter() - native_started) * 1000.0,
                    bytes_rewritten=len(artifact_content.encode()),
                )
                records.append(
                    _record(
                        protocol=protocol,
                        family_id=family_id,
                        seed=int(seed),
                        fault_state=str(fault),
                        core_hash=core_hash,
                        result=result,
                    )
                )
        return tuple(records)
    finally:
        service.stop()


def run_live_families(
    protocol: dict[str, Any],
    *,
    core_hash: str,
    asset_path: Path,
    evidence_root: Path,
    service_root: Path,
    smoke: bool,
) -> tuple[TransferCaseRecord, ...]:
    evidence_root.mkdir(parents=True, exist_ok=True)
    service_root.mkdir(parents=True, exist_ok=True)
    keycloak = run_keycloak_family(
        protocol,
        core_hash=core_hash,
        evidence_path=evidence_root / "keycloak-identity.jsonl",
        service_root=service_root / "keycloak",
        smoke=smoke,
    )
    mlflow = run_mlflow_family(
        protocol,
        core_hash=core_hash,
        evidence_path=evidence_root / "mlflow-lineage.jsonl",
        service_root=service_root / "mlflow",
        smoke=smoke,
    )
    qdrant = run_qdrant_family(
        protocol,
        core_hash=core_hash,
        asset_path=asset_path,
        evidence_path=evidence_root / "qdrant-biometric.jsonl",
        service_root=service_root / "qdrant",
        smoke=smoke,
    )
    return (*keycloak, *mlflow, *qdrant)
