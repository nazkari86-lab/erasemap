# Source-Locked Multi-System Holdout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, execute, and publish a one-shot PCUG holdout derived from independently sourced official system structures, plus a bounded MUFAC remediation attempt and offline evaluator kit.

**Architecture:** A source-lock layer records immutable official-source excerpts and mappings; a separate holdout constructor converts only those mappings into typed cases and sealed truth commitments; an evaluator consumes public cases without importing truth, then a reveal/report layer scores results. MUFAC v2 remains a separate model-evidence stratum so a model result cannot be confused with topology-holdout evidence.

**Tech Stack:** Python 3.11, dataclasses, canonical JSON/SHA-256, existing EraSeMap PCUG/CDC/proof-bundle modules, cryptography, pytest/Hypothesis, NumPy/scikit-learn/PyTorch for MUFAC, GitHub Actions.

---

## File map

- `src/erasemap/source_lock.py`: strict source-manifest parsing, excerpt hashing, and mapping validation.
- `src/erasemap/external_cases.py`: source-family case construction without evaluation logic.
- `src/erasemap/holdout_commitment.py`: seed commitments, answer sealing/reveal, immutable run directory.
- `src/erasemap/external_evaluator.py`: public-case execution, baselines, PCUG, CDC, and proof bundles.
- `src/erasemap/holdout_report.py`: truth join, endpoints, Wilson intervals, macro summaries, report JSON.
- `benchmark/external-sources-v1.json`: frozen official URLs, retrieval metadata, excerpts, mappings, hashes.
- `benchmark/pcug-source-locked-holdout-v1.json`: preregistered families, faults, seeds, endpoints, and thresholds.
- `benchmark/commitments/pcug-source-locked-holdout-v1.json`: public case/truth commitments.
- `experiments/run_source_locked_holdout.py`: guarded one-shot orchestration.
- `external_evaluator/`: offline verifier entrypoint, schema, README, and example command.
- `experiments/run_mufac_utility_constrained_v2.py`: development-only selection and frozen v2 evaluation.
- `benchmark/mufac-external-v2.json`: immutable MUFAC remediation protocol.
- `tests/test_source_lock.py`, `tests/test_external_cases.py`, `tests/test_holdout_commitment.py`, `tests/test_external_evaluator.py`, `tests/test_holdout_report.py`: component and negative tests.
- `.github/workflows/ci.yml`, `scripts/reproduce_release.sh`, `README.md`, and study reports: publication gates.

### Task 1: Freeze and validate official source evidence

**Files:**
- Create: `src/erasemap/source_lock.py`
- Create: `benchmark/external-sources-v1.json`
- Create: `tests/test_source_lock.py`

- [ ] Write tests proving unknown fields, changed excerpts, duplicate mapping IDs, non-HTTPS URLs, unsupported relations, and mismatched SHA-256 fail closed.
- [ ] Run `.venv/bin/pytest tests/test_source_lock.py -q` and confirm failure because `erasemap.source_lock` does not exist.
- [ ] Implement frozen dataclasses `SourceExcerpt`, `RelationMapping`, and `SourceManifest`; canonicalize JSON; recompute every excerpt and manifest hash; allow only declared PCUG node/edge mappings.
- [ ] Populate the manifest from NIST SP 800-63A, W3C PROV-O, OpenSearch snapshot documentation, MLflow store/registry documentation, and PostgreSQL backup/WAL documentation. Store short factual excerpts within quotation limits and record source URL, retrieval date, title, relation, and mapping rationale.
- [ ] Run `.venv/bin/pytest tests/test_source_lock.py -q` and `.venv/bin/mypy src/erasemap`; expect success.
- [ ] Commit with `git commit -m "feat: freeze independent system source mappings"`.

### Task 2: Construct heterogeneous source-derived cases

**Files:**
- Create: `src/erasemap/external_cases.py`
- Create: `tests/test_external_cases.py`

