import json
import subprocess
from pathlib import Path

CLI = Path(".venv/bin/erasemap")


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(CLI), *arguments], capture_output=True, text=True, check=False)


def test_audit_command_emits_machine_readable_status() -> None:
    result = run_cli("audit", "examples/five_branch_system.json", "--subject", "subject-1")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "INCOMPLETE"
    assert payload["shortest_path"] == ["source", "template"]


def test_generate_command_writes_reproducible_graph(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"

    first = run_cli(
        "generate", "--seed", "7", "--nodes", "10", "--fault", "STALE_CACHE", "--output", str(left)
    )
    second = run_cli(
        "generate", "--seed", "7", "--nodes", "10", "--fault", "STALE_CACHE", "--output", str(right)
    )

    assert first.returncode == second.returncode == 0
    assert left.read_bytes() == right.read_bytes()
    assert json.loads(first.stdout)["faults"][0]["kind"] == "STALE_CACHE"


def test_invalid_input_returns_code_two() -> None:
    result = run_cli("generate", "--seed", "-1", "--nodes", "2", "--output", "x")

    assert result.returncode == 2
    assert result.stderr


def test_invalid_receipt_returns_code_three(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}")

    result = run_cli("receipt", "verify", "--public-key", "00" * 32, "--receipt", str(receipt))

    assert result.returncode == 3
