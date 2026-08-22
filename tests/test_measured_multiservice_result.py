from __future__ import annotations

from scripts.verify_measured_multiservice_v1 import verify


def test_frozen_measured_multiservice_result_verifies() -> None:
    result = verify()
    assert result["decision"] == "PASS"
    assert result["holdout_pairs"] == 20