- [ ] Write tests asserting five distinct structural families, stable case IDs, no adapter-label multiplication, valid PCUG graphs, family-specific node vocabularies, complete/incomplete/unverified truth classes, and PostgreSQL recovery branches crossing at least two families.
- [ ] Run `.venv/bin/pytest tests/test_external_cases.py -q`; expect import failure.
- [ ] Implement `ExternalCase`, `ExternalFault`, and `build_source_cases(manifest, protocol)` using a registry of isolated family builders. Each builder must cite mapping IDs and produce graph, protocol, actions, frozen truth verdict, and expected residual path without calling the PCUG audit function.
- [ ] Add deterministic single and compound fault transformations for surviving biometric references, PROV alternates, OpenSearch snapshots, MLflow artifacts/metadata, WAL recovery, unknown verification, and replay-inconsistent evidence.
- [ ] Run the targeted tests and existing PCUG tests; expect success.
- [ ] Commit with `git commit -m "feat: derive heterogeneous external holdout cases"`.

### Task 3: Commit and seal the holdout before evaluation

**Files:**
- Create: `src/erasemap/holdout_commitment.py`
- Create: `benchmark/pcug-source-locked-holdout-v1.json`
- Create: `tests/test_holdout_commitment.py`

- [ ] Write tests for deterministic commitments, wrong-key rejection, tamper detection, protocol-hash mismatch, parent/reveal revision mismatch, and refusal to overwrite an existing run.
- [ ] Run `.venv/bin/pytest tests/test_holdout_commitment.py -q`; expect import failure.
- [ ] Implement canonical commitment envelopes that publish hashes of cases and answers while keeping the evaluator input free of truth fields. Use authenticated encryption from `cryptography` for the local sealed answer archive and accept the key only at reveal time.
- [ ] Freeze primary false-complete endpoint, Wilson upper bound `<=0.05`, per-family and macro reporting, baselines, ablations, exclusions, timeouts, one-shot rule, and pass/fail/inconclusive wording.
- [ ] Generate and commit the public commitment manifest before running any evaluator.
- [ ] Run targeted tests and `git diff --check`; expect success.
- [ ] Commit with `git commit -m "experiment: preregister source-locked pcug holdout"`.

### Task 4: Build an answer-blind external evaluator

**Files:**
- Create: `src/erasemap/external_evaluator.py`
- Create: `tests/test_external_evaluator.py`
- Modify: `src/erasemap/cli.py`

- [ ] Write tests that monkeypatch truth-module imports to fail, verify PCUG and every named baseline emit one record per public case, ensure exceptions become non-complete records, and verify proof bundles independently.
- [ ] Run `.venv/bin/pytest tests/test_external_evaluator.py -q`; expect failure.
- [ ] Implement evaluator records containing case commitment, method, verdict, shortest path, action IDs, cost, exception, runtime, and bundle path. Do not include or import expected verdict/path.
- [ ] Add `erasemap holdout evaluate` CLI with exclusive output creation and protocol/source/commitment hash checks.
- [ ] Run targeted tests plus `tests/test_cli.py`; expect success.
- [ ] Commit with `git commit -m "feat: add answer-blind pcug holdout evaluator"`.

### Task 5: Reveal truth and calculate preregistered endpoints

**Files:**
- Create: `src/erasemap/holdout_report.py`
- Create: `tests/test_holdout_report.py`

- [ ] Write exact tests for Wilson intervals, zero-denominator handling, exception inclusion, per-family metrics, macro versus micro separation, exact-path scoring, and pass/fail/inconclusive decisions.
- [ ] Run `.venv/bin/pytest tests/test_holdout_report.py -q`; expect failure.
- [ ] Implement commitment-checked truth joins and immutable JSON/Markdown rendering. Mark any missing, duplicate, or unmatched evaluator record inconclusive rather than dropping it.
- [ ] Run targeted tests and a mutation test that changes one result byte; expect the untampered report to pass verification and the changed record to be rejected.
- [ ] Commit with `git commit -m "feat: score committed holdout evidence"`.

### Task 6: Run and preserve the one-shot topology holdout

**Files:**
- Create: `experiments/run_source_locked_holdout.py`
- Create after execution: `outputs/source-locked-holdout-v1/**`
- Create after execution: `docs/SOURCE_LOCKED_HOLDOUT_V1_REPORT.md`

