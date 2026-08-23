# EraSeMap Open Transfer Challenge v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prospectively evaluate one frozen EraSeMap contract across stock Keycloak, MLflow, and Qdrant service families, then ship a bilingual external usability and transfer handoff without fabricating human or organization evidence.

**Architecture:** A dependency-free core module validates canonical transfer cases, equal-budget baseline outcomes, leave-one-family-out invariants, and conjunctive gates. A separate experiment layer owns Docker lifecycle and documented REST calls for three unmodified services. Offline verifiers, committed hashes, a bilingual usability kit, and existing release/CI gates make results reproducible while keeping live-service dependencies out of the package runtime.

**Tech Stack:** Python 3.11/3.14, dataclasses, JSON/JSONL, urllib, Docker CLI, Keycloak 26.7.1, MLflow 3.x pinned by digest, Qdrant pinned by digest, pytest, Hypothesis, mypy strict, ruff, GitHub Actions.

---

## File structure

- `benchmark/open-transfer-v1.json`: frozen images, case matrix, rotations, gates, sources, and claim boundary.
- `docs/OPEN_TRANSFER_V1_PREREGISTRATION.md`: human-readable frozen hypotheses and analysis.
- `src/erasemap/open_transfer.py`: family-neutral records, validation, metrics, rotation checks, and final decision.
- `src/erasemap/open_transfer_evidence.py`: canonical JSON, credential redaction, hashes, and evidence ledger.
- `experiments/open_transfer_services.py`: isolated Docker lifecycle and raw REST helpers.
- `experiments/open_transfer_adapters.py`: Keycloak, MLflow, and Qdrant stock-service workflows.
- `experiments/prepare_open_transfer_assets.py`: frozen Olivetti selection and deterministic vector asset.
- `experiments/run_open_transfer_v1.py`: protocol loader, live smoke, 60-case confirmatory runner, and provenance writer.
- `scripts/verify_open_transfer_v1.py`: offline committed-result and fresh-result verifier.
- `tests/test_open_transfer.py`: core metrics, gates, rotations, and validation.
- `tests/test_open_transfer_evidence.py`: canonicalization, redaction, hashes, and secrets rejection.
- `tests/test_open_transfer_adapters.py`: frozen response-fixture adapter contracts.
- `tests/test_open_transfer_result.py`: committed result invariants.
- `external_transfer/`: answer-blind run, manifest, attestation, signing, and submission validation.
- `usability/`: bilingual cards, participant schema, sealed gold, scorer, verifier, and empty result handoff.
- `outputs/open-transfer-v1/`: committed first-run result, trial JSONL, and provenance only after a valid live run.
- Existing `README.md`, scorecard, claim matrix, papers, showcase, release script, and CI: bounded integration.

### Task 1: Freeze protocol and preregistration

**Files:**
- Create: `benchmark/open-transfer-v1.json`
- Create: `docs/OPEN_TRANSFER_V1_PREREGISTRATION.md`
- Test: `tests/test_open_transfer_protocol.py`

- [ ] **Step 1: Write protocol tests before the protocol exists**

```python
def test_open_transfer_protocol_is_exact_and_bounded() -> None:
    payload = json.loads(Path("benchmark/open-transfer-v1.json").read_text())
    assert payload["schema_version"] == "erasemap-open-transfer-v1"
    assert [item["id"] for item in payload["families"]] == [
        "keycloak-identity", "mlflow-lineage", "qdrant-biometric"
    ]
    assert payload["seeds"] == [3101, 3109, 3119, 3121, 3137]
    assert payload["fault_states"] == [
        "safe_native", "surviving_derivative", "recovery_regeneration", "coverage_fault"
    ]
    assert 3 * 5 * 4 == payload["gates"]["case_count"] == 60
    assert payload["claim_boundary"]["independent"] is False
```

- [ ] **Step 2: Run the test and confirm the missing-file failure**

Run: `.venv/bin/pytest tests/test_open_transfer_protocol.py -q`
Expected: FAIL with `FileNotFoundError: benchmark/open-transfer-v1.json`.

- [ ] **Step 3: Add the exact machine protocol and preregistration**

