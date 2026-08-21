# EraseMap Core Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python CLI that generates controlled biometric-data lineage graphs, injects erasure faults, detects and explains residual paths, validates typed evidence, computes remediation plans, and benchmarks EraseMap against fixed baselines.

**Architecture:** The first sub-project is a dependency-light Python package with immutable domain types and pure core algorithms. JSON is the stable interchange format. The CLI composes generation, audit, planning, receipt verification, and benchmark modules; the future EraseTwin and web applications consume these interfaces without changing the core.

**Tech Stack:** Python 3.11+, standard library, `cryptography` for Ed25519, `pytest`, `pytest-cov`, `hypothesis`, `ruff`, and `mypy`.

---

## Scope decomposition

This plan implements the complete graph-audit research core. Two later plans will independently deliver:

1. `EraseTwin`: matched-nonmember model auditing against exact retraining.
2. `EraseMap Web`: offline graph visualization, receipt QR view, and fixed demonstration scenarios.

The core represents model evidence as a typed input but does not manufacture model-audit results. This preserves the scientific boundary between synthetic graph experiments and ML experiments.

## File map

- `pyproject.toml`: package metadata, commands, lint, type, and test configuration.
- `README.md`: reproducible installation and CLI quick start.
- `src/erasemap/__init__.py`: public version.
- `src/erasemap/domain.py`: enums and immutable graph, evidence, policy, action, audit, and plan records.
- `src/erasemap/codec.py`: strict JSON encoding and decoding.
- `src/erasemap/evidence.py`: artifact-specific evidence validators.
- `src/erasemap/audit.py`: descendant traversal, residual-path detection, explanations, and status aggregation.
- `src/erasemap/planning.py`: exact small-instance and greedy remediation solvers.
- `src/erasemap/generator.py`: seeded topology generation and deterministic fault injection.
- `src/erasemap/baselines.py`: receipt-only, checklist, and untyped traversal comparators.
- `src/erasemap/metrics.py`: per-trial outcomes and aggregate confidence intervals.
- `src/erasemap/receipts.py`: privacy-minimized Ed25519 signed receipts and anti-replay verification.
- `src/erasemap/benchmark.py`: frozen trial runner and machine-readable report export.
- `src/erasemap/cli.py`: `generate`, `audit`, `plan`, `receipt`, and `benchmark` commands.
- `tests/`: unit, property, integration, and deterministic snapshot tests mirroring the modules.
- `examples/five_branch_system.json`: fixed government-style demonstration graph.
- `docs/CORE_PROTOCOL.md`: algorithm, claims, limitations, and result-field documentation.

### Task 1: Create the executable package scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/erasemap/__init__.py`
- Create: `tests/test_package.py`

- [ ] **Step 1: Write the failing package test**

```python
from importlib.metadata import version

import erasemap


def test_package_version_matches_metadata() -> None:
    assert erasemap.__version__ == version("erasemap")
```

- [ ] **Step 2: Run the test and verify the package is missing**

Run: `python3 -m pytest tests/test_package.py -v`

Expected: failure because `erasemap` is not importable.

- [ ] **Step 3: Add package metadata and the public version**

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "erasemap"
version = "0.1.0"
description = "Typed residual-path auditing for controlled biometric data erasure"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["cryptography>=43"]

[project.optional-dependencies]
dev = [
  "hypothesis>=6.112",
  "mypy>=1.11",
  "pytest>=8.3",
  "pytest-cov>=5",
  "ruff>=0.6",
]

[project.scripts]
erasemap = "erasemap.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/erasemap"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["erasemap"]
```

```python
# src/erasemap/__init__.py
__version__ = "0.1.0"
```

Document `python3 -m venv .venv`, editable installation, test, lint, and CLI commands in `README.md` without claiming benchmark results.

- [ ] **Step 4: Install and run the package test**

Run: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest tests/test_package.py -v`

Expected: one passing test.

- [ ] **Step 5: Commit the scaffold**

