# PCUG and Counterfactual Deletion Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, fail-closed Proof-Carrying Unlearning Graph core that computes and independently verifies minimum-cost counterfactual deletion cuts without rewriting existing EraSeMap evidence.

**Architecture:** New immutable PCUG types represent request-scoped physical and influence edges, verification channels, transitions, plans, and three-valued verdicts. A pure evaluator replays actions and determines path/risk feasibility; brute force is the correctness oracle, branch-and-bound is the exact solver, and a deterministic greedy solver is a named approximation. A canonical proof bundle contains enough committed input and raw verifier evidence for a separate checker to recompute the verdict.

**Tech Stack:** Python 3.11+, frozen dataclasses, standard-library graph/search/hash/JSON tools, Ed25519 from `cryptography`, pytest, Hypothesis, Ruff, mypy, Hatch.

---

## File map

- Create `src/erasemap/pcug_domain.py`: strict immutable PCUG enums and value objects.
- Create `src/erasemap/multiview_verifier.py`: channel validation and fail-closed composition.
- Create `src/erasemap/cdc.py`: graph replay, path feasibility, brute-force oracle, exact CDC, and greedy CDC.
- Create `src/erasemap/proof_bundle.py`: canonical encoding, commitments, signing, and independent checking.
- Create `src/erasemap/pcug_benchmark.py`: deterministic controlled cases and baseline evaluation.
- Create `src/erasemap/pcug_model_adapter.py`: strict import of existing v3 model evidence as request-scoped channels.
- Create `src/erasemap/pcug_adapters.py`: application-labelled simulator adapters over identical core semantics.
- Modify `src/erasemap/cli.py`: `pcug demo` and `pcug verify` commands.
- Create `benchmark/pcug-protocol-v1.json`: development-only deterministic protocol; no locked result is opened during implementation.
- Create `examples/pcug-faceid-style.json`: clearly labelled synthetic example.
- Create `tests/test_pcug_domain.py`: domain validation tests.
- Create `tests/test_multiview_verifier.py`: three-valued verifier tests.
- Create `tests/test_cdc.py`: replay, feasibility, oracle, exact, and greedy unit tests.
- Create `tests/pcug_factories.py`: deterministic shared fixtures used by CDC and proof tests.
- Create `tests/test_cdc_properties.py`: exhaustive/property equivalence and fail-closed invariants.
- Create `tests/test_proof_bundle.py`: canonicalization, tamper, signature, and independent-replay tests.
- Create `tests/test_pcug_benchmark.py`: deterministic benchmark and baseline tests.
- Create `tests/test_pcug_model_adapter.py`: model-evidence provenance and threshold tests.
- Create `tests/test_pcug_adapters.py`: cross-adapter semantic-equivalence tests.
- Modify `README.md`: measured/proposed boundary and reproduction commands.
- Modify `docs/NOVELTY_AND_PRIOR_ART.md`: precise PCUG novelty boundary without priority claims.
- Create `docs/PCUG_PROTOCOL.md`: frozen semantics and field reference.

## Task 1: Immutable PCUG domain and validation

**Files:**
- Create: `src/erasemap/pcug_domain.py`
- Test: `tests/test_pcug_domain.py`

- [ ] **Step 1: Write failing validation tests**

```python
import math
import pytest

from erasemap.pcug_domain import ChannelDecision, ChannelResult, EdgeState, PCUGEdge


def test_unknown_edge_is_not_closed() -> None:
    edge = PCUGEdge("source", "model", "USED_TO_TRAIN", EdgeState.UNKNOWN, True)
    assert edge.state is EdgeState.UNKNOWN


def test_channel_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        ChannelResult("mia", math.nan, 0.2, 0.1, ChannelDecision.FAIL, True)
```

- [ ] **Step 2: Run tests and verify the module is missing**

Run: `.venv/bin/pytest tests/test_pcug_domain.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'erasemap.pcug_domain'`.

- [ ] **Step 3: Implement strict value objects**

```python
class EdgeState(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class ChannelDecision(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ChannelResult:
    name: str
    value: float
    upper_bound: float
    threshold: float
    decision: ChannelDecision
    mandatory: bool

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("channel name is required")
        if not all(math.isfinite(value) for value in (self.value, self.upper_bound, self.threshold)):
            raise ValueError("channel values must be finite")
```

