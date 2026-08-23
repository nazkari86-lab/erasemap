# Erasure Tomography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, exactly certified Erasure Tomography layer that localizes bounded deletion-recurrence mechanisms from coded synthetic-subject probes and hands them to existing PCUG/TRE repair.

**Architecture:** A pure Python core owns immutable probe designs, exhaustive identifiability certificates, and exact decoding. A separately implemented oracle checks the production decoder; a bounded physical lab and prospective runner produce append-only evidence; Lean proves the finite decoding and composition boundaries. Existing temporal and robust-erasure modules remain authoritative for stabilization.

**Tech Stack:** Python 3.11 dataclasses/enums/itertools/hashlib/json, pytest/Hypothesis, existing EraSeMap PCUG/RSE/TRE modules, Docker-backed stock services where available, Lean 4, GitHub Actions.

---

## File structure

- `src/erasemap/erasure_tomography.py`: immutable domain model, verdicts, exact prediction, certificate, and decoder.
- `src/erasemap/erasure_tomography_design.py`: feasible-row validation and deterministic exact matrix constructor.
- `src/erasemap/erasure_tomography_oracle.py`: independently structured exhaustive oracle used only for comparison.
- `src/erasemap/erasure_tomography_lab.py`: bounded candidate catalogue, synthetic-subject replay, and PCUG/TRE bridge.
- `src/erasemap/erasure_tomography_conformance.py`: deterministic finite-domain conformance sweep.
- `tests/test_erasure_tomography.py`: domain, decoding, ambiguity, noise, and failure tests.
- `tests/test_erasure_tomography_design.py`: constructor optimality and infeasibility tests.
- `tests/test_erasure_tomography_lab.py`: physical replay and stabilization integration tests.
- `tests/test_erasure_tomography_conformance.py`: production/oracle equality and frozen digest tests.
- `experiments/run_erasure_tomography_v1.py`: prospective experiment runner.
- `scripts/verify_erasure_tomography_v1.py`: independent recomputation of result identities, metrics, and gates.
- `scripts/verify_erasure_tomography_conformance.py`: frozen conformance verifier.
- `benchmark/erasure-tomography-v1.json`: frozen prospective protocol.
- `formal/erasure-tomography-conformance-v1.json`: frozen executable conformance digest.
- `EraseMapFormal/ErasureTomography.lean`: finite unique-recovery and fail-closed boundary theorems.
- `EraseMapFormal.lean`: import the new formal module.
- `docs/ERASURE_TOMOGRAPHY_V1_PREREGISTRATION.md`: human-readable prospective protocol.
- `docs/ERASURE_TOMOGRAPHY_V1_REPORT.md`: generated-result interpretation after the first frozen run.
- `docs/NOVELTY_AND_PRIOR_ART.md`: bounded novelty comparison.
- `docs/SCIENTIFIC_CLAIM_MATRIX.md`: ET claim, assumptions, evidence, and falsifier.
- `docs/JUDGE_QA_RU.md`: simple Russian explanation.
- `README.md`: headline result and reproduction commands.
- `.github/workflows/ci.yml`: unit, conformance, prospective replay, and verification gates.
- `scripts/reproduce_release.sh`: local reproduction of the same gates.

### Task 1: Exact domain and fail-closed decoder

**Files:**
- Create: `src/erasemap/erasure_tomography.py`
- Create: `tests/test_erasure_tomography.py`

- [ ] **Step 1: Write failing domain and decoding tests**

```python
from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyVerdict,
    certify_design,
    decode,
)


def test_unique_support_is_localized() -> None:
    design = ProbeDesign(
        mechanism_ids=("backup", "queue", "vector"),
        rows=((True, True, False), (True, False, True), (False, True, True)),
        max_failures=1,
        error_budget=0,
    )
    report = decode(design, (True, False, True), TomographyEvidence.complete())
    assert report.verdict is TomographyVerdict.LOCALIZED
    assert report.support == ("queue",)


def test_identical_columns_are_ambiguous() -> None:
    design = ProbeDesign(("a", "b"), ((True, True),), 1, 0)
    report = decode(design, (True,), TomographyEvidence.complete())
    assert report.verdict is TomographyVerdict.AMBIGUOUS
    assert report.admissible_supports == (("a",), ("b",))


def test_missing_execution_evidence_is_unverified() -> None:
    design = ProbeDesign(("a",), ((True,),), 1, 0)
    evidence = TomographyEvidence(True, False, True, True, True)
    assert decode(design, (True,), evidence).verdict is TomographyVerdict.UNVERIFIED


def test_all_negative_is_not_global_complete() -> None:
    design = ProbeDesign(("a", "b"), ((True, False), (False, True)), 1, 0)
    report = decode(design, (False, False), TomographyEvidence.complete())
    assert report.verdict is TomographyVerdict.NO_OBSERVED_RECURRENCE
    assert report.support == ()
```

