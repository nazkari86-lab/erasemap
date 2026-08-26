from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.run_qwen_tofu_kaggle_v3 import EvidenceJournal, run_smoke

PROTOCOL = Path("benchmark/qwen-tofu-kaggle-v3.json")


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_journal_refuses_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "result"
    output.mkdir()
    with pytest.raises(FileExistsError):
        EvidenceJournal(output, protocol_path=PROTOCOL, code_revision="a" * 40)


def test_confirmation_requires_committed_selection(tmp_path: Path) -> None:
    journal = EvidenceJournal(
        tmp_path / "result", protocol_path=PROTOCOL, code_revision="a" * 40
    )
    journal.complete_development({"decision": "CANDIDATE_AVAILABLE", "trials": []})
    with pytest.raises(ValueError, match="selection commitment"):
        journal.begin_confirmation()


def test_no_candidate_seals_without_confirmation_state(tmp_path: Path) -> None:
    journal = EvidenceJournal(
        tmp_path / "result", protocol_path=PROTOCOL, code_revision="a" * 40
    )
    journal.complete_development({"decision": "NO_CANDIDATE", "trials": []})
    summary = journal.seal_no_candidate()
    assert summary["decision"] == "NO_CANDIDATE"
    assert not (journal.root / "state-03-confirmation-complete.json").exists()
    assert (journal.root / "MANIFEST.sha256.json").is_file()


def test_state_chain_binds_previous_digest(tmp_path: Path) -> None:
    journal = EvidenceJournal(
        tmp_path / "result", protocol_path=PROTOCOL, code_revision="a" * 40
    )
    initial = journal.root / "state-00-initial.json"
    journal.complete_development({"decision": "CANDIDATE_AVAILABLE", "trials": []})
    state = json.loads((journal.root / "state-01-development-complete.json").read_text())
    assert state["previous_state_sha256"] == _sha256(initial)


def test_smoke_is_explicitly_non_scientific_and_never_passes(tmp_path: Path) -> None:
    result = run_smoke(PROTOCOL, tmp_path / "smoke", code_revision="b" * 40)
    assert result["decision"] == "NON_SCIENTIFIC_SMOKE"
    assert result["scientific"] is False
    assert (tmp_path / "smoke" / "MANIFEST.sha256.json").is_file()
