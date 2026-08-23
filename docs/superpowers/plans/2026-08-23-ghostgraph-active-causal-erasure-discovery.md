# GhostGraph Active Causal Erasure Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an exact fail-closed system that actively discovers a bounded hidden data-resurrection graph, reports complete equivalence classes, bridges justified paths into TRE controls, and validates the contract prospectively in an abstract lab and live stock services.

**Architecture:** The pure core enumerates canonical graph hypotheses and exact experiment traces. A deterministic one-step minimax planner chooses interventions, while an independently structured packed-bit oracle checks every scientific decision. Prospective runners, live adapters, Lean proofs, and CI sit outside the pure core and preserve explicit evidence boundaries.

**Tech Stack:** Python 3.11+, frozen dataclasses, enums, exhaustive finite search, pytest/Hypothesis, strict mypy, Ruff, Docker stock services, Lean 4, JSON protocols and provenance bundles.

---

## File map

- `src/erasemap/ghostgraph.py`: graph domain, temporal trace prediction, version-space update,
  evidence, verdicts, and canonical path signatures.
- `src/erasemap/ghostgraph_planner.py`: exact experiment partitions, minimax scores, and selection
  certificates.
- `src/erasemap/ghostgraph_oracle.py` and `ghostgraph_conformance.py`: independent packed-bit oracle
  and exhaustive comparison.
- `src/erasemap/ghostgraph_bridge.py` and `ghostgraph_lab.py`: PCUG/TRE translation and deterministic
  state replay.
- `experiments/run_ghostgraph_v1.py`: prospective internal hidden-graph runner.
- `experiments/ghostgraph_services.py` and `run_ghostgraph_live_v1.py`: live stock-service layer.
- `external_ghostgraph_challenge/`: external-author sealing, execution, and verification kit.
- `EraseMapFormal/GhostGraph.lean`: finite filtering, separation, and minimax theorems.
- `scripts/verify_ghostgraph_*.py`: independent artifact gates.

### Task 1: Canonical graph domain and trace semantics

**Files:**
- Create: `src/erasemap/ghostgraph.py`
- Create: `tests/test_ghostgraph.py`

- [ ] **Step 1: Write failing domain and prediction tests**

```python
def test_predicts_multihop_recurrence_trace() -> None:
    graph = graph_with_edges(("backup", "db"), ("db", "worker"), ("worker", "vector"))
    experiment = experiment_enabling("restore", "sync", checkpoints=("db", "vector"))
    assert predict_trace(graph, experiment).bits == (True, True)


def test_rejects_noncanonical_nodes() -> None:
    with pytest.raises(ValueError):
        GraphHypothesis(nodes=(node("b"), node("a")), edges=())
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph.py -q`

Expected: collection fails because `erasemap.ghostgraph` does not exist.

- [ ] **Step 3: Implement immutable validated types and exact reachability**

Implement `GraphNode`, `GraphEdge`, `GraphHypothesis`, `DiscoveryExperiment`, `ObservationTrace`,
`DiscoveryEvidence`, `ExecutedObservation`, `DiscoveryReport`, and this fixed verdict enum:

```python
class DiscoveryVerdict(StrEnum):
    NO_OBSERVED_RECURRENCE = "NO_OBSERVED_RECURRENCE"
    GRAPH_DISCOVERED = "GRAPH_DISCOVERED"
    PATH_CLASS_DISCOVERED = "PATH_CLASS_DISCOVERED"
    EQUIVALENCE_CLASS = "EQUIVALENCE_CLASS"
    OUT_OF_HYPOTHESIS = "OUT_OF_HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"
```

Require sorted unique IDs, endpoints inside the node universe, at most eight nodes and twelve
optional edges, and declared time buckets/checkpoints. `predict_trace` advances a subject-state
frontier bucket by bucket through only experiment-enabled transitions.

- [ ] **Step 4: Add version-space and path-signature tests**