- [ ] **Step 2: Run tests and confirm missing-module failure**

Run: `python -m pytest tests/test_erasure_tomography.py -q`

Expected: collection fails with `ModuleNotFoundError: erasemap.erasure_tomography`.

- [ ] **Step 3: Implement immutable types, validation, prediction, certificate, and decoder**

```python
class TomographyVerdict(str, Enum):
    NO_OBSERVED_RECURRENCE = "NO_OBSERVED_RECURRENCE"
    LOCALIZED = "LOCALIZED"
    AMBIGUOUS = "AMBIGUOUS"
    OUT_OF_MODEL = "OUT_OF_MODEL"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class ProbeDesign:
    mechanism_ids: tuple[str, ...]
    rows: tuple[tuple[bool, ...], ...]
    max_failures: int
    error_budget: int

    def __post_init__(self) -> None:
        if not self.mechanism_ids or len(set(self.mechanism_ids)) != len(self.mechanism_ids):
            raise ValueError("mechanism ids must be non-empty and unique")
        if not self.rows or any(len(row) != len(self.mechanism_ids) for row in self.rows):
            raise ValueError("every probe row must match the mechanism catalogue")
        if self.max_failures < 0 or self.max_failures > len(self.mechanism_ids):
            raise ValueError("invalid maximum failure count")
        if self.error_budget < 0:
            raise ValueError("error budget cannot be negative")


def decode(
    design: ProbeDesign,
    observations: tuple[bool, ...],
    evidence: TomographyEvidence,
) -> TomographyReport:
    if not evidence.valid:
        return TomographyReport(TomographyVerdict.UNVERIFIED, (), (), None)
    if len(observations) != len(design.rows):
        raise ValueError("observation count must match probe rows")
    admissible = tuple(
        support for support in enumerate_supports(design)
        if hamming_distance(predict(design, support), observations) <= design.error_budget
    )
    if not admissible:
        return TomographyReport(TomographyVerdict.OUT_OF_MODEL, (), (), None)
    if len(admissible) > 1:
        return TomographyReport(TomographyVerdict.AMBIGUOUS, (), admissible, None)
    support = admissible[0]
    verdict = (
        TomographyVerdict.NO_OBSERVED_RECURRENCE
        if not support else TomographyVerdict.LOCALIZED
    )
    return TomographyReport(verdict, support, admissible, distance_for(support))
```

The complete file must also define `TomographyEvidence`, `TomographyCertificate`,
`TomographyReport`, `enumerate_supports`, `predict`, `hamming_distance`, and `certify_design` using
deterministic tuple ordering.

- [ ] **Step 4: Add validation, noise, out-of-model, and order-determinism tests**

Add tests that reject duplicate IDs, malformed rows, invalid bounds, wrong observation length;
correct one flipped observation when minimum outcome distance exceeds two; return `OUT_OF_MODEL`
when no bounded support fits; and produce identical reports for repeated calls.

- [ ] **Step 5: Run focused quality gates**

Run: `python -m pytest tests/test_erasure_tomography.py -q && python -m ruff check src/erasemap/erasure_tomography.py tests/test_erasure_tomography.py && python -m mypy --strict src/erasemap/erasure_tomography.py`

Expected: all tests pass and both static checks exit zero.

- [ ] **Step 6: Commit the exact decoder**

```bash
git add src/erasemap/erasure_tomography.py tests/test_erasure_tomography.py
git commit -m "feat: add fail-closed erasure tomography decoder"
```

### Task 2: Certified workflow-constrained probe constructor

**Files:**
- Create: `src/erasemap/erasure_tomography_design.py`
- Create: `tests/test_erasure_tomography_design.py`

- [ ] **Step 1: Write failing exact-construction tests**

