from pathlib import Path

from scripts.verify_ci_environment import verify


def test_environment_verifier_reports_missing_and_mismatched_packages(
    tmp_path: Path,
) -> None:
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("pytest==0.0.0\ndefinitely-missing-package==1.0.0\n")

    mismatches = verify(constraints)

    assert any(item.startswith("pytest==") for item in mismatches)
    assert "definitely-missing-package missing; expected 1.0.0" in mismatches