Test singleton discovery, complete equivalence classes, empty version space, missing evidence,
no-recurrence scope, trace mismatch, and identical relevant path signatures with irrelevant graph
differences. Assert that no function chooses an arbitrary graph representative.

- [ ] **Step 5: Implement exact update and terminal verdicts**

```python
def update_version_space(
    hypotheses: tuple[GraphHypothesis, ...],
    observations: tuple[ExecutedObservation, ...],
    evidence: DiscoveryEvidence,
) -> DiscoveryReport: ...
```

The report contains all surviving graph IDs, path/control signatures, and the shortest inconsistency
when no graph survives. `PATH_CLASS_DISCOVERED` requires exact signature equality across survivors.

- [ ] **Step 6: Run tests, lint, and commit**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph.py -q`

Run: `.venv/bin/python -m ruff check src/erasemap/ghostgraph.py tests/test_ghostgraph.py`

```bash
git add src/erasemap/ghostgraph.py tests/test_ghostgraph.py
git commit -m "feat: add fail-closed GhostGraph domain"
```

### Task 2: Exact active minimax planner

**Files:**
- Create: `src/erasemap/ghostgraph_planner.py`
- Create: `tests/test_ghostgraph_planner.py`

- [ ] **Step 1: Write failing planner tests**

```python
def test_selects_smallest_worst_case_partition() -> None:
    certificate = select_next_experiment(hypotheses, experiments, used_ids=())
    assert certificate.selected_experiment_id == "balanced"
    assert certificate.selected_score == PlannerScore(2, 8, 3, "balanced")


def test_stops_when_graphs_are_not_separable() -> None:
    certificate = select_next_experiment(equivalent_graphs, experiments, used_ids=())
    assert certificate.selected_experiment_id is None
```

- [ ] **Step 2: Verify tests fail**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph_planner.py -q`

Expected: missing module failure.

- [ ] **Step 3: Implement exact partitions and certificates**

Add `ExperimentPartition`, `PlannerScore`, `PlannerCandidate`, and `PlannerCertificate`. Compute the
score exactly as `(largest bucket, sum of squared bucket sizes, declared cost, experiment ID)` and
select the lexicographic minimum only when the query separates a surviving graph pair.

- [ ] **Step 4: Test order invariance, caps, and tie-breaking**

Shuffle hypotheses and experiments, check byte-identical canonical certificates, reject more than
4,096 hypotheses or 32 experiments, and assert every partition includes each graph exactly once.

- [ ] **Step 5: Run and commit**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph_planner.py -q`

```bash
git add src/erasemap/ghostgraph_planner.py tests/test_ghostgraph_planner.py
git commit -m "feat: choose exact GhostGraph interventions"
```

### Task 3: Independent oracle and exhaustive conformance

**Files:**
- Create: `src/erasemap/ghostgraph_oracle.py`
- Create: `src/erasemap/ghostgraph_conformance.py`
- Create: `scripts/verify_ghostgraph_conformance.py`
- Create: `tests/test_ghostgraph_conformance.py`
- Create: `formal/ghostgraph-conformance-v1.json`

- [ ] **Step 1: Write independence and deliberate-mismatch tests**

Assert that oracle source does not import production prediction, update, planner, or path functions.
Inject a wrong production trace and require a nonzero mismatch.

- [ ] **Step 2: Implement packed-bit oracle independently**

Represent optional edges and reached nodes as integers and traces as packed bits. Reimplement
temporal reachability, Hamming filtering, path-signature comparison, partitions, and minimax choice
without calling production scientific functions.

- [ ] **Step 3: Implement and freeze the exhaustive sweep**

Enumerate tiny grammars, hidden graphs, input orderings, evidence masks, equivalent classes, and
outside-prediction traces. Emit verdict counts, mismatches, case count, and record SHA-256.

Run:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/verify_ghostgraph_conformance.py \
  --output /tmp/ghostgraph-conformance-v1.json
```