Add validated frozen types for `PCUGNode`, `PCUGEdge`, `PCUGGraph`, `Transition`, `CDCAction`,
`CDCProtocol`, `CDCPlan`, `FeasibilityReport`, and `PCUGVerdict`. Use tuples/frozensets and reject
duplicate IDs, unknown endpoints, negative costs, missing source/sink IDs, invalid influence-edge
metadata, and thresholds with the wrong direction.

- [ ] **Step 4: Run focused quality gates**

Run: `.venv/bin/pytest tests/test_pcug_domain.py -q && .venv/bin/ruff check src/erasemap/pcug_domain.py tests/test_pcug_domain.py && .venv/bin/mypy src/erasemap/pcug_domain.py`

Expected: all commands exit `0`.

- [ ] **Step 5: Commit the domain slice**

```bash
git add src/erasemap/pcug_domain.py tests/test_pcug_domain.py
git commit -m "feat: define strict pcug domain"
```

## Task 2: Fail-closed multi-view verifier

**Files:**
- Create: `src/erasemap/multiview_verifier.py`
- Test: `tests/test_multiview_verifier.py`

- [ ] **Step 1: Write failing composition tests**

```python
from erasemap.multiview_verifier import compose_channels
from erasemap.pcug_domain import ChannelDecision, ChannelResult, PCUGVerdict


def channel(name: str, decision: ChannelDecision, mandatory: bool = True) -> ChannelResult:
    return ChannelResult(name, 0.05, 0.08, 0.10, decision, mandatory)


def test_mandatory_unknown_prevents_complete() -> None:
    result = compose_channels((channel("storage", ChannelDecision.PASS), channel("mia", ChannelDecision.UNKNOWN)))
    assert result.verdict is PCUGVerdict.UNVERIFIED


def test_any_mandatory_failure_is_incomplete() -> None:
    result = compose_channels((channel("storage", ChannelDecision.PASS), channel("mia", ChannelDecision.FAIL)))
    assert result.verdict is PCUGVerdict.INCOMPLETE
```

- [ ] **Step 2: Verify the tests fail for the missing module**

Run: `.venv/bin/pytest tests/test_multiview_verifier.py -q`

Expected: collection fails on the missing `multiview_verifier` module.

- [ ] **Step 3: Implement deterministic conjunction**

```python
def compose_channels(channels: tuple[ChannelResult, ...]) -> VerificationSummary:
    names = [channel.name for channel in channels]
    if len(names) != len(set(names)):
        raise ValueError("duplicate verification channel")
    mandatory = tuple(channel for channel in channels if channel.mandatory)
    if not mandatory or any(item.decision is ChannelDecision.FAIL for item in mandatory):
        verdict = PCUGVerdict.INCOMPLETE
    elif any(item.decision is ChannelDecision.UNKNOWN for item in mandatory):
        verdict = PCUGVerdict.UNVERIFIED
    else:
        verdict = PCUGVerdict.COMPLETE
    return VerificationSummary(tuple(sorted(channels, key=lambda item: item.name)), verdict)
```

Implement upper-bound and equivalence-margin constructors that recompute decisions from raw values;
reject a caller-supplied decision inconsistent with its registered threshold.

- [ ] **Step 4: Run focused tests, lint, and typing**

Run: `.venv/bin/pytest tests/test_multiview_verifier.py -q && .venv/bin/ruff check src/erasemap/multiview_verifier.py tests/test_multiview_verifier.py && .venv/bin/mypy src/erasemap/multiview_verifier.py`

Expected: all commands exit `0`.

- [ ] **Step 5: Commit verifier composition**

```bash
git add src/erasemap/multiview_verifier.py tests/test_multiview_verifier.py
git commit -m "feat: compose multiview deletion evidence"
```

## Task 3: Pure transition replay and active-path evaluation

**Files:**
- Create: `src/erasemap/cdc.py`
- Test: `tests/test_cdc.py`

- [ ] **Step 1: Write failing path-closure tests**