```bash
git add pyproject.toml README.md src/erasemap/__init__.py tests/test_package.py
git commit -m "build: scaffold EraseMap package"
```

### Task 2: Define immutable domain records and invariants

**Files:**
- Create: `src/erasemap/domain.py`
- Create: `tests/test_domain.py`

- [ ] **Step 1: Write failing invariant tests**

```python
import pytest

from erasemap.domain import Artifact, ArtifactState, ArtifactType, Edge, ErasureGraph


def test_graph_rejects_edge_with_unknown_target() -> None:
    source = Artifact("person", "subject-1", ArtifactType.SOURCE_RECORD, ArtifactState.ACTIVE)
    with pytest.raises(ValueError, match="unknown target"):
        ErasureGraph(nodes={"person": source}, edges=(Edge("person", "missing", "COPIED_TO"),))


def test_erased_artifact_cannot_be_active_sink() -> None:
    with pytest.raises(ValueError, match="active sink"):
        Artifact("copy", "subject-1", ArtifactType.SOURCE_RECORD, ArtifactState.ERASED, active_sink=True)
```

- [ ] **Step 2: Run the tests and verify imports fail**

Run: `.venv/bin/pytest tests/test_domain.py -v`

Expected: collection failure because `erasemap.domain` does not exist.

- [ ] **Step 3: Implement enums and frozen dataclasses**

Define the enum values exactly so JSON and later modules share one vocabulary:

```python
class ArtifactType(StrEnum):
    SOURCE_RECORD = auto()
    BIOMETRIC_TEMPLATE = auto()
    SEARCH_INDEX_ENTRY = auto()
    CACHE_ENTRY = auto()
    BACKUP_COPY = auto()
    MODEL_INFLUENCE = auto()
    AUDIT_RECEIPT = auto()


class ArtifactState(StrEnum):
    ACTIVE = auto()
    ERASED = auto()
    BLOCKED = auto()
    WAITING_EXPIRY = auto()
    UNVERIFIED = auto()


class EdgeType(StrEnum):
    COPIED_TO = auto()
    DERIVED_INTO = auto()
    INDEXED_AS = auto()
    BACKED_UP_AS = auto()
    USED_TO_TRAIN = auto()
    SUPERSEDED_BY = auto()


class EvidenceKind(StrEnum):
    ABSENCE_CHECK = auto()
    CACHE_INVALIDATION = auto()
    EXPIRY_SCHEDULE = auto()
    CRYPTO_ERASURE = auto()
    MODEL_AUDIT = auto()
    SIGNED_STATEMENT = auto()


class AuditStatus(StrEnum):
    COMPLETE = auto()
    INCOMPLETE = auto()
    UNVERIFIED = auto()


class PolicyDecision(StrEnum):
    ERASE_REQUIRED = auto()
    BLOCK_ALLOWED = auto()
    RETENTION_REQUIRED = auto()
```

Define frozen dataclasses using these fields:

```python
@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    subject_id: str
    type: ArtifactType
    state: ArtifactState
    active_sink: bool = False
    purpose: str = ""
    commitment: str = ""
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.subject_id:
            raise ValueError("artifact id and subject id are required")
        if self.state is ArtifactState.ERASED and self.active_sink:
            raise ValueError("erased artifact cannot be an active sink")
```

Define the remaining record signatures exactly:

```python
@dataclass(frozen=True, slots=True)
class Edge:
    source_id: str
    target_id: str
    type: EdgeType
    cross_subject: bool = False


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    artifact_id: str
    kind: EvidenceKind
    valid_signature: bool = False
    commitment: str = ""
    observed_absent: bool = False
    issued_epoch: int = 0
    expires_epoch: int | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    artifact_id: str
    decision: PolicyDecision


@dataclass(frozen=True, slots=True)
class RemediationAction:
    id: str
    covers_artifact_ids: frozenset[str]
    cost: int
    result_state: ArtifactState
    permitted: bool = True


@dataclass(frozen=True, slots=True)
class EvidenceCheck:
    valid: bool
    reason: str
    effective_state: ArtifactState


@dataclass(frozen=True, slots=True)
class ResidualPath:
    node_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class AuditResult:
    status: AuditStatus
    residual_paths: tuple[ResidualPath, ...]
    shortest_path: ResidualPath | None
    evidence_checks: tuple[tuple[str, EvidenceCheck], ...]
    reachable_artifact_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class RemediationPlan:
    action_ids: tuple[str, ...]
    total_cost: int
    covered_artifact_ids: frozenset[str]
    uncovered_artifact_ids: frozenset[str]

    @property
    def complete(self) -> bool:
        return not self.uncovered_artifact_ids


@dataclass(frozen=True, slots=True)
class ErasureGraph:
    nodes: Mapping[str, Artifact]
    edges: tuple[Edge, ...]
```

`ErasureGraph.__post_init__` must reject unknown endpoints, duplicate edges, and subject-mismatched edges unless the edge is explicitly marked cross-subject. Freeze `nodes` with `MappingProxyType(dict(self.nodes))` so callers cannot mutate a validated graph.

- [ ] **Step 4: Run invariant tests**

Run: `.venv/bin/pytest tests/test_domain.py -v`

Expected: all tests pass.

- [ ] **Step 5: Run static checks and commit**

Run: `.venv/bin/ruff check src/erasemap/domain.py tests/test_domain.py && .venv/bin/mypy src/erasemap/domain.py`

Expected: both commands succeed.

```bash
git add src/erasemap/domain.py tests/test_domain.py
git commit -m "feat: define erasure graph domain model"
```

### Task 3: Add strict, canonical JSON interchange

**Files:**
- Create: `src/erasemap/codec.py`
- Create: `tests/test_codec.py`

- [ ] **Step 1: Write failing round-trip and rejection tests**

```python
import pytest

from erasemap.codec import graph_from_json, graph_to_json
from tests.factories import simple_graph


def test_graph_json_is_canonical_and_round_trips() -> None:
    graph = simple_graph()
    encoded = graph_to_json(graph)
    assert encoded == graph_to_json(graph_from_json(encoded))
    assert " " not in encoded


def test_decoder_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="unknown field"):
        graph_from_json('{"nodes":[],"edges":[],"surprise":1}')
```

Create `tests/factories.py` with explicit reusable constructors:

```python
from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    Edge,
    EdgeType,
    ErasureGraph,
)


def artifact(
    *,
    id: str = "artifact",
    subject_id: str = "subject-1",
    type: ArtifactType = ArtifactType.SOURCE_RECORD,
    state: ArtifactState = ArtifactState.ACTIVE,
    active_sink: bool = False,
    commitment: str = "sha256:test",
) -> Artifact:
    return Artifact(id, subject_id, type, state, active_sink, "test", commitment)


def simple_graph() -> ErasureGraph:
    nodes = {
        "source": artifact(id="source"),
        "template": artifact(id="template", type=ArtifactType.BIOMETRIC_TEMPLATE),
        "index": artifact(
            id="index",
            type=ArtifactType.SEARCH_INDEX_ENTRY,
            active_sink=True,
        ),
    }
    edges = (
        Edge("source", "template", EdgeType.DERIVED_INTO),
        Edge("template", "index", EdgeType.INDEXED_AS),
    )
    return ErasureGraph(nodes=nodes, edges=edges)
```

- [ ] **Step 2: Run tests and verify codec imports fail**

Run: `.venv/bin/pytest tests/test_codec.py -v`

Expected: collection failure for `erasemap.codec`.

- [ ] **Step 3: Implement explicit encoders and decoders**

Use `json.dumps(payload, sort_keys=True, separators=(",", ":"))`. Decode every allowed field explicitly, convert strings through enums, reject extra or missing keys with deterministic errors, and construct `ErasureGraph` so domain invariants run after decoding. Do not use `pickle`, `eval`, or automatic object hooks.

- [ ] **Step 4: Run round-trip tests**