```python
def test_constructor_finds_minimum_row_design() -> None:
    feasible = tuple(product((False, True), repeat=4))[1:]
    result = construct_minimum_design(("a", "b", "c", "d"), feasible, 1, 0)
    assert result.status is DesignStatus.OPTIMAL
    assert result.design is not None
    assert result.design.certificate.uniquely_decodable
    assert len(result.design.rows) == 3


def test_constructor_reports_infeasible_constraints() -> None:
    result = construct_minimum_design(
        ("a", "b"), ((True, True),), max_failures=1, error_budget=0
    )
    assert result.status is DesignStatus.INFEASIBLE
    assert result.indistinguishable_pairs
```

- [ ] **Step 2: Run tests and verify missing-module failure**

Run: `python -m pytest tests/test_erasure_tomography_design.py -q`

Expected: missing module/function failure.

- [ ] **Step 3: Implement exact branch-and-bound construction**

Define `DesignStatus`, `ConstructionResult`, row validation, lexicographic canonicalization, and
`construct_minimum_design`. Enumerate row subsets by increasing row count and increasing total
declared row cost; call `certify_design` as the sole feasibility authority; return the first key
`(row_count, total_cost, rows)` that is uniquely decodable.

- [ ] **Step 4: Add exhaustive small-domain optimality property test**

For catalogues of two through five mechanisms, compare the constructor result with a separately
written test-only combinations oracle. Include duplicated feasible rows, forbidden all-zero rows,
and reverse input ordering.

- [ ] **Step 5: Run focused gates and commit**

Run: `python -m pytest tests/test_erasure_tomography_design.py -q`

Run: `python -m ruff check src/erasemap/erasure_tomography_design.py tests/test_erasure_tomography_design.py`

Commit:

```bash
git add src/erasemap/erasure_tomography_design.py tests/test_erasure_tomography_design.py
git commit -m "feat: construct certified tomography probe designs"
```

### Task 3: Independent oracle and executable conformance

**Files:**
- Create: `src/erasemap/erasure_tomography_oracle.py`
- Create: `src/erasemap/erasure_tomography_conformance.py`
- Create: `tests/test_erasure_tomography_conformance.py`
- Create: `scripts/verify_erasure_tomography_conformance.py`
- Create after execution: `formal/erasure-tomography-conformance-v1.json`

- [ ] **Step 1: Write failing oracle-agreement tests**

Build all non-empty matrices with up to four mechanisms and four rows, all supports within `k <= 2`,
and observation flips within `e <= 1`. Assert production verdict, support, and admissible supports
equal the oracle output.

- [ ] **Step 2: Implement an independently structured oracle**

The oracle must enumerate integer bitmasks rather than call `enumerate_supports`, `predict`, or
`decode`. It converts each support mask into an outcome mask with bit operations, calculates XOR
bit counts, and returns all matching supports in mechanism-ID order.

- [ ] **Step 3: Implement deterministic conformance sweep**

`run_erasure_tomography_conformance()` must return schema, configuration count, localized,
ambiguous, out-of-model, no-recurrence counts, mismatch count, and SHA-256 over canonical JSONL
records. Include forward and reversed input orderings.

- [ ] **Step 4: Add verifier and freeze the record**

Run:

```bash
PYTHONPATH=src python scripts/verify_erasure_tomography_conformance.py \
  --output formal/erasure-tomography-conformance-v1.json
```

Then rerun with `--expected formal/erasure-tomography-conformance-v1.json --output /tmp/et.json` and
expect an exact match and `mismatches: 0`.

- [ ] **Step 5: Commit conformance authority**

```bash
git add src/erasemap/erasure_tomography_oracle.py \
  src/erasemap/erasure_tomography_conformance.py \
  tests/test_erasure_tomography_conformance.py \
  scripts/verify_erasure_tomography_conformance.py \
  formal/erasure-tomography-conformance-v1.json
git commit -m "test: freeze erasure tomography conformance"
```

### Task 4: Bounded physical lab and PCUG/TRE bridge

**Files:**
- Create: `src/erasemap/erasure_tomography_lab.py`
- Create: `tests/test_erasure_tomography_lab.py`
- Modify: `src/erasemap/temporal_robust.py`

- [ ] **Step 1: Write failing physical recurrence tests**

```python
def test_coded_probe_localizes_backup_and_queue(tmp_path: Path) -> None:
    trial = run_tomography_round(tmp_path, active_ids=("backup_restore", "retry_replay"))
    assert trial.report.verdict is TomographyVerdict.LOCALIZED
    assert trial.report.support == ("backup_restore", "retry_replay")
    assert all(trial.workflow_evidence_complete)


def test_localization_translates_to_robust_controls(tmp_path: Path) -> None:
    trial = run_tomography_and_stabilize(tmp_path, active_ids=("backup_restore",))
    assert trial.transition_ids == ("backup_restore",)
    assert trial.plan.complete
    assert not trial.post_control_recurrence
```