- [ ] Implement orchestration that verifies a clean preregistration revision, creates a new output directory, evaluates once, reveals once, verifies every proof bundle, and writes provenance plus a SHA-256 manifest.
- [ ] Run the command once from the preregistered revision. Do not delete, overwrite, relabel, or rerun failed cases.
- [ ] Validate all output hashes using a separate verification command and inspect failures without changing v1.
- [ ] Render a report that states actual denominators, intervals, failures, source-independence boundary, and production limitation.
- [ ] Commit the complete raw evidence and report with `git commit -m "experiment: publish source-locked holdout evidence"`.

### Task 7: Attempt bounded MUFAC retained-utility remediation

**Files:**
- Create: `benchmark/mufac-external-v2.json`
- Create: `experiments/run_mufac_utility_constrained_v2.py`
- Create: `tests/test_mufac_v2_protocol.py`
- Create after execution: `outputs/mufac-external-v2/**`
- Create after execution: `docs/MUFAC_EXTERNAL_V2_REPORT.md`

- [ ] Write protocol tests ensuring v1 outputs cannot be overwritten, evaluation identities cannot influence checkpoint selection, all candidate selection is development-only, and original v1 evidence remains referenced.
- [ ] Implement utility-constrained deletion-matched restart candidates with frozen seeds/budgets and development-only selection on retained utility subject to forgetting/privacy constraints.
- [ ] Commit the v2 protocol and code before the evaluation command with `git commit -m "experiment: preregister MUFAC utility remediation"`.
- [ ] Run v2 once using the already downloaded immutable MUFAC revision. If data or compute is unavailable, preserve an `INCONCLUSIVE` environment manifest rather than synthesize a result.
- [ ] Report v1 and v2 side by side, including any remaining failure, and commit with `git commit -m "experiment: publish MUFAC v2 evidence"`.

### Task 8: Package an independent organization evaluator kit

**Files:**
- Create: `external_evaluator/README.md`
- Create: `external_evaluator/result-schema.json`
- Create: `external_evaluator/run.py`
- Create: `external_evaluator/verify.py`
- Create: `tests/test_external_kit.py`

- [ ] Write a subprocess test that copies only the built wheel, kit, public protocol, public key, and example cases into a temporary directory and completes evaluation/verification without repository imports.
- [ ] Implement one-command offline run and verify interfaces, strict JSON schema behavior, non-overwrite semantics, and signed-result metadata for a future external evaluator.
- [ ] Document exactly what an organization must provide, what stays private, and why a kit run is not automatically production validation.
- [ ] Run the clean-room subprocess test and commit with `git commit -m "feat: ship independent pcug evaluator kit"`.

### Task 9: Add ablations, regression gates, and reproducibility

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/reproduce_release.sh`
- Modify: `tests/test_public_results.py`
- Modify: `README.md`

- [ ] Add public-result assertions for source hashes, preregistration ancestry, raw-record counts, metrics, proof-bundle verification, and immutable MUFAC v1/v2 references.
- [ ] Add CI commands for source validation, holdout evidence verification, clean-room evaluator-kit execution, Ruff, strict mypy, 90% coverage, and package build.
- [ ] Update reproduction script to start from a fresh temporary output path and verify committed evidence without overwriting it.
- [ ] Run the complete local gate; expect every command to pass.
- [ ] Commit with `git commit -m "ci: gate external holdout evidence"`.

### Task 10: Adversarial self-audit and publication

**Files:**
- Modify only files implicated by reproducible audit failures.

- [ ] Search for evaluator imports of truth/answer modules, pooled adapter claims, mutable output writes, unverified hash fields, source-family duplication, and wording that implies production access.
- [ ] Run `ruff`, strict `mypy`, full coverage, build, clean-room kit, evidence verification, `git diff --check`, and `git status` from a clean tree.
- [ ] Push the feature branch, open a PR, wait for all checks, merge to `main`, fetch, and fast-forward local `main`.
- [ ] Verify local HEAD equals `origin/main`, ahead/behind is `0/0`, expected evidence files exist in `origin/main`, the worktree is clean, and the post-merge GitHub Actions run succeeds.