The JSON must freeze three families, five seeds, four states, three leave-one-family-out rotations,
container references with `@sha256:` followed by exactly 64 lowercase hexadecimal characters,
official documentation URLs, source hashes, these
primary gates, and the project-authored claim boundary. The preregistration must state that any first
complete failure is retained and that no primary threshold changes under v1.

- [ ] **Step 4: Validate JSON and run the protocol test**

Run: `.venv/bin/python -m json.tool benchmark/open-transfer-v1.json >/dev/null && .venv/bin/pytest tests/test_open_transfer_protocol.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the frozen protocol separately**

```bash
git add benchmark/open-transfer-v1.json docs/OPEN_TRANSFER_V1_PREREGISTRATION.md tests/test_open_transfer_protocol.py
git commit -m "preregister open transfer challenge v1"
```

### Task 2: Implement family-neutral transfer scoring

**Files:**
- Create: `src/erasemap/open_transfer.py`
- Create: `tests/test_open_transfer.py`

- [ ] **Step 1: Write failing tests for valid records and conjunctive gates**

```python
def test_transfer_summary_passes_only_all_frozen_gates() -> None:
    records = frozen_passing_records()
    summary = summarize_transfer(records, protocol_core_sha256="sha256:core")
    assert summary.decision == "PASS"
    assert summary.case_count == 60
    assert summary.erasemap_false_complete_count == 0
    assert summary.post_control_recurrence_count == 0
    assert summary.core_diff_count == 0

def test_one_false_complete_fails_the_entire_result() -> None:
    records = list(frozen_passing_records())
    records[0] = replace(records[0], erasemap_verdict="COMPLETE", truth="REGENERATION")
    assert summarize_transfer(tuple(records), protocol_core_sha256="sha256:core").decision == "FAIL"
```

- [ ] **Step 2: Run the tests and confirm missing imports**

Run: `.venv/bin/pytest tests/test_open_transfer.py -q`
Expected: FAIL because `erasemap.open_transfer` does not exist.

- [ ] **Step 3: Implement immutable types and strict validation**

```python
@dataclass(frozen=True, slots=True)
class TransferCaseRecord:
    case_id: str
    family: str
    seed: int
    fault_state: str
    truth: str
    native_complete: bool
    typed_complete: bool
    erasemap_verdict: str
    shortest_witness: tuple[str, ...] | None
    post_control_recurrence: bool
    retained_loss: bool
    oracle_match: bool
    core_sha256: str
    service_digest: str
    evidence_sha256: str

@dataclass(frozen=True, slots=True)
class TransferSummary:
    decision: str
    case_count: int
    family_count: int
    erasemap_false_complete_count: int
    native_false_complete_by_family: dict[str, int]
    coverage_fail_closed_count: int
    post_control_recurrence_count: int
    retained_loss_count: int
    oracle_mismatch_count: int
    core_diff_count: int
```

Validation must reject duplicate case IDs, missing matrix cells, unknown verdicts/states, malformed
SHA-256 values, non-immutable image references, and a family using multiple core hashes.

- [ ] **Step 4: Implement equal-budget metrics and leave-one-family-out rotation checks**

`summarize_transfer` must derive truth from the frozen state, compute false-complete and safe-case
specificity for all three methods, require core hash equality across rotations, and apply every gate
with logical AND. It must never accept secondary latency or byte metrics as a substitute.

- [ ] **Step 5: Run focused tests and strict typing**

Run: `.venv/bin/pytest tests/test_open_transfer.py -q && .venv/bin/mypy --strict src/erasemap/open_transfer.py`
Expected: PASS.

- [ ] **Step 6: Commit the scoring core**

```bash
git add src/erasemap/open_transfer.py tests/test_open_transfer.py
git commit -m "feat: add frozen open transfer scoring"
```

### Task 3: Add tamper-evident redacted evidence records

**Files:**
- Create: `src/erasemap/open_transfer_evidence.py`
- Create: `tests/test_open_transfer_evidence.py`

- [ ] **Step 1: Write failing secret-redaction and hash tests**

```python
def test_evidence_redacts_credentials_before_hashing() -> None:
    record = canonical_evidence(
        method="POST",
        url="http://127.0.0.1/token",
        request_headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
        request_body={"password": "secret", "user": "subject-1"},
        status=204,
        response_body={},
    )
    encoded = canonical_json(record)
    assert b"secret" not in encoded
    assert b"[REDACTED]" in encoded
    assert sha256_bytes(encoded).startswith("sha256:")