```python
from erasemap.cdc import evaluate_actions
from erasemap.pcug_domain import EdgeState, PCUGVerdict
from tests.pcug_factories import forked_pcug_case


def test_deleting_parent_does_not_close_materialized_child() -> None:
    graph, protocol, actions = forked_pcug_case()
    report = evaluate_actions(graph, protocol, (actions["erase-source"],))
    assert report.verdict is PCUGVerdict.INCOMPLETE
    assert report.shortest_active_path == ("subject", "embedding", "api")


def test_unknown_influence_edge_prevents_complete() -> None:
    graph, protocol, actions = forked_pcug_case(model_edge_state=EdgeState.UNKNOWN)
    report = evaluate_actions(graph, protocol, (actions["purge-derived"],))
    assert report.verdict is PCUGVerdict.UNVERIFIED
```

Create `tests/pcug_factories.py` in this task with an eight-node subject/source/embedding/index/cache/
backup/model/API graph and deterministic erase, rebuild, invalidate, destroy-key, block, and unlearn
actions.

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/test_cdc.py -q`

Expected: import fails because `evaluate_actions` is not implemented.

- [ ] **Step 3: Implement replay and path enumeration**

```python
def evaluate_actions(
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
) -> FeasibilityReport:
    state = graph
    for action in sorted(actions, key=lambda item: item.id):
        state = apply_transition(state, action)
    paths = active_paths(state, protocol.source_ids, protocol.sink_ids)
    unknown = unknown_reachable_edges(state, protocol.source_ids)
    verification = compose_channels(state.channel_results)
    if paths or verification.verdict is PCUGVerdict.INCOMPLETE:
        verdict = PCUGVerdict.INCOMPLETE
    elif unknown or verification.verdict is PCUGVerdict.UNVERIFIED:
        verdict = PCUGVerdict.UNVERIFIED
    else:
        verdict = PCUGVerdict.COMPLETE
    return FeasibilityReport(state, verdict, paths, min(paths, key=lambda p: (len(p), p)) if paths else None)
```

Use strongly connected components to condense cycles before enumerating source-to-sink paths. Reject
an action whose observed transition does not match its committed action ID, and preserve the original
graph because all data structures are immutable.

- [ ] **Step 4: Run focused and legacy regression tests**

Run: `.venv/bin/pytest tests/test_cdc.py tests/test_audit.py tests/test_planning.py -q`

Expected: all tests pass and existing v1 behavior is unchanged.

- [ ] **Step 5: Commit the evaluator**

```bash
git add src/erasemap/cdc.py tests/test_cdc.py tests/pcug_factories.py
git commit -m "feat: replay counterfactual graph transitions"
```

## Task 4: Brute-force oracle and exact CDC

**Files:**
- Modify: `src/erasemap/cdc.py`
- Modify: `tests/test_cdc.py`
- Create: `tests/test_cdc_properties.py`

- [ ] **Step 1: Write failing optimality and tie-break tests**

```python
from erasemap.cdc import brute_force_cdc, exact_cdc
from tests.pcug_factories import forked_pcug_case


def test_exact_cdc_matches_brute_force() -> None:
    graph, protocol, action_map = forked_pcug_case()
    actions = tuple(action_map.values())
    assert exact_cdc(graph, protocol, actions) == brute_force_cdc(graph, protocol, actions)


def test_exact_cdc_uses_lexical_tie_break() -> None:
    graph, protocol, actions = equal_cost_complete_case()
    assert exact_cdc(graph, protocol, actions).action_ids == ("a-close",)
```

- [ ] **Step 2: Run and observe missing solver functions**

Run: `.venv/bin/pytest tests/test_cdc.py::test_exact_cdc_matches_brute_force -q`

Expected: import fails for `brute_force_cdc` or `exact_cdc`.

- [ ] **Step 3: Implement the oracle and branch-and-bound solver**

```python
def brute_force_cdc(graph: PCUGGraph, protocol: CDCProtocol, actions: tuple[CDCAction, ...]) -> CDCPlan:
    best: CDCPlan | None = None
    ordered = tuple(sorted((action for action in actions if action.permitted), key=lambda item: item.id))
    for size in range(len(ordered) + 1):
        for chosen in combinations(ordered, size):
            report = evaluate_actions(graph, protocol, chosen)
            candidate = plan_from_report(chosen, report, optimal=True)
            if report.verdict is PCUGVerdict.COMPLETE and (best is None or plan_key(candidate) < plan_key(best)):
                best = candidate
    return best or infeasible_plan(graph, protocol)
