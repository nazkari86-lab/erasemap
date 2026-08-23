from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from erasemap.erasure_tomography import TomographyVerdict
from erasemap.erasure_tomography_lab import default_probe_design
from experiments.erasure_tomography_services import (
    RedisTomographyAdapter,
    run_redis_tomography_case,
)


class FakeRedis:
    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}

    def __call__(
        self, args: Sequence[str], *, check: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        del check
        command = list(args[5:])
        op = command[0]
        output = ""
        if op == "PING":
            output = "PONG"
        elif op == "SET":
            self.strings[command[1]] = command[2]
            output = "OK"
        elif op == "GET":
            output = self.strings.get(command[1], "")
        elif op == "DEL":
            existed = command[1] in self.strings or command[1] in self.lists
            self.strings.pop(command[1], None)
            self.lists.pop(command[1], None)
            output = str(int(existed))
        elif op == "EXISTS":
            output = str(int(command[1] in self.strings))
        elif op == "HSET":
            self.hashes.setdefault(command[1], {})[command[2]] = command[3]
            output = "1"
        elif op == "HGET":
            output = self.hashes.get(command[1], {}).get(command[2], "")
        elif op == "HDEL":
            existed = command[2] in self.hashes.get(command[1], {})
            self.hashes.get(command[1], {}).pop(command[2], None)
            output = str(int(existed))
        elif op == "RPUSH":
            self.lists.setdefault(command[1], []).append(command[2])
            output = str(len(self.lists[command[1]]))
        elif op == "LINDEX":
            values = self.lists.get(command[1], [])
            output = values[int(command[2])] if values else ""
        else:
            raise AssertionError(f"unexpected fake Redis command: {op}")
        return subprocess.CompletedProcess(list(args), 0, f"{output}\n".encode(), b"")


def test_fake_redis_localizes_every_single_mechanism() -> None:
    design = default_probe_design()
    for index, mechanism_id in enumerate(design.mechanism_ids):
        adapter = RedisTomographyAdapter(
            "erasemap-transfer-et-test", command_runner=FakeRedis()
        )
        trial = run_redis_tomography_case(
            adapter,
            design,
            case_id=f"case-{index}",
            seed=7000 + index,
            active_ids=(mechanism_id,),
        )
        assert trial.verdict == TomographyVerdict.LOCALIZED.value
        assert trial.support == (mechanism_id,)
        assert trial.oracle_match
        assert not trial.post_control_recurrence
        assert not trial.retained_subject_loss


def test_fake_redis_safe_case_observes_no_recurrence() -> None:
    adapter = RedisTomographyAdapter(
        "erasemap-transfer-et-test", command_runner=FakeRedis()
    )
    trial = run_redis_tomography_case(
        adapter,
        default_probe_design(),
        case_id="safe",
        seed=8001,
        active_ids=(),
    )

    assert trial.verdict == TomographyVerdict.NO_OBSERVED_RECURRENCE.value
    assert trial.support == ()


def test_adapter_rejects_non_project_container_name() -> None:
    with pytest.raises(ValueError, match="non-transfer"):
        RedisTomographyAdapter("redis-production", command_runner=FakeRedis())
