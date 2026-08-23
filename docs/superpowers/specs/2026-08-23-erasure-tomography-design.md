# Erasure Tomography design

Date: 2026-08-23
Status: approved research direction; design awaiting implementation review

## One-sentence idea

Erasure Tomography (ET) uses carefully combined synthetic-subject deletion experiments to localize
which bounded, externally exercisable workflow mechanisms can make deleted data reappear, then
passes those discovered mechanisms to EraSeMap's existing PCUG/TRE verification and repair layer.

## Problem in plain language

EraSeMap can audit and stabilize a declared data-flow map. Real organizations often have an
incomplete map: a backup import, retry queue, stale export, vector-index rebuild, or model
redeployment may exist operationally but be missing from the deletion register.

Opening every internal service is often impossible. ET instead creates non-person synthetic test
subjects, sends different subjects through deliberately different combinations of permitted
workflows, deletes them, activates recovery operations, and observes which subjects recur. The
pattern of recurrence is used to localize the responsible mechanism or, when the evidence is not
identifying, to return `UNVERIFIED`.

ET is a bounded black-box diagnosis layer. It does not claim to discover arbitrary infrastructure
from nothing or prove that no unknown mechanism exists.

## Research question

Within a frozen catalogue of candidate data-reactivation mechanisms and feasible test workflows,
can coded deletion probes localize up to `k` active erasure failures with fewer experiments than
testing every mechanism separately, without producing false localization when identifiability,
noise, or model assumptions fail?

## Contribution

The proposed contribution is the tested composition of:

1. synthetic subject-scoped deletion and recurrence probes;
2. workflow-constrained Boolean tomography;
3. an exact, fail-closed decoder with an explicit identifiability certificate;
4. counterexample paths that turn decoded mechanisms into PCUG transitions; and
5. exact TRE repair followed by physical recurrence replay.

The contribution is not group testing, Boolean network tomography, canary records, synthetic test
accounts, shortest paths, or robust set cover individually.

## Formal model

Let the frozen candidate catalogue be

```text
U = {u_1, ..., u_m}.
```

Each `u_i` is an externally exercisable mechanism class, such as backup restore, delayed retry,
legacy import, index rebuild, or model redeployment. The hidden vector

```text
x in {0,1}^m
```

marks mechanisms that can cause subject-data recurrence after the declared deletion procedure.
The confirmatory experiment assumes sparsity `||x||_0 <= k`; cases outside this bound must not be
reported as successfully localized.

The probe design is a binary matrix

```text
A in {0,1}^{t x m},
```

where `A[j,i] = 1` means that permitted workflow probe `j` exercises candidate mechanism `u_i` for
its synthetic subject. A noiseless observation is

```text
y_j = OR_i (A[j,i] AND x_i).
```

The implementation uses an exact subset decoder. For every candidate support `S` with `|S| <= k`,
it computes

```text
prediction(S)_j = OR_{i in S} A[j,i]
distance(S) = Hamming(prediction(S), y).
```

For a declared observation-error budget `e`, a support is admissible when `distance(S) <= e`.
The decoder localizes only when exactly one support is admissible. Zero or multiple admissible
supports fail closed.

## Identifiability certificate

The matrix compiler must not merely label a design "good." It emits a machine-checkable certificate
containing:

- the catalogue digest and ordered mechanism IDs;
- the exact feasible workflow matrix;
- `k`, `e`, and the complete enumerated support domain;
- the minimum pairwise Hamming distance between all allowed outcome vectors;
- whether every allowed support is uniquely decodable under the declared error budget;
- indistinguishable support pairs when the condition fails.

For bounded catalogues the certificate is verified by exhaustive enumeration independent of the
matrix-construction heuristic. The sufficient decoding condition is

```text
minimum outcome distance > 2e.
```

A traditional `k`-disjunct construction may be used when workflow constraints permit it, but the
project claim relies on the independently checked bounded certificate rather than on the matrix
label.

## Verdict contract

ET returns exactly one of:

- `NO_OBSERVED_RECURRENCE`: all observations are negative under a valid probe execution; this is
  not a global deletion-completeness claim;
- `LOCALIZED`: one candidate support is uniquely consistent with the observations and error budget;
- `AMBIGUOUS`: two or more supports remain consistent;
- `OUT_OF_MODEL`: no allowed support explains the observation within the declared error budget;
- `UNVERIFIED`: provenance, execution, identity isolation, observation, or certificate evidence is
  incomplete.