Insert the canonical output into `formal/ghostgraph-conformance-v1.json` using `apply_patch`, then
rerun with `--expected`. Expected: `mismatches: 0`.

- [ ] **Step 4: Commit**

```bash
git add src/erasemap/ghostgraph_oracle.py src/erasemap/ghostgraph_conformance.py \
  scripts/verify_ghostgraph_conformance.py tests/test_ghostgraph_conformance.py \
  formal/ghostgraph-conformance-v1.json
git commit -m "test: freeze GhostGraph conformance"
```

### Task 4: PCUG/TRE bridge and abstract state lab

**Files:**
- Create: `src/erasemap/ghostgraph_bridge.py`
- Create: `src/erasemap/ghostgraph_lab.py`
- Create: `tests/test_ghostgraph_bridge.py`
- Create: `tests/test_ghostgraph_lab.py`

- [ ] **Step 1: Write failing bridge tests**

Test that `backup -> database -> worker -> vector` becomes typed PCUG transitions, unresolved graph
classes become separate TRE scenarios, and non-confident reports cannot produce controls.

- [ ] **Step 2: Implement the exact bridge**

```python
def build_topology_envelope(
    report: DiscoveryReport,
    graph_by_id: Mapping[str, GraphHypothesis],
) -> TopologyUncertaintyEnvelope: ...
```

Preserve edge type, operation, source, target, and witness. Call
`exact_robust_stabilization_cut` only after complete transition coverage is verified.

- [ ] **Step 3: Test and implement physical state replay**

Use four mutable carrier states. Establish uncontrolled recurrence, nominal-control failure on a
multi-hop graph, TRE success, and zero retained-subject loss. Record real before/after state rather
than returning predetermined flags.

- [ ] **Step 4: Run and commit**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph_bridge.py tests/test_ghostgraph_lab.py -q`

```bash
git add src/erasemap/ghostgraph_bridge.py src/erasemap/ghostgraph_lab.py \
  tests/test_ghostgraph_bridge.py tests/test_ghostgraph_lab.py
git commit -m "feat: connect GhostGraph discovery to TRE"
```

### Task 5: Preregister GhostGraph v1 before runner and reveal

**Files:**
- Create: `benchmark/ghostgraph-v1.json`
- Create: `docs/GHOSTGRAPH_V1_PREREGISTRATION.md`
- Create: `tests/test_ghostgraph_protocol.py`

- [ ] **Step 1: Write protocol-schema tests**

Require schema, domain caps, `e = 0`, graph-generator hash, disjoint development seeds, reveal
commitment, costs, stopping rule, metrics, gates, invalid-run rules, baseline budgets, core files,
and claim boundary.

- [ ] **Step 2: Create the frozen protocol and preregistration**

Use schema `erasemap-ghostgraph-v1`; include unique graphs, indistinguishable pairs, path classes,
outside-prediction cases, missing evidence, and cross-contamination. State explicitly that graphs and
mappings are project-authored and any post-reveal change creates v2.

- [ ] **Step 3: Verify and commit preregistration separately**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph_protocol.py -q`

```bash
git add benchmark/ghostgraph-v1.json docs/GHOSTGRAPH_V1_PREREGISTRATION.md \
  tests/test_ghostgraph_protocol.py
git commit -m "docs: preregister GhostGraph v1"
```

Do not create the runner or reveal in this commit.

### Task 6: Prospective runner, verifier, reveal, and one-shot result

**Files:**
- Create: `experiments/run_ghostgraph_v1.py`
- Create: `scripts/verify_ghostgraph_v1.py`
- Create: `tests/test_ghostgraph_result.py`
- Create after runner commit: `benchmark/ghostgraph-v1-reveal.json`
- Create after the run: `outputs/ghostgraph-v1/result.json`
- Create after the run: `outputs/ghostgraph-v1/trials.jsonl`
- Create after the run: `outputs/ghostgraph-v1/PROVENANCE.json`

