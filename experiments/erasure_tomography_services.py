from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyReport,
    TomographyVerdict,
    decode,
)
from erasemap.erasure_tomography_oracle import oracle_decode
from experiments.open_transfer_services import (
    require_transfer_container_name,
    run_command,
)

CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]


@dataclass(frozen=True, slots=True)
class RedisTomographyTrial:
    case_id: str
    seed: int
    active_ids: tuple[str, ...]
    observations: tuple[bool, ...]
    verdict: str
    support: tuple[str, ...]
    admissible_supports: tuple[tuple[str, ...], ...]
    distance: int | None
    oracle_match: bool
    post_control_recurrence: bool
    retained_subject_loss: bool
    evidence_sha256: str

    def payload(self) -> dict[str, object]:
        return asdict(self)


class RedisTomographyAdapter:
    def __init__(
        self,
        container_name: str,
        *,
        command_runner: CommandRunner = run_command,
    ) -> None:
        self.container_name = require_transfer_container_name(container_name)
        self.command_runner = command_runner
        self._evidence: list[dict[str, object]] = []

    def _redis(self, *args: str) -> str:
        if any(not item or "\n" in item or "\r" in item for item in args):
            raise ValueError("unsafe Redis command argument")
        result = self.command_runner(
            ["docker", "exec", self.container_name, "redis-cli", "--raw", *args],
            check=True,
        )
        output = result.stdout.decode(errors="strict").strip()
        self._evidence.append(
            {
                "sequence": len(self._evidence),
                "operation": args[0],
                "argument_count": len(args) - 1,
                "output_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "returncode": result.returncode,
            }
        )
        return output

    def ping(self) -> bool:
        return self._redis("PING") == "PONG"

    @staticmethod
    def _key(mechanism_id: str, subject: str) -> str:
        return f"erasemap:et:{mechanism_id}:{subject}"

    @staticmethod
    def _hash(mechanism_id: str) -> str:
        return f"erasemap:et:{mechanism_id}"

    def seed_carrier(self, subject: str, mechanism_id: str) -> None:
        payload = f"synthetic:{subject}"
        if mechanism_id == "backup_restore":
            self._redis("HSET", self._hash(mechanism_id), subject, payload)
        elif mechanism_id == "checkpoint_redeploy":
            self._redis("SET", self._key(mechanism_id, subject), payload)
        elif mechanism_id == "legacy_export_import":
            self._redis("HSET", self._hash(mechanism_id), subject, payload)
        elif mechanism_id == "retry_queue_replay":
            self._redis("RPUSH", self._key(mechanism_id, subject), payload)
        else:
            raise ValueError(f"unknown Redis tomography mechanism: {mechanism_id}")

    def remove_carrier(self, subject: str, mechanism_id: str) -> None:
        if mechanism_id in {"backup_restore", "legacy_export_import"}:
            self._redis("HDEL", self._hash(mechanism_id), subject)
        else:
            self._redis("DEL", self._key(mechanism_id, subject))

    def set_online(self, subject: str) -> None:
        self._redis("SET", f"erasemap:et:online:{subject}", "present")

    def delete_online(self, subject: str) -> None:
        self._redis("DEL", f"erasemap:et:online:{subject}")

    def online(self, subject: str) -> bool:
        return self._redis("EXISTS", f"erasemap:et:online:{subject}") == "1"

    def replay(self, subject: str, mechanism_ids: tuple[str, ...]) -> bool:
        recovered = False
        for mechanism_id in mechanism_ids:
            if mechanism_id in {"backup_restore", "legacy_export_import"}:
                value = self._redis("HGET", self._hash(mechanism_id), subject)
            elif mechanism_id == "checkpoint_redeploy":
                value = self._redis("GET", self._key(mechanism_id, subject))
            elif mechanism_id == "retry_queue_replay":
                value = self._redis("LINDEX", self._key(mechanism_id, subject), "0")
            else:
                raise ValueError(f"unknown Redis tomography mechanism: {mechanism_id}")
            recovered |= bool(value)
        if recovered:
            self.set_online(subject)
        return self.online(subject)

    def cleanup(self, subject: str, mechanism_ids: tuple[str, ...]) -> None:
        self.delete_online(subject)
        for mechanism_id in mechanism_ids:
            self.remove_carrier(subject, mechanism_id)

    def evidence_sha256(self) -> str:
        encoded = json.dumps(
            self._evidence, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


def run_redis_tomography_case(
    adapter: RedisTomographyAdapter,
    design: ProbeDesign,
    *,
    case_id: str,
    seed: int,
    active_ids: tuple[str, ...],
) -> RedisTomographyTrial:
    observations = []
    for probe_index, row in enumerate(design.rows):
        subject = f"subject-{seed}-{probe_index}"
        enabled = tuple(
            mechanism_id
            for mechanism_id, selected in zip(
                design.mechanism_ids, row, strict=True
            )
            if selected and mechanism_id in active_ids
        )
        for mechanism_id in enabled:
            adapter.seed_carrier(subject, mechanism_id)
        adapter.delete_online(subject)
        observations.append(adapter.replay(subject, design.mechanism_ids))
        adapter.cleanup(subject, design.mechanism_ids)

    evidence = TomographyEvidence.complete()
    observation_tuple = tuple(observations)
    report: TomographyReport = decode(design, observation_tuple, evidence)
    oracle = oracle_decode(design, observation_tuple, evidence)
    oracle_match = (
        report.verdict == oracle.verdict
        and report.support == oracle.support
        and report.admissible_supports == oracle.admissible_supports
        and report.distance == oracle.distance
    )
    retained = f"retained-{seed}"
    adapter.set_online(retained)
    retained_before = adapter.online(retained)
    post_control_recurrence = False
    if report.verdict is TomographyVerdict.LOCALIZED:
        validation_subject = f"validation-{seed}"
        for mechanism_id in report.support:
            adapter.seed_carrier(validation_subject, mechanism_id)
        adapter.delete_online(validation_subject)
        for mechanism_id in report.support:
            adapter.remove_carrier(validation_subject, mechanism_id)
        post_control_recurrence = adapter.replay(
            validation_subject, design.mechanism_ids
        )
        adapter.cleanup(validation_subject, design.mechanism_ids)
    retained_after = adapter.online(retained)
    adapter.delete_online(retained)
    return RedisTomographyTrial(
        case_id,
        seed,
        active_ids,
        observation_tuple,
        report.verdict.value,
        report.support,
        report.admissible_supports,
        report.distance,
        oracle_match,
        post_control_recurrence,
        retained_before and not retained_after,
        adapter.evidence_sha256(),
    )
