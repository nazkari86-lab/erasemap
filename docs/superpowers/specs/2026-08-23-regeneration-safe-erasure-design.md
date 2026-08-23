# Regeneration-Safe Erasure (RSE) design

**Status:** approved for implementation on 2026-08-23.

## Research question

Can a subject-specific deletion audit detect whether ordinary registered future operations can
recreate a deleted residual, explain the shortest such operation sequence, and select the
least-cost set of controls that prevents every registered regeneration path?

## Claim boundary

RSE is a conditional systems guarantee. It is sound only relative to:

1. a finite, registered transition catalogue;
2. sound subject-residual predicates and transition adapters; and
3. complete, verified observations from every declared transition sensor.

It does not prove that an organization has no silent system, unknown copy, dishonest sensor, or
future operation outside the catalogue. Missing sensors, unknown transition identifiers, and
unverified observations fail closed and cannot produce `RSE_VERIFIED`.

## State and transition model

A state is a finite set of subject-scoped facts. Some facts are current residuals (for example,
`postgres`, `qdrant`, or `model`); others are latent carriers (for example, a recoverable offline
backup). A registered transition has required and forbidden facts and deterministic add/remove
effects. RSE computes the finite reachable closure from the post-deletion state.

The verdict is:

- `SNAPSHOT_INCOMPLETE` when the initial state already contains a residual;
- `REGENERATION_RISK` when a later reachable state contains a residual;
- `INCOMPLETE_COVERAGE` when no registered risk is found but transition coverage is not verified;
- `RSE_VERIFIED` when the complete registered closure contains no residual and coverage passes.

For `REGENERATION_RISK`, breadth-first exploration returns a shortest transition sequence and its
terminal state. Deterministic lexical tie-breaking makes the witness reproducible.

## Minimal Stabilization Cut

A stabilization control guards one or more subject-scoped transitions and has a non-negative
declared operational cost. The exact solver enumerates permitted control subsets, reruns RSE, and
returns the lexicographically deterministic minimum `(cost, number of controls, identifiers)` that
reaches `RSE_VERIFIED`. The first implementation is deliberately bounded to 24 controls.

This is not a recommendation to disable whole organizational workflows. An adapter may represent a
persistent tombstone, restore-time exclusion, post-restore replay, or ingest deny-list as a guard on
only the deleted subject's transition.

## Development experiment

The first vertical slice uses a real local SQLite database, JSON cache, NumPy vector index,
AES-GCM backup, and model manifest. A recoverable offline backup is excluded from the online
snapshot predicate but remains a latent fact. The frozen sequence is:

`backup_restore -> nightly_etl -> vector_rebuild -> model_retrain`.

The online snapshot baseline, RSE without controls, exact MSC, and rebuild-all baseline are compared
on fixed seeds. Primary development endpoints are regeneration false-complete count, RSE detection
count, post-control recurrence count, witness length, and declared control cost. This experiment is
project-authored and is not independent or production evidence.