```

Implement `exact_cdc` with admissible cost lower bounds, suffix transition capabilities, deterministic
include/exclude search, and a configurable action limit. Do not prune on declared node coverage. Return
an explicit infeasible plan when no verified complete intervention exists.

- [ ] **Step 4: Add exhaustive/property comparison**

```python
@given(small_pcug_cases())
def test_exact_equals_oracle(case: PCUGCase) -> None:
    oracle = brute_force_cdc(case.graph, case.protocol, case.actions)
    exact = exact_cdc(case.graph, case.protocol, case.actions)
    assert exact.verdict == oracle.verdict
    assert exact.total_cost == oracle.total_cost
    assert exact.action_ids == oracle.action_ids
```

- [ ] **Step 5: Run solver tests and commit**

Run: `.venv/bin/pytest tests/test_cdc.py tests/test_cdc_properties.py -q`

Expected: unit and generated cases pass with no flaky seeds.

```bash
git add src/erasemap/cdc.py tests/test_cdc.py tests/test_cdc_properties.py
git commit -m "feat: compute exact counterfactual deletion cuts"
```

## Task 5: Deterministic greedy CDC baseline

**Files:**
- Modify: `src/erasemap/cdc.py`
- Modify: `tests/test_cdc.py`

- [ ] **Step 1: Write failing greedy safety tests**

```python
def test_greedy_never_labels_partial_plan_complete() -> None:
    graph, protocol, actions = infeasible_pcug_case()
    plan = greedy_cdc(graph, protocol, actions)
    assert plan.verdict is not PCUGVerdict.COMPLETE


def test_greedy_is_deterministic() -> None:
    graph, protocol, action_map = forked_pcug_case()
    forward = greedy_cdc(graph, protocol, tuple(action_map.values()))
    reverse = greedy_cdc(graph, protocol, tuple(reversed(tuple(action_map.values()))))
    assert forward == reverse
```

- [ ] **Step 2: Verify the missing function failure**

Run: `.venv/bin/pytest tests/test_cdc.py -k greedy -q`

Expected: import or name resolution fails for `greedy_cdc`.

- [ ] **Step 3: Implement measured marginal selection**

```python
def greedy_cdc(graph: PCUGGraph, protocol: CDCProtocol, actions: tuple[CDCAction, ...]) -> CDCPlan:
    chosen: tuple[CDCAction, ...] = ()
    remaining = tuple(sorted((a for a in actions if a.permitted), key=lambda a: a.id))
    report = evaluate_actions(graph, protocol, chosen)
    while report.verdict is not PCUGVerdict.COMPLETE:
        ranked = rank_marginal_actions(graph, protocol, chosen, remaining, report)
        if not ranked or ranked[0].closed_constraints == 0:
            break
        selected = ranked[0].action
        chosen = (*chosen, selected)
        remaining = tuple(action for action in remaining if action.id != selected.id)
        report = evaluate_actions(graph, protocol, chosen)
    return plan_from_report(chosen, report, optimal=False)
```

Rank by verified constraints closed per unit cost, then cost, then action ID. Zero-cost actions use an
infinite primary score only when they close at least one currently open constraint.

- [ ] **Step 4: Run focused tests and commit**

Run: `.venv/bin/pytest tests/test_cdc.py tests/test_cdc_properties.py -q`

Expected: all CDC tests pass.

```bash
git add src/erasemap/cdc.py tests/test_cdc.py
git commit -m "feat: add deterministic greedy cdc baseline"
```

## Task 6: Canonical proof bundle and independent checker

**Files:**
- Create: `src/erasemap/proof_bundle.py`
- Test: `tests/test_proof_bundle.py`

- [ ] **Step 1: Write failing canonical and tamper tests**

```python
def test_bundle_encoding_is_canonical() -> None:
    bundle = signed_complete_bundle()
    assert encode_bundle(bundle) == encode_bundle(decode_bundle(encode_bundle(bundle)))


def test_checker_recomputes_and_rejects_forged_complete_field() -> None:
    bundle, trust = forged_complete_bundle_with_active_path()
    result = check_bundle(bundle, trust)
    assert not result.valid
    assert result.reason == "declared verdict differs from replayed verdict"


def test_checker_rejects_hidden_challenge_commitment_mismatch() -> None:
    bundle, trust = bundle_with_changed_challenge()
    assert check_bundle(bundle, trust).reason == "challenge commitment mismatch"