```

- [ ] **Step 2: Run and confirm failure, then implement canonical evidence**

Run: `.venv/bin/pytest tests/test_open_transfer_evidence.py -q`
Expected: FAIL because the module is missing.

Implement recursive case-insensitive redaction for `authorization`, `password`, `secret`, `token`,
`client_secret`, and `cookie`; canonical sorted compact JSON; SHA-256 helpers; append-only JSONL
ledger with duplicate-evidence rejection; and a final scan that rejects raw secret values.

- [ ] **Step 3: Run tests and commit**

Run: `.venv/bin/pytest tests/test_open_transfer_evidence.py -q`
Expected: PASS.

```bash
git add src/erasemap/open_transfer_evidence.py tests/test_open_transfer_evidence.py
git commit -m "feat: add redacted transfer evidence ledger"
```

### Task 4: Build isolated stock-service lifecycle utilities

**Files:**
- Create: `experiments/open_transfer_services.py`
- Create: `tests/test_open_transfer_adapters.py`

- [ ] **Step 1: Write contract tests against frozen HTTP response fixtures**

Tests must cover health polling, JSON and empty responses, HTTP 404 as an observed absence rather
than a runner crash, startup timeout, container-name validation, immutable digest rejection, and
idempotent teardown limited to names beginning with `erasemap-transfer-`.

- [ ] **Step 2: Run the tests and confirm missing implementation**

Run: `.venv/bin/pytest tests/test_open_transfer_adapters.py -q`
Expected: FAIL because `experiments.open_transfer_services` is missing.

- [ ] **Step 3: Implement process utilities**

```python
@dataclass(frozen=True, slots=True)
class HttpObservation:
    status: int
    body: dict[str, Any]
    evidence_sha256: str

def require_transfer_container_name(name: str) -> str:
    if not name.startswith("erasemap-transfer-"):
        raise ValueError("refusing to manage a non-transfer container")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]+", name):
        raise ValueError("invalid transfer container name")
    return name

def require_digest_image(image: str) -> str:
    if re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image) is None:
        raise ValueError("container image must use an immutable sha256 digest")
    return image