- [ ] **Step 1: Write runner/verifier tests with development seeds**

Test append-only output, core/protocol/reveal drift, exact stopping, equal baseline budgets, metric
recomputation, artifact hashes, and rejection of changed gates.

- [ ] **Step 2: Implement runner and independent verifier**

The runner repeatedly filters, records the full planner certificate, executes the selected abstract
experiment, and stops only on a valid terminal verdict. Compare passive lineage, frozen random,
greedy-pair, exhaustive, and ET baselines under frozen budgets. The verifier recomputes everything
and never trusts the stored `passed` field.

- [ ] **Step 3: Commit runner before reveal**

```bash
git add experiments/run_ghostgraph_v1.py scripts/verify_ghostgraph_v1.py \
  tests/test_ghostgraph_result.py
git commit -m "feat: add prospective GhostGraph runner"
```

- [ ] **Step 4: Commit reveal only after verifying its preregistered digest**

```bash
git add benchmark/ghostgraph-v1-reveal.json
git commit -m "data: reveal GhostGraph v1 hidden graphs"
```

- [ ] **Step 5: Execute once, verify, and preserve the observed result**

```bash
PYTHONPATH=src:. .venv/bin/python experiments/run_ghostgraph_v1.py \
  --protocol benchmark/ghostgraph-v1.json \
  --reveal benchmark/ghostgraph-v1-reveal.json \
  --output outputs/ghostgraph-v1
PYTHONPATH=src:. .venv/bin/python scripts/verify_ghostgraph_v1.py
```

Do not change code or gates after observing the result. Commit PASS or FAIL as obtained.

- [ ] **Step 6: Commit the immutable result bundle**

```bash
git add -f outputs/ghostgraph-v1/result.json outputs/ghostgraph-v1/trials.jsonl \
  outputs/ghostgraph-v1/PROVENANCE.json
git commit -m "data: record GhostGraph v1 result"
```

### Task 7: Lean formalization

**Files:**
- Create: `EraseMapFormal/GhostGraph.lean`
- Modify: `EraseMapFormal.lean`
- Modify: `formal/README.md`
- Create: `tests/test_ghostgraph_formal.py`

- [ ] **Step 1: Add a failing source-contract test**

Require `true_graph_survives`, `singleton_discovery_sound`, `inseparable_class_fail_closed`, and
`selected_query_minimax`; reject `sorry`, `admit`, and custom `axiom` declarations.

- [ ] **Step 2: Formalize finite filtering, partitions, and the four claims**

Use finite hypothesis lists and Boolean-vector observations. Prove preservation and singleton
soundness by membership, inseparability relative to the frozen query language, and minimax relative
to the finite candidate list. Do not claim globally optimal adaptive-tree depth.

- [ ] **Step 3: Build and commit**

Run: `lake build --wfail`

Run: `rg -n "sorry|admit|axiom" EraseMapFormal/GhostGraph.lean`

Expected: build succeeds and the search has no matches.

```bash
git add EraseMapFormal/GhostGraph.lean EraseMapFormal.lean formal/README.md \
  tests/test_ghostgraph_formal.py
git commit -m "proof: formalize bounded GhostGraph discovery"
```

### Task 8: Preregister and execute live four-service transfer

**Files:**
- Create first: `benchmark/ghostgraph-live-v1.json`
- Create first: `docs/GHOSTGRAPH_LIVE_V1_PREREGISTRATION.md`
- Create after protocol commit: `experiments/ghostgraph_services.py`
- Create after protocol commit: `experiments/run_ghostgraph_live_v1.py`
- Create after protocol commit: `scripts/verify_ghostgraph_live_v1.py`
- Create: `tests/test_ghostgraph_services.py`
- Create after run: `outputs/ghostgraph-live-v1/result.json`
- Create after run: `outputs/ghostgraph-live-v1/PROVENANCE.json`

- [ ] **Step 1: Freeze and commit live protocol before runner code**