Run: `.venv/bin/pytest tests/test_codec.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit canonical interchange**

```bash
git add src/erasemap/codec.py tests/factories.py tests/test_codec.py
git commit -m "feat: add canonical graph JSON codec"
```

### Task 4: Validate typed evidence without conflating signatures and truth

**Files:**
- Create: `src/erasemap/evidence.py`
- Create: `tests/test_evidence.py`

- [ ] **Step 1: Write failing typed-validation tests**

```python
from erasemap.domain import ArtifactState, ArtifactType, Evidence, EvidenceKind
from erasemap.evidence import validate_evidence
from tests.factories import artifact


def test_signed_statement_does_not_prove_template_absence() -> None:
    node = artifact(type=ArtifactType.BIOMETRIC_TEMPLATE, state=ArtifactState.ERASED)
    evidence = Evidence("ev", node.id, EvidenceKind.SIGNED_STATEMENT, valid_signature=True)
    result = validate_evidence(node, evidence, now_epoch=100)
    assert not result.valid
    assert result.reason == "template requires committed absence evidence"


def test_pending_backup_is_not_erased() -> None:
    node = artifact(type=ArtifactType.BACKUP_COPY, state=ArtifactState.WAITING_EXPIRY)
    evidence = Evidence("ev", node.id, EvidenceKind.EXPIRY_SCHEDULE, expires_epoch=200)
    result = validate_evidence(node, evidence, now_epoch=100)
    assert result.valid
    assert result.effective_state is ArtifactState.WAITING_EXPIRY
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/test_evidence.py -v`

Expected: import failure for `erasemap.evidence`.

- [ ] **Step 3: Implement a validator dispatch table**

Implement `validate_evidence(artifact, evidence, now_epoch) -> EvidenceCheck`. Require:

- `ABSENCE_CHECK` plus matching pre-deletion commitment for source, template, and index erasure;
- `CACHE_INVALIDATION` plus elapsed propagation deadline for cache erasure;
- `EXPIRY_SCHEDULE` for a pending backup and `CRYPTO_ERASURE` for an erased backup;
- `MODEL_AUDIT` with frozen protocol id, reference id, and pass flag for model influence;
- matching artifact id, non-expired evidence, and consistent requested state for every kind.

Return a failed check instead of raising for invalid evidence content. Raise only for programmer misuse such as a negative `now_epoch`.

- [ ] **Step 4: Run typed evidence tests**

Run: `.venv/bin/pytest tests/test_evidence.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit evidence contracts**

```bash
git add src/erasemap/evidence.py tests/test_evidence.py
git commit -m "feat: validate artifact-specific erasure evidence"
```

### Task 5: Detect residual paths and produce minimal explanations

**Files:**
- Create: `src/erasemap/audit.py`
- Create: `tests/test_audit.py`
- Create: `tests/test_audit_properties.py`

- [ ] **Step 1: Write failing residual-path tests**

```python
from erasemap.audit import audit_subject
from erasemap.domain import AuditStatus
from tests.factories import graph_with_orphaned_index


def test_audit_returns_shortest_residual_counterexample() -> None:
    graph, evidence = graph_with_orphaned_index()
    result = audit_subject(graph, evidence, subject_id="subject-1", now_epoch=100)
    assert result.status is AuditStatus.INCOMPLETE
    assert result.shortest_path.node_ids == ("source", "template", "index")
    assert result.shortest_path.reason == "active sink remains reachable"
```

Add a Hypothesis property: when every descendant is erased with matching valid evidence, `audit_subject` never returns `INCOMPLETE`; when a reachable active sink is inserted, it never returns `COMPLETE`.

Add the concrete orphaned-index fixture to `tests/factories.py`:

```python
def graph_with_orphaned_index() -> tuple[ErasureGraph, dict[str, Evidence]]:
    graph = simple_graph()
    erased_source = replace(graph.nodes["source"], state=ArtifactState.ERASED)
    erased_template = replace(graph.nodes["template"], state=ArtifactState.ERASED)
    updated = ErasureGraph(
        nodes={**graph.nodes, "source": erased_source, "template": erased_template},
        edges=graph.edges,
    )
    evidence = {
        erased_source.id: absence_evidence(erased_source),
        erased_template.id: absence_evidence(erased_template),
    }
    return updated, evidence


def absence_evidence(node: Artifact) -> Evidence:
    return Evidence(
        id=f"{node.id}-proof",
        artifact_id=node.id,
        kind=EvidenceKind.ABSENCE_CHECK,
        commitment=node.commitment,
        observed_absent=True,
        issued_epoch=90,
        expires_epoch=200,
    )
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/test_audit.py tests/test_audit_properties.py -v`

Expected: import failure for `erasemap.audit`.

- [ ] **Step 3: Implement deterministic breadth-first auditing**

Build sorted adjacency lists. Traverse only nodes matching the requested subject. Validate evidence for non-active terminal states. Record:

- reachable descendants;
- invalid and missing evidence checks;
- every residual active-sink path;
- the lexicographically deterministic shortest counterexample.

Aggregate status:

- `INCOMPLETE` when a prohibited active path exists;
- `UNVERIFIED` when no prohibited active path exists but required evidence is absent or invalid;
- `COMPLETE` only when neither condition exists.

- [ ] **Step 4: Run audit tests and coverage**

Run: `.venv/bin/pytest tests/test_audit.py tests/test_audit_properties.py --cov=erasemap.audit --cov-report=term-missing`

Expected: all tests pass and no uncovered decision branch remains in `audit_subject`.

- [ ] **Step 5: Commit residual auditing**

```bash
git add src/erasemap/audit.py tests/test_audit.py tests/test_audit_properties.py tests/factories.py
git commit -m "feat: detect and explain residual identity paths"
```

### Task 6: Compute exact and greedy remediation plans

**Files:**
- Create: `src/erasemap/planning.py`
- Create: `tests/test_planning.py`
- Create: `tests/test_planning_properties.py`

- [ ] **Step 1: Write failing optimality tests**

```python
from erasemap.planning import exact_plan, greedy_plan
from tests.factories import remediation_case


def test_exact_plan_finds_minimum_cost_cover() -> None:
    required, actions = remediation_case()
    plan = exact_plan(required, actions)
    assert plan.covered_artifact_ids == frozenset(required)
    assert plan.total_cost == 5
    assert plan.action_ids == ("purge-index-and-template",)


def test_greedy_plan_never_claims_complete_with_uncovered_artifacts() -> None:
    required, actions = remediation_case(with_uncoverable=True)
    plan = greedy_plan(required, actions)
    assert not plan.complete
    assert plan.uncovered_artifact_ids == frozenset({"unknown-copy"})
```

Add the exact planning fixture to `tests/factories.py`:

```python
def remediation_case(
    *, with_uncoverable: bool = False
) -> tuple[frozenset[str], tuple[RemediationAction, ...]]:
    required = {"template", "index"}
    if with_uncoverable:
        required.add("unknown-copy")
    actions = (
        RemediationAction("purge-template", frozenset({"template"}), 4, ArtifactState.ERASED),
        RemediationAction("purge-index", frozenset({"index"}), 3, ArtifactState.ERASED),
        RemediationAction(
            "purge-index-and-template",
            frozenset({"template", "index"}),
            5,
            ArtifactState.ERASED,
        ),
    )
    return frozenset(required), actions
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/test_planning.py tests/test_planning_properties.py -v`

Expected: import failure for `erasemap.planning`.

- [ ] **Step 3: Implement deterministic solvers**

`exact_plan` uses branch-and-bound over actions sorted by id, tracks current coverage and cost, prunes branches whose cost is not lower than the best complete plan, and rejects more than 30 candidate actions with a clear instruction to use `greedy_plan`.

`greedy_plan` repeatedly selects the permitted action with minimum `(cost / newly_covered_count, action_id)`. Both solvers must preserve the distinction between erasure and processing restriction, reject actions prohibited by retention policy, and return uncovered artifacts explicitly.