- [ ] **Step 2: Implement the smallest honest physical catalogue**

Reuse `MultiCarrierStorageLab` for real filesystem/SQLite carriers and define candidate adapters
with `seed`, `erase`, `reactivate`, and `observe` callables. Each probe receives a distinct random
commitment. Do not simulate a service name that is presented as a live stock service.

- [ ] **Step 3: Implement ET-to-TRE translation**

Add a helper that accepts only `LOCALIZED`, maps every mechanism ID to an existing
`TemporalTransition`, constructs a complete bounded topology envelope, and invokes
`exact_robust_stabilization_cut`. Missing mappings return an explicit unverified bridge result.

- [ ] **Step 4: Add contamination and missing-evidence negative tests**

Deliberately reuse a subject commitment across probes, skip one workflow action, hide one adapter,
and make two mechanisms observationally identical. Assert no case returns `LOCALIZED`.

- [ ] **Step 5: Run focused tests and commit**

Run: `python -m pytest tests/test_erasure_tomography_lab.py tests/test_temporal_robust.py -q`

Commit:

```bash
git add src/erasemap/erasure_tomography_lab.py src/erasemap/temporal_robust.py \
  tests/test_erasure_tomography_lab.py
git commit -m "feat: bridge tomography findings to robust erasure"
```

### Task 5: Freeze the prospective protocol before the first confirmatory run

**Files:**
- Create: `benchmark/erasure-tomography-v1.json`
- Create: `docs/ERASURE_TOMOGRAPHY_V1_PREREGISTRATION.md`
- Create: `tests/test_erasure_tomography_protocol.py`

- [ ] **Step 1: Write protocol schema tests**

Assert exact schema version, unique candidate IDs, `k`, `e`, frozen rows, row costs, seed list,
hidden-support commitment, container/adapter digests, primary gates, exclusions, and claim boundary.

- [ ] **Step 2: Create the machine-readable preregistration**

Use schema `erasemap-erasure-tomography-v1`. Include only mechanisms for which an implemented
adapter and feasible workflow exist. Primary gates must include zero false localization, full valid
support recovery, zero oracle mismatches, correct rejection of every frozen invalid case, zero
post-control recurrence, and zero retained-subject loss.

- [ ] **Step 3: Create the human-readable preregistration**

Explain the hypothesis, split, support generation, probe budget, baselines, stopping rule, invalid
run conditions, exact metrics, and claim exclusions. Label all expected directions as hypotheses.

- [ ] **Step 4: Verify hashes and commit without running confirmatory seeds**

Run: `python -m pytest tests/test_erasure_tomography_protocol.py -q`

Commit:

```bash
git add benchmark/erasure-tomography-v1.json \
  docs/ERASURE_TOMOGRAPHY_V1_PREREGISTRATION.md \
  tests/test_erasure_tomography_protocol.py
git commit -m "docs: preregister erasure tomography v1"
```

Record this commit hash as `PREREGISTRATION_COMMIT` in the runner and verifier. Do not amend it.

### Task 6: Prospective runner, strong baselines, and independent result verifier

**Files:**
- Create: `experiments/run_erasure_tomography_v1.py`
- Create: `scripts/verify_erasure_tomography_v1.py`
- Create: `tests/test_erasure_tomography_result.py`
- Create after first run: `outputs/erasure-tomography-v1/result.json`
- Create after first run: `outputs/erasure-tomography-v1/PROVENANCE.json`

- [ ] **Step 1: Write failing result-verification tests**

Test a valid small development result plus mutations of protocol hash, preregistration commit,
case order, duplicate subject, reported support, metrics, gates, oracle record, and final decision.
Every mutation must raise `ValueError`.

- [ ] **Step 2: Implement the prospective runner**

Read protocol bytes, validate every frozen field, execute valid and negative cases once in declared
order, record per-probe manifests, compare production decoder with the independent oracle, invoke
TRE on localized supports, and write canonical JSON with `schema_version`, protocol hash,
preregistration commit, evidence scope, claim boundary, baselines, metrics, gates, and trials.

- [ ] **Step 3: Implement baselines under frozen budgets**