```

`DockerService` must expose `start(env, mounts, args)`, `inspect_digest()`, and `stop()`. `start`
constructs one argument array beginning with `docker run --detach --rm --name`, followed by the
validated generated name and `-p 127.0.0.1:<host-port>:<internal-port>`;
`inspect_digest` compares `docker image inspect` RepoDigests with the frozen reference; `stop` calls
`docker rm -f` only after `require_transfer_container_name` succeeds.

Use `subprocess.run` argument arrays only. Reject mutable image tags at protocol load even when a
digest follows a human-readable tag. Bind random ports to `127.0.0.1`, create unique names using PID
plus a random nonce, mount only runner-created temporary directories, and always tear down in
`__exit__`.

- [ ] **Step 4: Run adapter contracts, lint, and typing**

Run: `.venv/bin/pytest tests/test_open_transfer_adapters.py -q && .venv/bin/ruff check experiments/open_transfer_services.py tests/test_open_transfer_adapters.py`
Expected: PASS.

- [ ] **Step 5: Commit lifecycle utilities**

```bash
git add experiments/open_transfer_services.py tests/test_open_transfer_adapters.py
git commit -m "feat: isolate stock transfer services"
```

### Task 5: Implement Qdrant biometric adapter

**Files:**
- Create: `experiments/prepare_open_transfer_assets.py`
- Create: `experiments/open_transfer_adapters.py`
- Modify: `tests/test_open_transfer_adapters.py`

- [ ] **Step 1: Add failing public-face asset tests**

Assert that the asset builder loads the documented Olivetti source, selects the exact frozen subject
and image indices, preserves original 64x64 float samples as 4,096-dimensional vectors without a
trained transform, writes deterministic NPZ content, and emits source plus derived SHA-256 values.
Development and confirmatory subject identifiers must be disjoint.

- [ ] **Step 2: Implement and run the deterministic asset builder**

Run: `PYTHONPATH=src .venv/bin/python experiments/prepare_open_transfer_assets.py --output /tmp/open-transfer-assets`
Expected: one deterministic NPZ and one provenance JSON whose source URL, source description,
selected indices, preprocessing declaration, and hashes match the frozen protocol.

- [ ] **Step 3: Add failing Qdrant workflow tests**

Test fixture order must be: create collection, upsert public-face embeddings with subject payload,
create collection snapshot, delete one subject point with `wait=true`, query absence, recover the
snapshot with priority `snapshot`, query recurrence, apply registered control, replay, query final
absence. Assert that a 2xx delete response alone makes `native-success` complete but not EraSeMap.

- [ ] **Step 4: Implement `QdrantBiometricAdapter` using raw documented REST calls**

The adapter must expose `setup_case`, `native_delete`, `observe_derivatives`, `replay_recovery`,
`apply_control`, and `retained_count`. It records the collection snapshot filename/hash and uses
actual Olivetti-derived embeddings already materialized by the protocol asset step.

- [ ] **Step 5: Run Qdrant contract tests**

Run: `.venv/bin/pytest tests/test_open_transfer_adapters.py -q -k qdrant`
Expected: PASS.

### Task 6: Implement Keycloak identity adapter

**Files:**
- Modify: `experiments/open_transfer_adapters.py`
- Modify: `tests/test_open_transfer_adapters.py`

- [ ] **Step 1: Add failing Keycloak fixture tests**

Cover bootstrap token acquisition, realm/user creation, user deletion returning 204, user search
returning empty, stopped-server realm export containing the subject, import into a fresh isolated
container, and recurrence observation. Assert export/import limitations from the official protocol
are preserved in the report.

- [ ] **Step 2: Implement `KeycloakIdentityAdapter`**

Use only the Admin REST API and documented `kc.sh export`/`kc.sh import` commands inside stock
containers. Stop the source instance before export, never export bootstrap credentials into evidence,
and restore into a fresh runner-owned database directory. Controls delete the subject and invalidate
the registered export carrier; they do not claim to invalidate unknown replicas.

- [ ] **Step 3: Run Keycloak contract tests**

Run: `.venv/bin/pytest tests/test_open_transfer_adapters.py -q -k keycloak`
Expected: PASS.

### Task 7: Implement MLflow lineage adapter

**Files:**
- Modify: `experiments/open_transfer_adapters.py`
- Modify: `tests/test_open_transfer_adapters.py`

- [ ] **Step 1: Add failing MLflow fixture tests**

Cover experiment/run creation, subject commitment tag, real artifact upload, `runs/delete` soft
deletion, metadata lifecycle stage observation, artifact survival, run restore recurrence, and hard
cleanup control. Missing artifact evidence must produce `UNVERIFIED`.

- [ ] **Step 2: Implement `MLflowLineageAdapter`**

Use the stock tracking REST API for metadata and the server's configured artifact root for physical
artifact checks. Record soft-delete and artifact existence as distinct observations. Do not import
MLflow into the package or call private database tables from the decision core.

- [ ] **Step 3: Run all adapter tests and commit the three adapters**

Run: `.venv/bin/pytest tests/test_open_transfer_adapters.py -q`
Expected: PASS.

```bash
git add experiments/prepare_open_transfer_assets.py experiments/open_transfer_adapters.py tests/test_open_transfer_adapters.py
git commit -m "feat: add stock service transfer adapters"
```

### Task 8: Build the live 60-case runner and offline verifier

**Files:**
- Create: `experiments/run_open_transfer_v1.py`
- Create: `scripts/verify_open_transfer_v1.py`
- Create: `tests/test_open_transfer_result.py`

- [ ] **Step 1: Write failing runner/result tests**

Test deterministic case IDs, exact 60-cell matrix, one service lifecycle per family batch, no
credential persistence, atomic result writing, non-overwrite default, all three rotation records,
and verifier rejection of any changed trial hash or result metric.

- [ ] **Step 2: Implement runner modes**

The CLI must support `--smoke`, `--output`, `--protocol`, and `--allow-overwrite`. Normal mode loads
the frozen protocol, verifies assets and image digests, executes all 60 cases, writes raw redacted
evidence, `trials.jsonl`, `result.json`, and `PROVENANCE.json`, then computes the summary only from
the serialized trial records.

- [ ] **Step 3: Implement independent offline recomputation**

The verifier must parse JSON independently of the runner, recompute case matrix/gates/hashes, reject
extra files or missing evidence, compare the recorded core hash with the committed source, and print
one canonical summary with exit code 0 only on PASS.

- [ ] **Step 4: Run all non-live tests**

Run: `.venv/bin/pytest tests/test_open_transfer.py tests/test_open_transfer_evidence.py tests/test_open_transfer_adapters.py tests/test_open_transfer_result.py -q`
Expected: PASS.

- [ ] **Step 5: Commit implementation before the first confirmatory run**

```bash
git add experiments/run_open_transfer_v1.py scripts/verify_open_transfer_v1.py tests/test_open_transfer_result.py
git commit -m "feat: add open transfer experiment runner"
```

### Task 9: Execute live smoke and first confirmatory run

**Files:**
- Create: `outputs/open-transfer-v1/result.json`
- Create: `outputs/open-transfer-v1/trials.jsonl`
- Create: `outputs/open-transfer-v1/PROVENANCE.json`
- Create: `docs/OPEN_TRANSFER_V1_REPORT.md`

- [ ] **Step 1: Start Docker Desktop only if the daemon is unavailable**

Run: `docker info >/dev/null || open -a Docker`
Expected: Docker daemon becomes available without touching existing containers.

- [ ] **Step 2: Pull exactly the digest-pinned protocol images**

Extract the three immutable `repository@sha256:<64 lowercase hex>` values from the frozen protocol,
run `docker pull` once per value, then inspect each with `docker image inspect` and require exact
RepoDigest equality.

- [ ] **Step 3: Execute live service smokes**

Run: `PYTHONPATH=src .venv/bin/python experiments/run_open_transfer_v1.py --smoke --output /tmp/erasemap-open-transfer-smoke`
Expected: all three stock services start, pass their documented workflow, and tear down; no existing
container is removed.

- [ ] **Step 4: Execute the first complete confirmatory run once**

Run: `PYTHONPATH=src .venv/bin/python experiments/run_open_transfer_v1.py --output outputs/open-transfer-v1`
Expected: either one immutable PASS result or a preserved FAIL result. Do not tune v1 after seeing it.

- [ ] **Step 5: Verify the serialized result offline**

Run: `.venv/bin/python scripts/verify_open_transfer_v1.py --result outputs/open-transfer-v1/result.json`
Expected: printed recomputed metrics match the committed files; exit 0 only if every gate passed.

- [ ] **Step 6: Write the bounded result report and commit raw evidence**

Report the first result, service versions/digests, public input hashes, every failure, and the exact
claim boundary. Force-add ignored output artifacts only after checking them for credentials.

```bash
git add docs/OPEN_TRANSFER_V1_REPORT.md
git add -f outputs/open-transfer-v1/result.json outputs/open-transfer-v1/trials.jsonl outputs/open-transfer-v1/PROVENANCE.json
git commit -m "evidence: record open transfer v1 result"
```

### Task 10: Build bilingual usability and external-transfer handoff

**Files:**
- Create: `usability/protocol-v1.json`
- Create: `usability/cards-en.json`
- Create: `usability/cards-ru.json`
- Create: `usability/participant-response-schema.json`
- Create: `usability/score.py`
- Create: `usability/verify.py`
- Create: `usability/README.md`
- Create: `external_transfer/README.md`
- Create: `external_transfer/manifest-template.json`
- Create: `external_transfer/attest.py`
- Create: `external_transfer/verify.py`
- Create: `tests/test_usability_kit.py`
- Create: `tests/test_external_transfer.py`

- [ ] **Step 1: Write failing packet and scorer tests**

Assert twelve aligned cards per language, four cases per truth class, no gold fields in participant
cards, exact response schema, deterministic randomized order from participant nonce, comprehension
metrics, no aggregate PASS under 10 participants, and signature/attestation rejection when external
authorship fields are absent.

- [ ] **Step 2: Implement sealed gold and deterministic scoring**

Gold labels live in a separate hashed file consumed only by `score.py`. The scorer emits counts and
Wilson intervals for explanation, verdict, path, and action accuracy plus median completion time.
It must label fewer than ten participants `INSUFFICIENT_SAMPLE`, never PASS.

- [ ] **Step 3: Implement external manifest and attestation verification**

Require evaluator identity, contact, organization or independent status, authorship declaration,
start/end timestamps, clean commit, core hash, image digests, raw evidence manifest, result hash, and
Ed25519 signature. Keep `external_transfer/results/` empty except for a README until a real signed
submission exists.

- [ ] **Step 4: Run kit tests and commit**

Run: `.venv/bin/pytest tests/test_usability_kit.py tests/test_external_transfer.py -q`
Expected: PASS.

```bash
git add usability external_transfer tests/test_usability_kit.py tests/test_external_transfer.py
git commit -m "feat: add bilingual transfer evaluation kits"
```

### Task 11: Integrate evidence into presentation and scientific artifacts

**Files:**
- Modify: `README.md`
- Modify: `docs/COMPETITION_EVIDENCE_SCORECARD.md`
- Modify: `docs/SCIENTIFIC_CLAIM_MATRIX.md`
- Modify: `docs/JURY_DEFENSE_RU.md`
- Modify: `docs/JUDGE_QA_RU.md`
- Modify: `docs/NOVELTY_AND_PRIOR_ART.md`
- Modify: `competition/paper/EraSeMap_scientific_paper_EN.md`
- Modify: `competition/paper/EraSeMap_scientific_paper_RU.md`
- Modify: generated DOCX/PDF files
- Modify: `src/erasemap/showcase.py`
- Modify: `tests/test_showcase.py`

- [ ] **Step 1: Add failing showcase assertions**

Assert the showcase verifies the open-transfer result hash, contains one common seven-step visual
story, distinguishes real process/public input/project-authored/external pending, and exposes the
usability handoff without displaying invented participant metrics.

- [ ] **Step 2: Integrate only metrics supported by the frozen result**

If v1 passes, update real-input/transfer and relevance rows within the design's score bounds. Keep
independence at 7.8 and clarity below 9.7 until human results exist. If v1 fails, document the
negative result and do not raise the affected score.

- [ ] **Step 3: Rebuild and visually inspect both papers**

Run the existing paper builder and LibreOffice conversion, then use `pdftotext` plus page rendering
to confirm tables, captions, page breaks, links, and both language versions.

- [ ] **Step 4: Run showcase tests and commit**

Run: `.venv/bin/pytest tests/test_showcase.py -q`
Expected: PASS.

```bash
git add README.md docs competition/paper src/erasemap/showcase.py tests/test_showcase.py
git commit -m "docs: integrate open transfer evidence"
```

### Task 12: Add release and CI gates, then publish verified main

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/reproduce_release.sh`