Every non-localized outcome remains fail-closed. `AMBIGUOUS` may report the complete equivalence
class but must not select a convenient member. `OUT_OF_MODEL` is evidence that the frozen catalogue,
sparsity bound, Boolean observation model, or noise budget is insufficient; it is not automatic
proof of a newly discovered component.

## Required assumptions

ET's localization claim is conditional on all of the following:

1. candidate catalogue closure for the confirmatory case;
2. faithful execution of each declared workflow row;
3. isolation between synthetic subjects;
4. recurrence observability for the subject commitment;
5. at most `k` active failing mechanisms;
6. at most `e` flipped probe outcomes;
7. stable mechanism behavior during one tomography round; and
8. no real person's identifier or biometric material in a probe.

Each assumption has a corresponding evidence field. Missing evidence forces `UNVERIFIED`.

## Formal results to implement

### Theorem 1: unique bounded recovery

If the certified outcome distance is greater than `2e`, the real support has size at most `k`, and
at most `e` outcomes are flipped, the exact decoder returns that support uniquely.

This is an application of error-correcting group-testing distance reasoning and is not claimed as a
new general theorem.

### Theorem 2: ambiguity soundness

If two allowed supports have outcome distance at most `2e`, there exists an observation vector
within error distance `e` of both whenever the corresponding Hamming balls intersect. A decoder
that chooses either support cannot justify unique localization. ET must return `AMBIGUOUS`.

### Theorem 3: fail-closed ET-to-TRE composition

Under ET's assumptions, sound translation from each localized mechanism into a PCUG transition,
and sound physical effects for selected TRE controls, a successful post-control replay excludes
recurrence through every localized mechanism in that experiment.

This theorem remains relative to the frozen catalogue and exercised workflows. It does not imply
safety against arbitrary unknown mechanisms.

The formalization should use finite sets and Boolean matrices in Lean. Executable conformance tests
must compare the production decoder with a separately implemented exhaustive oracle.

## Probe construction

The design has two layers:

1. **Exact verifier:** exhaustively determines the real bounded identifiability of any proposed
   feasible matrix. It is the scientific authority.
2. **Matrix constructor:** searches permitted workflow combinations for a matrix minimizing probe
   count, then total workflow cost, then lexicographic row order. It may use branch-and-bound but
   cannot weaken the exact certificate.

If no uniquely decodable matrix exists under the workflow constraints, construction returns
`INFEASIBLE`. It must never fabricate direct access to an internal mechanism that the deployment
cannot exercise.

## Physical experiment

### Infrastructure

The first implementation extends the existing Docker multi-service laboratory rather than creating
a disconnected simulator. The bounded catalogue should include at least these distinct mechanism
families:

- PostgreSQL base and materialized data;
- Redis cache or delayed queue replay;
- MinIO or equivalent backup/export restore;
- Qdrant vector-index reconstruction;
- MLflow-tracked model or artifact redeployment; and
- legacy identity import into the identity service.

Every mechanism requires a real adapter that can seed a synthetic subject commitment, invoke the
operation, perform deletion, trigger reactivation, and observe recurrence. Simulated mechanisms may
be used for unit tests but must be reported separately from physical Docker evidence.

### Synthetic subjects

Each probe uses a generated identity and random high-entropy subject commitment. No real face,
government identifier, phone number, or personal record is used. A probe manifest records the
generator version, seed commitment, workflow row, timestamps, adapter digests, and final observation.

### Frozen confirmatory protocol

Before the first confirmatory execution, commit:

- catalogue and container digests;
- feasible workflow constraints;
- selected matrix and its exact certificate;
- `k`, `e`, seeds, expected execution count, and stopping rule;
- hidden failing-support generator and reveal procedure;
- primary metrics and pass/fail gates;
- baseline implementations; and
- all exclusions and invalid-run conditions.

Development runs use separate seeds and supports. Confirmatory outputs are append-only. Changing the
decoder, matrix, catalogue, adapters, or gates after reveal creates a new version rather than
overwriting the run.

## Baselines

The primary comparison uses an equal workflow-execution budget where applicable:

1. **Individual audit:** one isolated probe per candidate mechanism; strong interpretable upper-cost
   baseline requiring `m` tests when all mechanisms are individually exercisable.
2. **Random feasible matrix:** same number of rows as ET, decoded by the same exact oracle.
3. **Greedy separating design:** repeatedly add the feasible row that separates the most currently
   indistinguishable support pairs.