Compute individual audit, random feasible matrices, greedy separating design, and declared-topology
only. Report exact probe counts and support recovery; do not call an expected result observed.

- [ ] **Step 4: Implement independent verification**

Recompute case identities, observations from probe records, oracle supports, all aggregate metrics,
every gate, and `passed`. Reject missing or extra records and non-canonical duplicate IDs.

- [ ] **Step 5: Run development tests only and commit implementation**

Run: `python -m pytest tests/test_erasure_tomography_result.py -q`

Commit the runner and verifier before executing the frozen confirmatory seeds.

- [ ] **Step 6: Execute the first frozen run once**

Run:

```bash
PYTHONPATH=src python experiments/run_erasure_tomography_v1.py \
  --protocol benchmark/erasure-tomography-v1.json \
  --output outputs/erasure-tomography-v1
python scripts/verify_erasure_tomography_v1.py \
  --result outputs/erasure-tomography-v1/result.json
```

Expected: the verifier exits zero only if every preregistered gate actually passes. If a gate fails,
commit the negative result unchanged and create v2 rather than editing v1.

- [ ] **Step 7: Commit append-only evidence**

```bash
git add outputs/erasure-tomography-v1
git commit -m "data: record erasure tomography v1 result"
```

### Task 7: Lean formal boundary and executable correspondence

**Files:**
- Create: `EraseMapFormal/ErasureTomography.lean`
- Modify: `EraseMapFormal.lean`
- Modify: `formal/README.md`
- Create: `tests/test_erasure_tomography_formal.py`

- [ ] **Step 1: Add a failing source-contract test**

Assert the Lean file declares `unique_decode_of_separated`, `ambiguous_without_separation`, and
`localized_controls_safe_for_listed_mechanisms`, and that the root module imports it.

- [ ] **Step 2: Formalize finite outcome separation**

Define finite supports, observation outcomes, Hamming distance, admissibility, and a decoder relation.
Prove that two admissible supports under `e` errors must be equal when pairwise outcome distance is
greater than `2*e`.

- [ ] **Step 3: Formalize the composition boundary**

State a problem structure whose assumptions explicitly include catalogue closure, sound mechanism
translation, and sound control effects. Prove safety only for the listed localized mechanisms; do
not quantify over arbitrary external mechanisms.

- [ ] **Step 4: Build with warnings and axiom audit**

Run: `lake build --wfail`

Run the repository's axiom audit path and confirm no new `axiom`, `sorry`, or `admit` appears.

- [ ] **Step 5: Commit formal results**

```bash
git add EraseMapFormal/ErasureTomography.lean EraseMapFormal.lean \
  formal/README.md tests/test_erasure_tomography_formal.py
git commit -m "proof: formalize bounded erasure tomography"
```

### Task 8: Docker-backed transfer layer

**Files:**
- Create: `experiments/erasure_tomography_services.py`
- Create: `experiments/run_erasure_tomography_docker_v1.py`
- Create: `tests/test_erasure_tomography_services.py`
- Modify: `benchmark/erasure-tomography-v1.json` only in a new version if the v1 protocol is already frozen

- [ ] **Step 1: Probe available existing stock-service lifecycle**

Reuse the digest-pinned Keycloak, MLflow, Qdrant, and PostgreSQL lifecycle from
`experiments/open_transfer_live.py` and `experiments/open_transfer_services.py`. Add Redis/MinIO only
if images are digest-pinned and health checks pass. Unavailable services produce `INCONCLUSIVE`, not
a simulated success.

- [ ] **Step 2: Write adapter contract tests with fake HTTP/process boundaries**

Test create, seed, delete, reactivate, observe, cleanup, timeout, wrong digest, and partial execution.
Every partial execution must yield incomplete evidence.

- [ ] **Step 3: Implement service adapters and provenance capture**

Record image digest, endpoint, operation timestamps, response commitments, container logs hash,
and cleanup status without storing credentials or raw synthetic secret values.

- [ ] **Step 4: Execute opt-in live profile**

Run only when Docker is available. Keep it outside the default unit test path; verify the output with
the same independent result verifier and label it `PROJECT_AUTHORED_LIVE_STOCK_SERVICE_TRANSFER`.

- [ ] **Step 5: Commit code and any honest environment result**

Do not claim a Docker result if the environment is unavailable. Commit an `INCONCLUSIVE` manifest
when execution was attempted but blocked after all safe checks.

### Task 9: Scientific report, novelty review, and judge explanation