Use these existing digest-pinned images: Redis
`e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2`, Keycloak
`f1f1f01e472c8a78df40d8f2a49a925274eda4d3d80d5f6edbb5c880ee3c01c6`, MLflow
`9f9276e57cda1593cfa0fe8519145cd49328e119e85951851b9244e82e3769be`, and Qdrant
`6ac4807063bbecddca0250bfbcff52acf18c22263b904d12919349e6d0a408f1`.
Freeze a multi-hop path, safe case, equivalent pair, outside-prediction case, observation window,
cleanup contract, and gates. Commit protocol and preregistration alone.

- [ ] **Step 2: Write fake-service safety and lifecycle tests**

Test loopback binding, digest enforcement, unique `erasemap-ghostgraph-` names, timeouts, failure
teardown, seed/delete/intervene/observe/reset, redaction, and refusal to manage unrelated containers.

- [ ] **Step 3: Implement live adapters and runner**

Reuse hardened `DockerService` patterns. Store only synthetic commitments and use real native service
operations. An orchestrated worker may copy commitments along enabled hidden edges, but recurrence
must be observed from destination APIs rather than inferred from worker return codes.

- [ ] **Step 4: Commit runner before the first live confirmatory execution**

```bash
git add experiments/ghostgraph_services.py experiments/run_ghostgraph_live_v1.py \
  scripts/verify_ghostgraph_live_v1.py tests/test_ghostgraph_services.py
git commit -m "feat: add live GhostGraph transfer"
```

- [ ] **Step 5: Execute once, verify, and confirm cleanup**

```bash
PYTHONPATH=src:. .venv/bin/python experiments/run_ghostgraph_live_v1.py \
  --protocol benchmark/ghostgraph-live-v1.json \
  --output outputs/ghostgraph-live-v1
PYTHONPATH=src:. .venv/bin/python scripts/verify_ghostgraph_live_v1.py
docker ps --format '{{.Names}}' --filter name=erasemap-ghostgraph-
```

Expected: the verifier reflects the frozen result and Docker prints no container names.

- [ ] **Step 6: Commit live evidence**

```bash
git add -f outputs/ghostgraph-live-v1/result.json \
  outputs/ghostgraph-live-v1/PROVENANCE.json
git commit -m "data: record live GhostGraph result"
```

### Task 9: External hidden-topology challenge kit

**Files:**
- Create: `external_ghostgraph_challenge/README.md`
- Create: `external_ghostgraph_challenge/protocol-v1.json`
- Create: `external_ghostgraph_challenge/schema.py`
- Create: `external_ghostgraph_challenge/seal.py`
- Create: `external_ghostgraph_challenge/run.py`
- Create: `external_ghostgraph_challenge/verify.py`
- Create: `tests/test_external_ghostgraph_challenge.py`

- [ ] **Step 1: Write seal, signature, and authorship tests**

Test external key generation, sealed truth commitments, answer-blind bundles, signature validation,
duplicate rejection, source drift, self-signature rejection, nine evidence gates, and explicit
`NOT_COLLECTED` when no external bundle exists.

- [ ] **Step 2: Implement and document the evaluator flow**

The external author supplies adapter endpoints, hidden graph, interventions, checkpoints, and truth
reveal. The runner calls the frozen public build without truth; verifier scores only after reveal and
records evaluator identity separately from project authorship.

