from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.run_qwen_tofu_kaggle_v3 import run_smoke
from scripts.verify_qwen_tofu_kaggle_v3 import verify_protocol, verify_result

PROTOCOL = Path("benchmark/qwen-tofu-kaggle-v3.json")


def test_protocol_only_verifies_frozen_invariants() -> None:
    result = verify_protocol(PROTOCOL)
    assert result["status"] == "PROTOCOL_VALID"
    assert result["author_block_count"] == 20
    assert result["primary_gate_count"] == 12


def test_smoke_requires_explicit_allow_and_never_returns_pass(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    run_smoke(PROTOCOL, output, code_revision="a" * 40)
    with pytest.raises(ValueError, match="smoke"):
        verify_result(output, protocol_path=PROTOCOL)
    result = verify_result(output, protocol_path=PROTOCOL, allow_smoke=True)
    assert result["decision"] == "NON_SCIENTIFIC_SMOKE"
    assert result["scientific"] is False


def test_manifest_tamper_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    run_smoke(PROTOCOL, output, code_revision="a" * 40)
    development = json.loads((output / "development.json").read_text())
    development["trials"] = [{"fabricated": True}]
    (output / "development.json").write_text(json.dumps(development) + "\n")
    with pytest.raises(ValueError, match="manifest"):
        verify_result(output, protocol_path=PROTOCOL, allow_smoke=True)


def test_state_chain_tamper_is_rejected_even_with_updated_manifest(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    run_smoke(PROTOCOL, output, code_revision="a" * 40)
    state_path = output / "state-01-development-complete.json"
    state = json.loads(state_path.read_text())
    state["previous_state_sha256"] = "sha256:" + "0" * 64
    state_path.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n")
    manifest_path = output / "MANIFEST.sha256.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][state_path.name] = "sha256:" + hashlib.sha256(
        state_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(ValueError, match="state chain"):
        verify_result(output, protocol_path=PROTOCOL, allow_smoke=True)
