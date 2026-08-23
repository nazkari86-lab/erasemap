# RSE multi-path v2 preregistration

**Frozen:** 2026-08-23, before implementation or execution of the v2 multi-path adapters.

## Question

Does RSE add measurable value beyond a strong snapshot PCUG audit when a currently dormant carrier
can be reopened by a registered future transition, and can exact MSC prevent several physically
different regeneration mechanisms with lower declared cost than path-specific controls or
destroy-all remediation?

## Fixed systems and paths

The local lab will use deterministic synthetic vectors and real local persistence formats. Four
separate latent mechanisms are registered:

1. AES-GCM backup and restore into the source database;
2. legacy offline export and import;
3. delayed retry queue replay into cache;
4. old model checkpoint redeployment.

Downstream ETL, vector rebuild, and model retraining transitions remain registered. The risk split
contains five single-path trials for each mechanism and ten mixed-carrier trials. Ten safe trials
retain carriers but install a persistent subject tombstone. Ten coverage-fault trials remove or
invalidate a required transition attestation.

## Fixed baselines

- **Snapshot PCUG:** all currently online artifacts and request-scoped influence are closed, every
  mandatory snapshot channel passes, and dormant carriers are represented as closed at the audit
  instant. It has no future-transition semantics.
- **Blanket carrier audit:** any retained latent carrier is always incomplete, even when every
  registered reactivation transition is guarded.
- **Destroy all / rebuild all:** declared cost 60.

Snapshot PCUG is expected to be specific on current state but may be false-complete on future
regeneration. Blanket carrier audit is expected to detect risk but may be false-incomplete on safe
guarded carriers. These directions are hypotheses, not recorded results.

## Frozen primary endpoints

The machine-readable gates are in `benchmark/regeneration-safe-erasure-v2.json`. No primary gate may
be changed after the preregistration commit. Failed gates remain published. Secondary endpoints may
be reported descriptively and cannot replace a failed primary endpoint.

## Exactness check

For every case, production `exact_stabilization_cut` will be compared with a separately implemented
exhaustive subset oracle using the same declared controls. A mismatch fails the experiment.

## Interpretation

A passing result would establish only that the registered temporal mechanism and physical adapters
behave as declared in this project-authored lab. It would not establish independently authored
topologies, sensor completeness, organizational deployment, legal compliance, or global permanent
erasure.
