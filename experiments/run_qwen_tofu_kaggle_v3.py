from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar, cast

from experiments.qwen_tofu_v3_data import compute_selection_commitment

ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class EvidenceJournal:
    """Append-only evidence writer with a digest-linked phase state machine."""

    _STATE_FILES: ClassVar[dict[str, str]] = {
        "INITIAL": "state-00-initial.json",
        "DEVELOPMENT_COMPLETE": "state-01-development-complete.json",
        "SELECTION_COMMITTED": "state-02-selection-committed.json",
        "CONFIRMATION_COMPLETE": "state-03-confirmation-complete.json",
        "SECONDARY_COMPLETE": "state-04-secondary-complete.json",
        "SEALED": "state-05-sealed.json",
    }

    def __init__(self, root: Path, *, protocol_path: Path, code_revision: str) -> None:
        if root.exists():
            raise FileExistsError(f"refusing to overwrite evidence directory: {root}")
        if len(code_revision) != 40 or any(
            value not in "0123456789abcdef" for value in code_revision
        ):
            raise ValueError("code revision must be a full lowercase git SHA-1")
        protocol = json.loads(protocol_path.read_text())
        if not isinstance(protocol, dict) or protocol.get("status") != (
            "FROZEN_BEFORE_FIRST_V3_GPU_RUN"
        ):
            raise ValueError("v3 protocol must be frozen")
        self.root = root
        self.protocol_path = protocol_path
        self.protocol = cast(Mapping[str, object], protocol)
        self.protocol_sha256 = _sha256(protocol_path)
        self.code_revision = code_revision
        self.state = "INITIAL"
        self._last_state: Path | None = None
        root.mkdir(parents=True, exist_ok=False)
        self._transition(
            "INITIAL",
            {
                "code_revision": code_revision,
                "protocol_sha256": self.protocol_sha256,
                "scientific_inputs_frozen": True,
            },
            expected=None,
        )

    def _write_once(self, name: str, value: object, *, jsonl: bool = False) -> Path:
        path = self.root / name
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence file: {path}")
        if jsonl:
            rows = cast(Sequence[Mapping[str, object]], value)
            path.write_bytes(b"".join(_canonical(row) + b"\n" for row in rows))
        else:
            path.write_bytes(_canonical(value) + b"\n")
        return path

    def _transition(
        self,
        next_state: str,
        payload: Mapping[str, object],
        *,
        expected: str | None,
    ) -> None:
        if expected is not None and self.state != expected:
            raise ValueError(f"invalid state transition: {self.state} -> {next_state}")
        state_file = self._STATE_FILES[next_state]
        value = {
            "payload": dict(payload),
            "previous_state_sha256": (
                _sha256(self._last_state) if self._last_state is not None else None
            ),
            "schema_version": "erasemap-qwen-tofu-v3-state-v1",
            "state": next_state,
        }
        self._last_state = self._write_once(state_file, value)
        self.state = next_state

    def complete_development(self, development: Mapping[str, object]) -> None:
        decision = development.get("decision")
        if decision not in {"CANDIDATE_AVAILABLE", "NO_CANDIDATE", "NON_SCIENTIFIC_SMOKE"}:
            raise ValueError("invalid development decision")
        path = self._write_once("development.json", development)
        self._transition(
            "DEVELOPMENT_COMPLETE",
            {"decision": decision, "development_sha256": _sha256(path)},
            expected="INITIAL",
        )

    def commit_selection(self, selection: Mapping[str, object]) -> Mapping[str, object]:
        if self.state != "DEVELOPMENT_COMPLETE":
            raise ValueError("development must complete before selection")
        development = json.loads((self.root / "development.json").read_text())
        if development.get("decision") != "CANDIDATE_AVAILABLE":
            raise ValueError("selection commitment requires an available candidate")
        value = dict(selection)
        value["protocol_sha256"] = self.protocol_sha256
        value["code_revision"] = self.code_revision
        value["selection_commitment"] = compute_selection_commitment(value)
        path = self._write_once("selection.json", value)
        self._transition(
            "SELECTION_COMMITTED",
            {
                "selection_commitment": value["selection_commitment"],
                "selection_sha256": _sha256(path),
            },
            expected="DEVELOPMENT_COMPLETE",
        )
        return value

    def begin_confirmation(self) -> Mapping[str, object]:
        selection_path = self.root / "selection.json"
        if self.state != "SELECTION_COMMITTED" or not selection_path.is_file():
            raise ValueError("selection commitment is required before confirmation")
        value = json.loads(selection_path.read_text())
        if not isinstance(value, dict) or value.get("selection_commitment") != (
            compute_selection_commitment(value)
        ):
            raise ValueError("selection commitment is invalid")
        return cast(Mapping[str, object], value)

    def complete_confirmation(
        self,
        trials: Sequence[Mapping[str, object]],
        baseline_trials: Sequence[Mapping[str, object]],
    ) -> None:
        self.begin_confirmation()
        trial_path = self._write_once("trials.jsonl", trials, jsonl=True)
        baseline_path = self._write_once(
            "baseline_trials.jsonl", baseline_trials, jsonl=True
        )
        self._transition(
            "CONFIRMATION_COMPLETE",
            {
                "baseline_trials_sha256": _sha256(baseline_path),
                "trial_count": len(trials),
                "trials_sha256": _sha256(trial_path),
            },
            expected="SELECTION_COMMITTED",
        )

    def complete_secondary(self, trials: Sequence[Mapping[str, object]]) -> None:
        path = self._write_once("secondary_trials.jsonl", trials, jsonl=True)
        self._transition(
            "SECONDARY_COMPLETE",
            {"secondary_trial_count": len(trials), "secondary_trials_sha256": _sha256(path)},
            expected="CONFIRMATION_COMPLETE",
        )

    def _seal(self, summary: Mapping[str, object], *, expected: str) -> dict[str, object]:
        value = {
            **summary,
            "code_revision": self.code_revision,
            "protocol_sha256": self.protocol_sha256,
            "schema_version": "erasemap-qwen-tofu-kaggle-result-v3",
        }
        summary_path = self._write_once("summary.json", value)
        self._transition(
            "SEALED",
            {"decision": value["decision"], "summary_sha256": _sha256(summary_path)},
            expected=expected,
        )
        manifest_files = sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_file() and path.name != "MANIFEST.sha256.json"
        )
        self._write_once(
            "MANIFEST.sha256.json",
            {
                "files": {name: _sha256(self.root / name) for name in manifest_files},
                "protocol_sha256": self.protocol_sha256,
            },
        )
        return value

    def seal_no_candidate(self) -> dict[str, object]:
        development = json.loads((self.root / "development.json").read_text())
        if development.get("decision") != "NO_CANDIDATE":
            raise ValueError("NO_CANDIDATE seal requires that development outcome")
        return self._seal(
            {
                "decision": "NO_CANDIDATE",
                "scientific": True,
                "confirmation_loaded": False,
            },
            expected="DEVELOPMENT_COMPLETE",
        )

    def seal_smoke(self) -> dict[str, object]:
        development = json.loads((self.root / "development.json").read_text())
        if development.get("decision") != "NON_SCIENTIFIC_SMOKE":
            raise ValueError("smoke seal requires a smoke development outcome")
        return self._seal(
            {
                "decision": "NON_SCIENTIFIC_SMOKE",
                "scientific": False,
                "confirmation_loaded": False,
            },
            expected="DEVELOPMENT_COMPLETE",
        )

    def seal_scientific(self, summary: Mapping[str, object]) -> dict[str, object]:
        if summary.get("decision") not in {"PASS", "FAIL"}:
            raise ValueError("scientific confirmation decision must be PASS or FAIL")
        return self._seal(summary, expected="SECONDARY_COMPLETE")


def run_smoke(
    protocol_path: Path, output: Path, *, code_revision: str
) -> dict[str, object]:
    journal = EvidenceJournal(
        output,
        protocol_path=protocol_path,
        code_revision=code_revision,
    )
    journal.complete_development(
        {
            "decision": "NON_SCIENTIFIC_SMOKE",
            "selection_uses_confirmation": False,
            "trials": [],
        }
    )
    return journal.seal_smoke()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run frozen Qwen-TOFU Kaggle v3")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "benchmark/qwen-tofu-kaggle-v3.json",
    )
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/qwen-tofu-v3"))
    parser.add_argument("--code-revision", default=os.environ.get("ERASEMAP_CODE_REVISION"))
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    revision = args.code_revision or _git_revision()
    if not args.smoke:
        raise RuntimeError(
            "scientific GPU backend is not yet wired; refusing to fabricate v3 evidence"
        )
    result = run_smoke(args.protocol, args.output, code_revision=revision)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