- [ ] **Step 3: Test and commit without fabricating external evidence**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_external_ghostgraph_challenge.py -q`

```bash
git add external_ghostgraph_challenge tests/test_external_ghostgraph_challenge.py
git commit -m "feat: add external GhostGraph challenge kit"
```

### Task 10: Reports, papers, and claim audit

**Files:**
- Create: `docs/GHOSTGRAPH_V1_REPORT.md`
- Modify: `README.md`
- Modify: `docs/NOVELTY_AND_PRIOR_ART.md`
- Modify: `docs/STRUCTURED_PRIOR_ART_AND_PATENT_REVIEW.md`
- Modify: `docs/SCIENTIFIC_CLAIM_MATRIX.md`
- Modify: `docs/COMPETITION_EVIDENCE_SCORECARD.md`
- Modify: `docs/JUDGE_QA_RU.md`
- Modify: `docs/JURY_DEFENSE_RU.md`
- Modify: `src/erasemap/showcase.py`
- Modify: `tests/test_showcase.py`
- Modify and rebuild: both English/Russian scientific paper MD, DOCX, and PDF artifacts
- Create: `tests/test_ghostgraph_public_result.py`

- [ ] **Step 1: Write public-number and boundary tests**

Read committed result JSON and require every quoted number to match. Require `project-authored`,
`bounded grammar`, `not production`, and external status `NOT_COLLECTED`.

- [ ] **Step 2: Update exact prior art and explain the result bilingually**

Cover active causal discovery, network tomography, automated lineage, recovered-state verification,
dependency-aware erasure, and deletion-testing patents. Claim only the implemented composition.
Explain ET versus GhostGraph, version filtering, minimax selection, equivalence classes, results, and
limitations consistently in English and Russian.

- [ ] **Step 3: Rebuild and inspect papers**

Use the existing document build workflow, convert DOCX to PDF, verify A4 geometry, and use
`pdftotext` to find GhostGraph, limitations, and all result numbers.

- [ ] **Step 4: Add the evidence-backed judge demonstration**

Extend the existing showcase payload with deletion, observed recurrence, each selected experiment,
remaining hypothesis count, discovered path or full equivalence class, selected TRE controls, and
post-control replay. `tests/test_showcase.py` must assert that every displayed value comes from the
committed result bundle and that an equivalence class is never rendered as one graph.

- [ ] **Step 5: Test and commit**

Run: `PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ghostgraph_public_result.py tests/test_showcase.py -q`

```bash
git add README.md docs competition/paper src/erasemap/showcase.py tests/test_showcase.py \
  tests/test_ghostgraph_public_result.py
git commit -m "docs: report GhostGraph evidence"
```

### Task 11: CI, release reproduction, and delivery

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/reproduce_release.sh`

- [ ] **Step 1: Add deterministic GhostGraph gates**

CI verifies the committed result, reruns internal v1 into `/tmp`, compares conformance, tests the
external kit, builds the package, and builds Lean. Add opt-in release profile `ghostgraph-live`; core
does not require privileged Docker.

- [ ] **Step 2: Run the complete local gates**

```bash
PYTHONPATH=src:. .venv/bin/python -m ruff check .
PYTHONPATH=src:. .venv/bin/python -m mypy --strict \
  src pilot external_challenge external_temporal_challenge external_transfer \
  external_ghostgraph_challenge usability
PYTHONPATH=src:. .venv/bin/python -m pytest \
  --cov=erasemap --cov=external_challenge --cov=external_temporal_challenge \
  --cov=external_ghostgraph_challenge --cov=pilot \
  --cov-report=term-missing --cov-fail-under=90
.venv/bin/python -m build
lake build --wfail
ERASEMAP_PYTHON=.venv/bin/python scripts/reproduce_release.sh core
ERASEMAP_PYTHON=.venv/bin/python scripts/reproduce_release.sh ghostgraph-live
```

Expected: every command exits 0, coverage is at least 90%, and no live container remains.

- [ ] **Step 3: Commit CI integration**

```bash
git add .github/workflows/ci.yml scripts/reproduce_release.sh
git commit -m "ci: reproduce GhostGraph evidence"
```

- [ ] **Step 4: Finish and verify exact delivery**

Use `superpowers:finishing-a-development-branch`. Verify local HEAD equals `origin/main`,
ahead/behind is `0/0`, the worktree is clean, remote GhostGraph artifacts exist, and the exact GitHub
Actions run has successful `test` and `formal` jobs. Never mark external validation complete without
a genuine independently signed bundle.