4. **Declared topology only:** existing PCUG/TRE without tomography, demonstrating what an omitted
   mechanism does to the pre-existing contract.

ET succeeds scientifically only if it improves test efficiency over individual audit while retaining
zero false localization, or provides strictly greater bounded identifiability than random/greedy
designs at the same probe budget.

## Primary metrics and gates

Primary metrics:

- exact support-recovery rate;
- false-localization count;
- `AMBIGUOUS`, `OUT_OF_MODEL`, and `UNVERIFIED` counts;
- number and total declared cost of physical probes;
- certified maximum uniquely identifiable sparsity;
- post-TRE physical recurrence count; and
- retained synthetic-subject loss outside the deletion target.

Minimum confirmatory gates:

- zero false localizations;
- 100% exact recovery for all valid frozen supports within `k` and `e`;
- every deliberately non-identifiable design returns `AMBIGUOUS`;
- every missing-evidence case returns `UNVERIFIED`;
- every frozen out-of-model case is rejected rather than mislocalized;
- production decoder exactly matches the exhaustive oracle;
- zero post-control recurrence for localized mechanisms; and
- zero retained-subject loss in specificity controls.

Probe-count reduction is reported with the exact numerator and denominator, not only a percentage.

## Negative and ablation cases

The benchmark must contain cases designed to break the claim:

- identical mechanism columns;
- insufficient matrix rows;
- more than `k` active mechanisms;
- more than `e` flipped observations;
- a deliberately omitted candidate mechanism;
- subject cross-contamination;
- a skipped workflow step;
- an unobservable recurrence;
- unstable behavior across repeated rounds; and
- a localized transition whose adapter-to-PCUG mapping is missing.

These are expected to yield `AMBIGUOUS`, `OUT_OF_MODEL`, or `UNVERIFIED`, not a passing localization.

## Claim and falsification boundary

Supported after all gates pass:

> In the frozen, project-authored, bounded multi-service laboratory, the certified ET probe design
> uniquely localized up to `k` active recurrence mechanisms within error budget `e`, matched an
> independent exhaustive decoder, failed closed outside its assumptions, and enabled PCUG/TRE to
> prevent replayed recurrence through the localized mechanisms.

Not supported:

- arbitrary open-world topology discovery;
- production FaceID, eGov, bank, school, or hospital validation;
- completeness of an organization's candidate catalogue;
- legal compliance;
- independent external validation;
- discovery of a named internal component when two candidates have the same observable signature;
- invention of group testing, network tomography, canaries, or synthetic identities; or
- a worldwide-first or patentability claim.

The hypothesis is falsified if any valid frozen case is falsely localized, if the decoder disagrees
with the oracle, if an invalid case passes, or if a localized-and-controlled mechanism physically
regenerates the deleted synthetic subject.

## Prior-art boundary

The structured review must explicitly compare ET against:

- Boolean network tomography and group-testing identifiability;
- deletion canaries and synthetic privacy test subjects;
- provenance and automatic data-flow discovery;
- dependency-aware minimal erasure such as P2E2;
- machine-unlearning proofs and deletion-compliance definitions;
- verification-aware or obligation-carrying data models such as Chava; and
- EraSeMap's own RSE, MSC, and TRE.

The current targeted search did not identify the same end-to-end composition, but absence from a
targeted search is not proof of global novelty. Any novelty score remains provisional until a
documented systematic literature and patent review is complete.

## Deliverables

Implementation is complete only when the repository contains:

- immutable ET domain types and exact decoder;
- exact certificate verifier and constrained matrix constructor;
- independent exhaustive oracle;
- physical Docker adapters and synthetic-subject manifest;
- preregistration, append-only result records, and independent verifier script;
- Lean statements and checked proofs for the bounded contract;
- unit, property, mutation, conformance, and physical integration tests;
- a Russian and English explanation suitable for judges;
- an interactive demonstration showing probe pattern, recurrence vector, candidate equivalence
  class, localized path, selected TRE control, and replay result;
- updated claim matrix, prior-art review, scorecard, reproduction command, and CI gate.

## Implementation order after design review

1. Freeze the smallest honest formal contract and verdict schema.
2. Implement the exact oracle and certificate checker before the constructor.
3. Implement the decoder and prove oracle conformance.
4. Add negative cases before optimizing probe count.
5. Connect localized mechanisms to existing PCUG/TRE types.
6. Add physical adapters and prospective protocol.
7. Run confirmatory evidence once only after all gates and documentation are frozen.
8. Update project scoring only from recorded evidence, not expected results.