- [ ] **Step 4: Run unit and property tests**

Use Hypothesis to compare `exact_plan` against exhaustive combinations for generated cases containing at most eight actions.

Run: `.venv/bin/pytest tests/test_planning.py tests/test_planning_properties.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit remediation planning**

```bash
git add src/erasemap/planning.py tests/test_planning.py tests/test_planning_properties.py tests/factories.py
git commit -m "feat: plan cost-aware erasure remediation"
```

### Task 7: Generate seeded systems and inject labeled faults

**Files:**
- Create: `src/erasemap/generator.py`
- Create: `tests/test_generator.py`
- Create: `examples/five_branch_system.json`

- [ ] **Step 1: Write failing determinism tests**

```python
from erasemap.codec import graph_to_json
from erasemap.generator import FaultKind, generate_case


def test_generation_is_byte_deterministic() -> None:
    left = generate_case(seed=17, node_count=100, faults=(FaultKind.ORPHANED_TEMPLATE,))
    right = generate_case(seed=17, node_count=100, faults=(FaultKind.ORPHANED_TEMPLATE,))
    assert graph_to_json(left.graph) == graph_to_json(right.graph)
    assert left.truth == right.truth


def test_injected_fault_is_present_in_ground_truth() -> None:
    case = generate_case(seed=3, node_count=20, faults=(FaultKind.REPLAYED_RECEIPT,))
    assert case.truth.faults[0].kind is FaultKind.REPLAYED_RECEIPT
    assert case.truth.has_prohibited_residual
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/test_generator.py -v`

Expected: import failure for `erasemap.generator`.

- [ ] **Step 3: Implement seeded topology templates and fault mutations**

Use a local `random.Random(seed)` only. Implement at least three topology families: government identity proofing, bank KYC, and school access. Implement every fault class named in the design spec. Return a `GeneratedCase` containing graph, evidence, actions, policies, and ground truth inaccessible to the auditor.

Generate `examples/five_branch_system.json` from a fixed seed through the codec rather than hand-editing JSON.

- [ ] **Step 4: Run determinism and size tests**

Run: `.venv/bin/pytest tests/test_generator.py -v`

Expected: all tests pass for 10, 100, 1,000, and 10,000-node generation.

- [ ] **Step 5: Commit the controlled benchmark generator**

```bash
git add src/erasemap/generator.py tests/test_generator.py examples/five_branch_system.json
git commit -m "feat: generate seeded erasure fault scenarios"
```

### Task 8: Add fixed baselines and honest benchmark metrics

**Files:**
- Create: `src/erasemap/baselines.py`
- Create: `src/erasemap/metrics.py`
- Create: `tests/test_baselines.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing metric tests**

```python
from erasemap.metrics import TrialOutcome, aggregate_outcomes


def test_false_complete_rate_uses_only_positive_truth_cases() -> None:
    report = aggregate_outcomes(
        [
            TrialOutcome(True, True, 1.0, 1.0),
            TrialOutcome(True, False, 1.0, 1.0),
            TrialOutcome(False, True, 1.0, 1.0),
        ]
    )
    assert report.false_complete_rate == 0.5
    assert report.positive_trials == 2
```

Add baseline tests proving receipt-only trusts a valid signature, checklist cannot see an unlisted store, and untyped traversal cannot accept type-specific evidence as equivalent.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/test_baselines.py tests/test_metrics.py -v`

Expected: import failures for both modules.

- [ ] **Step 3: Implement baselines and metrics**

Expose each baseline through the same `AuditMethod` protocol. Aggregate confusion counts, false-complete rate, recall, precision, false-alarm rate, exact-node recall, runtime, and remediation cost. Compute deterministic percentile-bootstrap 95% intervals from an explicit seed; return `None` intervals when the denominator is zero instead of inventing a value.

- [ ] **Step 4: Run baseline and metric tests**

Run: `.venv/bin/pytest tests/test_baselines.py tests/test_metrics.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit comparative evaluation primitives**