- [ ] **Step 1: Add offline result and packet checks to CI**

CI must run the committed open-transfer verifier, usability kit tests, and external-transfer tests.
A live container job may rerun only when all three immutable images are available and must never
substitute fixtures for the committed live result.

- [ ] **Step 2: Add equivalent local release checks**

The core release profile verifies committed evidence and packet integrity. A separate
`transfer-live` profile performs the full container rerun into a temporary directory and verifies
it without changing the worktree.

- [ ] **Step 3: Run all deterministic gates**

```bash
.venv/bin/ruff check .
.venv/bin/mypy --strict src pilot external_challenge external_temporal_challenge external_transfer usability
.venv/bin/pytest --cov=erasemap --cov=external_challenge --cov=external_temporal_challenge --cov=pilot --cov-report=term-missing --cov-fail-under=90
lake build --wfail
./scripts/reproduce_release.sh core
git diff --check
```

Expected: every command exits 0; coverage remains at least 90%; the release script leaves the
worktree unchanged.

- [ ] **Step 4: Run the live transfer reproduction gate**

Run: `./scripts/reproduce_release.sh transfer-live`
Expected: three stock services rerun into a temporary directory and the independent offline verifier
returns the same frozen primary metrics.

- [ ] **Step 5: Commit CI integration and push main**

```bash
git add .github/workflows/ci.yml scripts/reproduce_release.sh
git commit -m "ci: verify open transfer evidence"
git push origin main
```

- [ ] **Step 6: Wait for GitHub Actions and verify delivery**

Require the pushed workflow conclusion `success`, then verify local `HEAD == origin/main`, ahead and
behind are `0 0`, the worktree is clean, and the remote tree contains protocol, raw result, verifier,
usability kit, external handoff, papers, and CI workflow before reporting completion.