```

- [ ] **Step 2: Verify tests fail for the missing module**

Run: `.venv/bin/pytest tests/test_proof_bundle.py -q`

Expected: collection fails with missing `proof_bundle`.

- [ ] **Step 3: Implement canonical encoding and commitment helpers**

```python
def canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def commitment(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()
```

Define a strict schema with exact fields for protocol, pre/post graph, selected actions, raw channels,
challenge opening, solver status, declared verdict, environment hashes, signature, nonce, and previous
bundle hash. Reject unknown fields, duplicates, non-finite values, path endpoints absent from the graph,
and noncanonical action order.

- [ ] **Step 4: Implement independent replay and signature checking**

```python
def check_bundle(bundle: ProofBundle, trust: Mapping[str, Ed25519PublicKey]) -> BundleCheck:
    key = trust.get(bundle.key_id)
    if key is None:
        return BundleCheck(False, "untrusted key id", None)
    if commitment(bundle.challenge_opening) != bundle.challenge_commitment:
        return BundleCheck(False, "challenge commitment mismatch", None)
    if not verify_signature(key, bundle.signing_payload(), bundle.signature):
        return BundleCheck(False, "invalid signature", None)
    replayed = evaluate_actions(bundle.pre_graph, bundle.protocol, bundle.selected_actions)
    if replayed.verdict is not bundle.declared_verdict:
        return BundleCheck(False, "declared verdict differs from replayed verdict", replayed)
    return BundleCheck(True, "verified", replayed)
```

The checker recomputes graph roots, action costs, channel decisions, paths, and the final verdict; it
never accepts producer-supplied derived totals.

- [ ] **Step 5: Run security-focused tests and commit**

Run: `.venv/bin/pytest tests/test_proof_bundle.py tests/test_receipts.py tests/test_evidence_envelopes.py -q`

Expected: new and existing signature/replay tests pass.

```bash
git add src/erasemap/proof_bundle.py tests/test_proof_bundle.py
git commit -m "feat: verify proof-carrying unlearning bundles"
```

## Task 7: Controlled benchmark and preregistered development protocol

**Files:**
- Create: `src/erasemap/pcug_benchmark.py`
- Create: `benchmark/pcug-protocol-v1.json`
- Test: `tests/test_pcug_benchmark.py`

- [ ] **Step 1: Write failing benchmark determinism tests**

```python
def test_development_benchmark_is_reproducible() -> None:
    protocol = load_pcug_protocol("benchmark/pcug-protocol-v1.json")
    first = run_pcug_benchmark(protocol, split="development")
    second = run_pcug_benchmark(protocol, split="development")
    assert encode_records(first) == encode_records(second)


def test_benchmark_keeps_unknown_separate_from_complete() -> None:
    records = run_unknown_fixture()
    assert records[0].verdict == "UNVERIFIED"
    assert records[0].false_complete is False
```

- [ ] **Step 2: Verify tests fail for missing benchmark API**

Run: `.venv/bin/pytest tests/test_pcug_benchmark.py -q`

Expected: collection fails for missing `pcug_benchmark`.

- [ ] **Step 3: Freeze a development-only JSON protocol**

```json
{
  "schema_version": "erasemap-pcug-protocol-v1",
  "development_seeds": [1103, 2207, 3301],
  "faults": ["none", "source_only", "stale_index", "live_backup", "unknown_model", "single_view_evasion", "artifact_displacement", "compound"],
  "methods": ["receipt_only", "flat_checklist", "erasemap_v1", "model_only", "greedy_cdc", "exact_cdc"],
  "primary_endpoint": "false_complete_rate",
  "bootstrap_seed": 88421,
  "bootstrap_samples": 2000,
  "holdout": {"committed": false, "seeds": []}
}
```

- [ ] **Step 4: Implement deterministic records and baseline adapters**

Every method-trial record contains protocol hash, code revision, seed, topology, fault, provider
behavior, ground-truth completeness, verdict, false-complete boolean, chosen actions, cost, active path
count, unknown constraint count, runtime, and exception. Exceptions are records, never dropped.

- [ ] **Step 5: Run benchmark tests and commit**

Run: `.venv/bin/pytest tests/test_pcug_benchmark.py tests/test_benchmark.py tests/test_fixture_benchmark.py -q`

Expected: deterministic outputs and legacy benchmark tests pass.

```bash
git add src/erasemap/pcug_benchmark.py benchmark/pcug-protocol-v1.json tests/test_pcug_benchmark.py
git commit -m "feat: register pcug development benchmark"
```

## Task 8: CLI and synthetic FaceID-style demonstration

**Files:**
- Modify: `src/erasemap/cli.py`
- Create: `examples/pcug-faceid-style.json`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
def test_pcug_demo_exports_verified_bundle(tmp_path: Path) -> None:
    output = tmp_path / "bundle.json"
    result = main(["pcug", "demo", "--output", str(output)])
    assert result == 0
    assert json.loads(output.read_text())["evidence_scope"] == "SYNTHETIC_SIMULATOR"


def test_pcug_verify_rejects_tampered_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = write_tampered_bundle(tmp_path)
    assert main(["pcug", "verify", str(bundle)]) == 1
    assert "invalid" in capsys.readouterr().out.lower()


def test_pcug_verify_directory_reports_every_bundle(tmp_path: Path) -> None:
    directory, public_key = write_valid_and_invalid_bundles(tmp_path)
    result = invoke(["pcug", "verify-directory", str(directory), "--public-key", str(public_key)])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"checked": 2, "invalid": 1, "unverifiable": 0, "valid": 1}
```

- [ ] **Step 2: Run focused CLI tests and verify failure**

Run: `.venv/bin/pytest tests/test_cli.py -k pcug -q`

Expected: parser rejects the unknown `pcug` command.

- [ ] **Step 3: Add explicit subcommands**

Implement `erasemap pcug demo`, `erasemap pcug verify`, `erasemap pcug verify-directory`, and
`erasemap pcug benchmark development`. All JSON is written atomically, simulator output is labelled
`SYNTHETIC_SIMULATOR`, and verification uses a supplied public key rather than silently trusting an
embedded key. Directory verification sorts paths, checks every `*.json` bundle, reports exact counts,
returns `1` when any bundle is invalid or unverifiable, and returns `0` only when all are valid.

- [ ] **Step 4: Run CLI and package smoke tests**

Run: `.venv/bin/pytest tests/test_cli.py tests/test_package.py -q && .venv/bin/erasemap pcug demo --output /tmp/erasemap-pcug-demo.json`

Expected: tests pass; command exits `0` and writes a simulator-labelled bundle.

- [ ] **Step 5: Commit CLI and example**

```bash
git add src/erasemap/cli.py tests/test_cli.py examples/pcug-faceid-style.json
git commit -m "feat: expose pcug verification demo"
```

## Task 9: Import existing model evidence without rewriting history

**Files:**
- Create: `src/erasemap/pcug_model_adapter.py`
- Create: `tests/test_pcug_model_adapter.py`

- [ ] **Step 1: Write failing provenance and fail-closed tests**

```python
def test_v3_import_preserves_dataset_strata() -> None:
    evidence = import_v3_evidence(valid_v3_fixture())
    assert tuple(item.stratum for item in evidence) == ("development", "locked_internal", "content_unseen")


def test_failed_external_stratum_cannot_be_hidden_by_average() -> None:
    summary = compose_model_strata(v3_fixture_with_external_failure())
    assert summary.verdict is PCUGVerdict.INCOMPLETE


def test_unknown_protocol_hash_is_unverified() -> None:
    summary = compose_model_strata(v3_fixture(protocol_hash="sha256:unregistered"))
    assert summary.verdict is PCUGVerdict.UNVERIFIED
```

- [ ] **Step 2: Verify the adapter module is missing**

Run: `.venv/bin/pytest tests/test_pcug_model_adapter.py -q`

Expected: collection fails with missing `pcug_model_adapter`.

- [ ] **Step 3: Implement strict evidence conversion**

`import_v3_evidence` accepts the current manifest, protocol, and result JSON paths; verifies their
SHA-256 hashes, registered schema versions, dataset/split identity, deletion unit, model seed,
retraining reference, and metric denominators; then emits named `ChannelResult` values for forgotten
behavior, retained utility, identity LiRA, representation comparison, and compute. Missing fields,
non-finite values, hash mismatch, a failed mandatory stratum, or an inconclusive registered margin
produce `UNVERIFIED`/`INCOMPLETE` according to the PCUG composition rules rather than a pooled pass.

- [ ] **Step 4: Run adapter and historical-result regression tests**

Run: `.venv/bin/pytest tests/test_pcug_model_adapter.py tests/test_public_results.py tests/test_task_agnostic_v21_protocol.py -q`

Expected: adapter tests pass and all historical v3 assertions remain byte-for-byte compatible.

- [ ] **Step 5: Commit the model-evidence bridge**

```bash
git add src/erasemap/pcug_model_adapter.py tests/test_pcug_model_adapter.py
git commit -m "feat: bind v3 model evidence to pcug channels"
```

## Task 10: FaceID, eGov, KYC, and school simulator adapters

**Files:**
- Create: `src/erasemap/pcug_adapters.py`
- Create: `tests/test_pcug_adapters.py`
- Create: `examples/pcug-egov-style.json`
- Create: `examples/pcug-kyc-style.json`
- Create: `examples/pcug-school-style.json`

- [ ] **Step 1: Write failing semantic-equivalence tests**

```python
@pytest.mark.parametrize("adapter", ("faceid_style", "egov_style", "kyc_style", "school_style"))
def test_adapter_label_does_not_change_core_verdict(adapter: str) -> None:
    case = build_adapter_case(adapter, seed=4409)
    reference = build_adapter_case("faceid_style", seed=4409)
    assert strip_display_metadata(case.graph) == strip_display_metadata(reference.graph)
    assert exact_cdc(case.graph, case.protocol, case.actions).verdict == exact_cdc(reference.graph, reference.protocol, reference.actions).verdict


def test_every_adapter_is_explicitly_simulated() -> None:
    assert all(build_adapter_case(name, seed=1).evidence_scope == "SYNTHETIC_SIMULATOR" for name in adapter_names())
```

- [ ] **Step 2: Verify the adapters are missing**

Run: `.venv/bin/pytest tests/test_pcug_adapters.py -q`

Expected: collection fails with missing `pcug_adapters`.

- [ ] **Step 3: Implement display-only application mapping**

Expose four fixed adapters that map the same typed graph roles to application-specific display names,
purposes, and action descriptions. Preserve node/edge/action semantics and costs across adapters for a
given seed. Every exported case includes `evidence_scope: SYNTHETIC_SIMULATOR`, `authorized_integration:
false`, and a statement that it is not evidence about Apple, eGov, a bank, or a school deployment.

- [ ] **Step 4: Run cross-adapter tests and commit**

Run: `.venv/bin/pytest tests/test_pcug_adapters.py tests/test_cdc.py -q`

Expected: all tests pass and all four adapters produce the same core decision for the same fault.

```bash
git add src/erasemap/pcug_adapters.py tests/test_pcug_adapters.py examples/pcug-egov-style.json examples/pcug-kyc-style.json examples/pcug-school-style.json
git commit -m "feat: add labelled pcug system simulators"
```

## Task 11: Protocol, novelty boundary, and measured-result separation

**Files:**
- Create: `docs/PCUG_PROTOCOL.md`
- Modify: `docs/NOVELTY_AND_PRIOR_ART.md`
- Modify: `README.md`

- [ ] **Step 1: Write the protocol field reference**

Document the three-valued logic, physical-versus-influence distinction, action replay, exact/greedy
solver semantics, bundle commitments, verifier-aware threat model, primary endpoint, and prohibited
claims. Include commands that actually exist after Task 8.

- [ ] **Step 2: Add an explicit evidence-status table to README**

```markdown
| Component | Status | Evidence |
|---|---|---|
| Typed residual-path audit v1 | Measured controlled benchmark | `docs/CORE_PROTOCOL.md` |
| Deletion-matched model experiments v3 | Measured on named datasets only | `docs/TASK_AGNOSTIC_V3_REPORT.md` |
| PCUG/CDC deterministic core | Implemented and unit-verified | `docs/PCUG_PROTOCOL.md` |
| PCUG external generalization | Not established | Requires locked external evaluation |
| Production FaceID/eGov applicability | Not established | Requires authorized integration |
```

- [ ] **Step 3: Update prior-art boundaries**

State that PCUG claims the tested composition only; it does not claim invention of provenance,
machine unlearning, per-instance privacy, hidden evaluation, min-cut, set cover, or deletion receipts.
Link primary sources and date the search snapshot.

- [ ] **Step 4: Check links, terminology, and prohibited claims**

Run: `rg -n "first in the world|proven deletion|production-ready|audits eGov|Apple Face ID" README.md docs`

Expected: no unqualified prohibited claim; any match appears only in an explicit limitation or
prohibition.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md docs/PCUG_PROTOCOL.md docs/NOVELTY_AND_PRIOR_ART.md docs/superpowers/specs/2026-08-22-proof-carrying-unlearning-graph.md docs/superpowers/plans/2026-08-22-pcug-cdc-implementation.md
git commit -m "docs: define pcug protocol and claim boundary"
```

## Task 12: Full verification and development evidence

**Files:**
- Modify: `pyproject.toml`
- Create: `outputs/pcug-development-v1/manifest.json`
- Create: `outputs/pcug-development-v1/records.jsonl`
- Create: `outputs/pcug-development-v1/metrics.json`
- Create: `docs/PCUG_DEVELOPMENT_REPORT.md`

- [ ] **Step 1: Run the full deterministic quality gate**

Add `build>=1.2` to the `dev` optional dependency so the documented clean-environment build command
is part of the declared toolchain.

Run: `.venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest --cov=erasemap --cov-report=term-missing`

Expected: all commands exit `0`; any uncovered safety branch is either tested before proceeding or
listed with a concrete non-safety reason in the development report.

- [ ] **Step 2: Build and inspect the distribution**

Run: `.venv/bin/python -m build && .venv/bin/python -m zipfile -l dist/erasemap-*.whl`

Expected: build exits `0`, and the wheel includes all four new runtime modules.

- [ ] **Step 3: Run only the registered development split**

Run: `.venv/bin/erasemap pcug benchmark development --protocol benchmark/pcug-protocol-v1.json --output outputs/pcug-development-v1`

Expected: exit `0`; manifest protocol hash matches the current protocol; record count equals the
Cartesian product declared by the protocol; exception count is reported explicitly.

- [ ] **Step 4: Independently replay every emitted complete bundle**

Run: `.venv/bin/erasemap pcug verify-directory outputs/pcug-development-v1/bundles --public-key outputs/pcug-development-v1/public-key.pem`

Expected: every bundle reported valid or the development run is marked failed. The command prints
checked, valid, invalid, and unverifiable counts.

- [ ] **Step 5: Write the development report from exported data**

Report denominators, false-complete rate, Wilson intervals, fault recall, false alarms, `UNVERIFIED`
rate, costs, exact-versus-greedy gap, runtimes, exceptions, negative results, and simulator limits.
Do not create a locked holdout protocol until development variance and failure modes are reviewed.

- [ ] **Step 6: Run repository cleanliness and publication audit**

Run: `git diff --check && git status --short && git log -5 --oneline`

Expected: no whitespace errors; only intentional generated evidence/report files are uncommitted.

- [ ] **Step 7: Commit reproducible development evidence**

```bash
git add -f outputs/pcug-development-v1
git add docs/PCUG_DEVELOPMENT_REPORT.md pyproject.toml
git commit -m "experiment: publish pcug development evidence"
```

## Task 13: Holdout readiness gate without opening holdout

**Files:**
- Create: `docs/PCUG_HOLDOUT_READINESS.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/reproduce_release.sh`

- [ ] **Step 1: Add CI coverage for the deterministic core**

Keep the existing Node 24-compatible actions. Add commands for Ruff, mypy, complete pytest, package
build, PCUG demo generation, and independent demo-bundle verification.

- [ ] **Step 2: Document readiness requirements**

The checklist requires reviewed development failures, frozen numeric margins, hidden topology and
challenge commitments, a clean commit, independent dataset provenance, one-shot execution, and a
rule that revealed holdout results cannot be relabelled development.

- [ ] **Step 3: Reproduce CI locally**

Run: `bash scripts/reproduce_release.sh`

Expected: the existing release reproduction plus new PCUG deterministic checks exit `0`.

- [ ] **Step 4: Commit the readiness gate**

```bash
git add .github/workflows/ci.yml docs/PCUG_HOLDOUT_READINESS.md scripts/reproduce_release.sh
git commit -m "ci: gate pcug holdout readiness"
```

- [ ] **Step 5: Verify branch state before any requested push**

Run: `git status --short --branch && git rev-list --left-right --count origin/main...HEAD`

Expected: clean worktree and an explicit ahead/behind count. A push, when separately requested or
already authorized by the active workflow, is not declared complete until local `HEAD` equals
`origin/main` and the required GitHub Actions run succeeds.