**Files:**
- Create: `docs/ERASURE_TOMOGRAPHY_V1_REPORT.md`
- Modify: `docs/NOVELTY_AND_PRIOR_ART.md`
- Modify: `docs/STRUCTURED_PRIOR_ART_AND_PATENT_REVIEW.md`
- Modify: `docs/SCIENTIFIC_CLAIM_MATRIX.md`
- Modify: `docs/JUDGE_QA_RU.md`
- Modify: `docs/JURY_DEFENSE_RU.md`
- Modify: `README.md`

- [ ] **Step 1: Write the report from verified result fields**

Include exact counts, denominators, baselines, certificate, false-localization count, negative cases,
probe reduction, post-control recurrence, evidence scope, limitations, and reproduction commands.

- [ ] **Step 2: Extend prior-art review with exact boundaries**

Add primary-source comparisons for group testing, Boolean network tomography, deletion canaries,
P2E2, proof of unlearning, Chava, and automatic data-flow discovery. State that the tested
composition was not found in the documented search, not that it is the first in the world.

- [ ] **Step 3: Update claim matrix and fixed scoring only from evidence**

Add the ET claim with all eight assumptions and concrete falsifiers. Do not raise external
independence or production-validation scores from project-authored Docker evidence.

- [ ] **Step 4: Add a one-minute Russian explanation**

Use the three-test backup/queue/model example, followed by one sentence explaining the bounded
catalogue limitation. Avoid `k`-disjunct terminology in the first answer to a judge.

- [ ] **Step 5: Verify every README number against JSON**

Add tests or script assertions for every headline count and hash; run the public-results test suite.

- [ ] **Step 6: Commit documentation**

```bash
git add README.md docs
git commit -m "docs: report bounded erasure tomography evidence"
```

### Task 10: CI, release reproduction, and final repository verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/reproduce_release.sh`
- Modify: `tests/test_ci_environment.py` if new pinned dependencies are required

- [ ] **Step 1: Add deterministic CI gates**

Run unit tests through the existing coverage job, verify the frozen prospective result, regenerate
and compare ET conformance, run the prospective experiment into `/tmp`, independently verify it,
and build Lean with warnings/axiom audit. Keep optional live Docker transfer outside normal CI.

- [ ] **Step 2: Mirror gates in release reproduction**

Add the same commands using the existing release temporary directory so reproduction cannot dirty
the worktree.

- [ ] **Step 3: Run focused and full local gates**

```bash
python -m pytest tests/test_erasure_tomography*.py -q
python -m ruff check .
python -m mypy --strict src pilot external_challenge external_temporal_challenge external_transfer usability
python -m pytest --cov=erasemap --cov=external_challenge --cov=external_temporal_challenge \
  --cov=pilot --cov-report=term-missing --cov-fail-under=90
lake build --wfail
scripts/reproduce_release.sh core
```

Expected: every command exits zero and reproduction leaves the worktree unchanged.

- [ ] **Step 4: Commit CI integration**

```bash
git add .github/workflows/ci.yml scripts/reproduce_release.sh tests/test_ci_environment.py
git commit -m "ci: gate erasure tomography evidence"
```

- [ ] **Step 5: Verify delivery state before any completion claim**

Run:

```bash
git status --short --branch
git log -1 --oneline
git rev-list --left-right --count origin/main...HEAD
```

After an explicitly requested push, verify local HEAD equals `origin/main`, ahead/behind is `0 0`,
the worktree is clean, the remote files exist, and the GitHub Actions run for that exact SHA is green.

## Self-review record

- Spec coverage: core decoder, certificate, constructor, independent oracle, fail-closed negative
  cases, PCUG/TRE bridge, preregistration, physical evidence, Lean, Docker, baselines, reports, and CI
  each have an owning task.
- Claim boundary: every success remains relative to a frozen candidate catalogue, feasible workflows,
  sparsity/noise limits, and project-authored execution.
- Independence boundary: the oracle is implementation-independent, not an independent human
  evaluator; documentation must not convert it into external evidence.
- Prospective boundary: protocol commit precedes runner execution; failures are preserved and require
  a version bump.
- Type consistency: `ProbeDesign`, `TomographyEvidence`, `TomographyCertificate`,
  `TomographyReport`, `TomographyVerdict`, and `ConstructionResult` retain the same names throughout.
- Placeholder scan: no `TBD`, `TODO`, or unbounded “appropriate handling” steps remain.