```bash
git add src/erasemap/baselines.py src/erasemap/metrics.py tests/test_baselines.py tests/test_metrics.py
git commit -m "feat: add baselines and false-complete metrics"
```

### Task 9: Create privacy-minimized signed receipts

**Files:**
- Create: `src/erasemap/receipts.py`
- Create: `tests/test_receipts.py`

- [ ] **Step 1: Write failing signature and replay tests**

```python
from erasemap.receipts import ReceiptLedger, generate_keypair, issue_receipt, verify_receipt


def test_receipt_binds_request_and_graph_root() -> None:
    private_key, public_key = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "graph-root-1", "INCOMPLETE", 100)
    assert verify_receipt(public_key, receipt, ReceiptLedger()).valid
    altered = receipt.with_graph_root("graph-root-2")
    assert not verify_receipt(public_key, altered, ReceiptLedger()).valid


def test_receipt_nonce_cannot_be_replayed() -> None:
    private_key, public_key = generate_keypair()
    receipt = issue_receipt(private_key, "request-1", "root", "COMPLETE", 100)
    ledger = ReceiptLedger()
    assert verify_receipt(public_key, receipt, ledger).valid
    ledger.record(receipt.nonce)
    assert verify_receipt(public_key, receipt, ledger).reason == "replayed nonce"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/pytest tests/test_receipts.py -v`

Expected: import failure for `erasemap.receipts`.

- [ ] **Step 3: Implement Ed25519 receipts**

Sign canonical JSON containing schema version, request id, graph-root commitment, audit status, issued timestamp, nonce, and previous-receipt hash. Exclude subject ids, biometric values, raw paths, evidence contents, and free text. Verification checks schema, signature, expected public key, timestamp bounds, chain link, and nonce replay.

- [ ] **Step 4: Run cryptographic tests**

Run: `.venv/bin/pytest tests/test_receipts.py -v`

Expected: all tests pass, including one-bit signature, payload, and chain mutations.

- [ ] **Step 5: Commit receipt integrity support**

```bash
git add src/erasemap/receipts.py tests/test_receipts.py
git commit -m "feat: issue privacy-minimized erasure receipts"
```

### Task 10: Build the frozen benchmark runner

**Files:**
- Create: `src/erasemap/benchmark.py`
- Create: `tests/test_benchmark.py`
- Create: `benchmark/protocol-v1.json`

- [ ] **Step 1: Write failing reproducibility tests**

```python
from erasemap.benchmark import load_protocol, run_protocol


def test_protocol_report_is_reproducible(tmp_path) -> None:
    protocol = load_protocol("benchmark/protocol-v1.json")
    left = run_protocol(protocol, output_dir=tmp_path / "left")
    right = run_protocol(protocol, output_dir=tmp_path / "right")
    assert left.canonical_results == right.canonical_results
    assert left.protocol_hash == right.protocol_hash
```

- [ ] **Step 2: Run test and verify failure**

Run: `.venv/bin/pytest tests/test_benchmark.py -v`

Expected: import failure for `erasemap.benchmark`.

- [ ] **Step 3: Implement the protocol schema and runner**

`protocol-v1.json` fixes schema version, topology families, development and holdout seed ranges, graph-size strata, fault matrix, methods, bootstrap seed, and primary endpoint. The runner writes:

- `manifest.json` with code revision and protocol hash;
- `trials.jsonl` with one canonical record per method-trial pair;
- `summary.json` with aggregate metrics and confidence intervals;
- `failures.jsonl` with exceptions and excluded trials, never silently dropped.

The holdout command refuses to run when the working tree is dirty and writes a one-time lock file containing the protocol and commit hashes.

- [ ] **Step 4: Run deterministic benchmark tests**

Run: `.venv/bin/pytest tests/test_benchmark.py -v`

Expected: all tests pass using a small test protocol.

- [ ] **Step 5: Commit the frozen runner**

