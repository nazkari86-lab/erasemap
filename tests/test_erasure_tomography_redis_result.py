from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_redis_runner_and_verifier_keep_live_scope_explicit() -> None:
    runner = (ROOT / "experiments/run_erasure_tomography_redis_v1.py").read_text()
    verifier = (ROOT / "scripts/verify_erasure_tomography_redis_v1.py").read_text()
    protocol = (ROOT / "benchmark/erasure-tomography-redis-v1.json").read_text()

    assert "inspect_digest" in runner
    assert "PROJECT_AUTHORED_LIVE_DIGEST_PINNED_REDIS_TRANSFER" in protocol
    assert "PREREGISTRATION_COMMIT" in runner
    assert "PREREGISTRATION_COMMIT" in verifier
    assert "oracle_decode" in verifier
