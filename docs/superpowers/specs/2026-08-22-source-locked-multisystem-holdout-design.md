# Source-Locked Multi-System Holdout

Date: 2026-08-22

Status: approved design

## Purpose

EraSeMap's existing PCUG development benchmark establishes internal consistency against
project-authored simulator faults. This study adds independently sourced topology families, freezes
them before evaluation, and runs PCUG once without tuning on revealed holdout outcomes. It does not
claim access to Apple Face ID, Kazakhstan eGov, a bank, a school, or any production organization.

The primary research question is:

> Can the frozen PCUG implementation avoid false declarations of complete deletion across unseen,
> externally sourced storage and derivation structures while returning actionable residual paths?

## Source families

The study derives structure from official sources whose documents, retrieval timestamps, content
hashes, and extraction decisions are committed before evaluation:

1. NIST SP 800-63A identity proofing: biometric samples, biometric references, consent records,
   subscriber accounts, service partners, retention, and deletion.
2. W3C PROV-O: entities, activities, derivations, specializations, alternate copies, collections,
   bundles, and invalidation.
3. OpenSearch documentation: indices, aliases, snapshot repositories, snapshots, deletion, and
   restoration.
4. MLflow documentation: tracking metadata, artifact stores, runs, registered models, versions,
   aliases, and garbage collection.
5. PostgreSQL documentation supplies a cross-cutting recovery branch: base backups, WAL archives,
   point-in-time recovery, and replication slots.

Application names such as FaceID, eGov, KYC, and School are presentation adapters only. Independent
units of analysis are source-derived topology cases, not adapter labels.

## Independence boundary

Source independence means that topology relations and fault opportunities are derived from external
official documents rather than copied from the PCUG development generator. It does not mean that an
independent human designed, labelled, or ran the study. All project-authored mappings are explicit
and auditable.

The source extractor may emit only relations supported by frozen source excerpts and a predeclared
mapping table. The holdout builder and PCUG evaluator are separate modules. The evaluator cannot
import holdout answers, fault labels, or expected residual paths.

## Two-phase freeze

### Phase A: source lock and preregistration

Before any candidate result is inspected, commit:

- source URLs, retrieval timestamps, local snapshots where redistribution permits, and SHA-256;
- normalized source excerpts and mapping-table version;
- topology-family identifiers and deterministic case-construction rules;
- fault catalogue, seed commitments, and encrypted or commitment-only answer material;
- primary and secondary endpoints, thresholds, denominators, interval method, exclusions, timeout
  behavior, and missing-evidence behavior;
- exact EraSeMap revision, dependency lock, runtime platform, and evaluator command;
- pass, fail, and inconclusive claim language.

The preregistration commit is the parent of the reveal commit. Changing a frozen item creates a new
study version and cannot replace the original result.

### Phase B: one-shot reveal and evaluation

The reveal tool verifies all Phase A hashes, materializes the committed cases, invokes the frozen
PCUG evaluator exactly once, and writes an append-only result directory. It refuses to overwrite a
prior run. Every exception, timeout, malformed case, missing channel, and unverifiable transition is
retained and counted as non-complete; it cannot be silently excluded.

## Case construction

Each family has distinct node types, derivation relations, deletion actions, evidence requirements,
and fault transformations. Cases include single and interacting faults such as:

- active biometric reference after account deletion;
- alternate or specialized PROV entity surviving invalidation of its primary entity;
- deleted search index recoverable from a snapshot;
- removed MLflow registry entry with artifacts or run metadata remaining;
- logically deleted database record recoverable through backup and WAL paths;
- unknown mandatory verifier channel;
- validly signed but replay-inconsistent completion evidence.

Cases must include genuine complete states, incomplete states, and states whose correct result is
`UNVERIFIED`. Ground truth is computed from frozen case construction, not from PCUG output.

## Endpoints

The unit of analysis is one unique source-derived topology and fault state. Cosmetic presentation
adapters and repeated seeds do not create independent units.

Primary endpoint:

- false-complete rate among ground-truth `INCOMPLETE` or `UNVERIFIED` cases, with a two-sided Wilson
  95% confidence interval.

Primary success criterion:

- observed false-complete rate is 0, and the Wilson 95% upper bound is at most 0.05.

Secondary endpoints:

- recall of non-complete states;
- specificity on genuinely complete states;
- exact residual-path match rate;
- actionable-path validity under independent replay;
- proof-bundle verification rate;
- planner completion rate and registered action cost;
- exception and timeout counts, always reported separately and included fail-closed.

No pooled FaceID/eGov/KYC/School headline is permitted. Results are reported per source family and as
a macro-average across eligible families. Micro-averages are supplementary.

## Baselines and ablations

The frozen comparison includes receipt-only, model-only, flat checklist, typed-node audit, and PCUG.
Planner comparison includes exact CDC, greedy CDC, and delete-all. Ablations remove, one at a time,
physical-artifact terminality, unknown-edge propagation, model-channel composition, action replay,
and independent proof replay.

## MUFAC remediation

The existing MUFAC retained-utility failure remains immutable negative evidence. A replacement
claim is allowed only through a new protocol version:

1. diagnose on development data without consulting locked evaluation outcomes;
2. choose remediation and thresholds using development data only;
3. commit the model code, seed, data hashes, subject split, training budget, and stopping rule;
4. run a new evaluation once and preserve pass, fail, or inconclusive output;
5. report the original and new protocols side by side.

The preferred remediation is utility-constrained deletion-matched restart with checkpoint selection
based solely on development retained utility and forgetting/privacy constraints. If it does not pass
the frozen external threshold, the failure remains part of the project result.

## External evaluator kit

The repository will include a minimal offline kit containing:

- schema and case validators;
- source and protocol manifests;
- a public-key bundle verifier;
- a one-command evaluator that accepts an EraSeMap executable or result bundle;
- machine-readable result schema and deterministic report renderer;
- instructions for an independent reviewer to contribute signed results without sharing private
  infrastructure data.

The kit must be runnable without trusting the result renderer or importing EraSeMap's holdout-answer
module into the PCUG evaluator.

## Security and integrity

- Source snapshots are treated as untrusted input and parsed without code execution.
- Paths are normalized and confined to a newly created output directory.
- Existing outputs are never overwritten.
- Commitments use canonical JSON and SHA-256; proof bundles use the existing signature verifier.
- A committed public simulator key demonstrates reproducibility, not production signer identity.
- Secrets, personal data, biometric data, and organization credentials are excluded.

## Verification gates

Before publication:

- all unit, property, mutation-resistance, and negative-path tests pass;
- Ruff, strict mypy, package build, and at least 90% line coverage pass;
- a clean-room installation reproduces the one-command evaluator;
- the preregistration parent and reveal/result child commits are identifiable;
- manifests verify from `origin/main` in a fresh checkout;
- GitHub Actions succeeds on the final `main` commit.

## Claim boundary and remaining external gate

A successful study supports generalization to the frozen, independently sourced system structures.
It does not prove deletion in an unknown production system or resistance to an operator controlling
all instrumentation. Production validation still requires written authorization, representative
instrumentation, a separately controlled signing key, operational threat modelling, and an external
evaluator. The project will ship a ready-to-run organization pilot package rather than claim that
this gate has already been passed.