```bash
git add src/erasemap/benchmark.py tests/test_benchmark.py benchmark/protocol-v1.json
git commit -m "feat: add frozen EraseMap benchmark runner"
```

### Task 11: Expose the complete workflow through the CLI

**Files:**
- Create: `src/erasemap/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
import json
import subprocess


def test_audit_command_emits_machine_readable_status(tmp_path) -> None:
    result = subprocess.run(
        ["erasemap", "audit", "examples/five_branch_system.json", "--subject", "subject-1"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "INCOMPLETE"
    assert payload["shortest_path"][0] == "source"
```

- [ ] **Step 2: Run test and verify the entry point fails**

Run: `.venv/bin/pytest tests/test_cli.py -v`

Expected: failure because `erasemap.cli` does not exist.

- [ ] **Step 3: Implement subcommands with `argparse`**

Commands:

- `erasemap generate --seed N --nodes N --fault NAME --output PATH`
- `erasemap audit GRAPH --subject ID [--evidence PATH]`
- `erasemap plan GRAPH --subject ID --actions PATH --solver exact|greedy`
- `erasemap receipt issue|verify ...`
- `erasemap benchmark dev|holdout --protocol PATH --output DIR`

Write canonical JSON to stdout, diagnostics to stderr, return code 0 for completed commands, 2 for invalid input, and 3 for an invalid receipt. `INCOMPLETE` is a valid audit outcome and therefore not a process error.

- [ ] **Step 4: Run CLI integration tests**

Run: `.venv/bin/pytest tests/test_cli.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the executable workflow**

```bash
git add src/erasemap/cli.py tests/test_cli.py
git commit -m "feat: expose EraseMap audit workflow via CLI"
```

### Task 12: Document, verify, and record the core milestone

**Files:**
- Create: `docs/CORE_PROTOCOL.md`
- Modify: `README.md`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write protocol documentation with claim boundaries**

Document the graph schema, evidence contracts, audit states, primary endpoint, baseline definitions, receipt boundary, deterministic commands, and explicit statement that registered-graph coverage does not prove global physical erasure. Include the fixed five-branch example and label every number as a test fixture or measured benchmark output.

- [ ] **Step 2: Add CI gates**

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e '.[dev]'
      - run: ruff check .
      - run: mypy src/erasemap
      - run: pytest --cov=erasemap --cov-report=term-missing --cov-fail-under=90
```

- [ ] **Step 3: Run the complete local gate**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/erasemap
.venv/bin/pytest --cov=erasemap --cov-report=term-missing --cov-fail-under=90
.venv/bin/erasemap audit examples/five_branch_system.json --subject subject-1
```

Expected: lint, types, and tests pass; the example audit returns canonical JSON with `status` equal to `INCOMPLETE` and a concrete shortest residual path.

- [ ] **Step 4: Run the development benchmark only**

Run: `.venv/bin/erasemap benchmark dev --protocol benchmark/protocol-v1.json --output outputs/dev-v1`

Expected: manifest, trial, summary, and failure files are created. Do not run the locked holdout until the EraseTwin plan and prior-art review determine whether the protocol needs amendment.

- [ ] **Step 5: Commit the verified milestone**

```bash
git add README.md docs/CORE_PROTOCOL.md .github/workflows/ci.yml
git commit -m "docs: document and gate EraseMap core audit"
```

## Plan self-review

- Spec coverage in this sub-project: domain model, typed evidence, residual paths, remediation planning, generator, fixed baselines, primary statistics, signed receipts, CLI, reproducibility, and claim boundaries are assigned to explicit tasks.
- Deferred by intentional decomposition: EraseTwin training experiments and the offline web demonstration each require their own approved implementation plan and independent test gates.
- Type consistency: `Artifact`, `Evidence`, `ErasureGraph`, `AuditResult`, and `RemediationPlan` are defined once in Task 2 and consumed without alternate names.
- Holdout safety: only the development benchmark runs in this plan; the holdout is locked and must remain unopened while research decisions can still change.
- No target threshold is described as an observed result.
