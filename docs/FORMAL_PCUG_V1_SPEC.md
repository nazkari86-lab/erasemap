# Formal PCUG/CDC v1: frozen specification

Status: frozen before proof implementation on 2026-08-22.

## Scope

The formal model covers a finite, registered erasure topology. It does not claim that an
unregistered service, replica, backup, or model influence cannot exist. Instead it makes the
boundary explicit through a topology-completeness assumption.

## Theorem F1: replayed COMPLETE soundness

For arbitrary real residual paths and registered paths, assume:

1. every real active residual path is represented by an active registered path;
2. every registered path marked closed by a local verifier has no represented real active path;
3. all mandatory verification channels are sound;
4. replayed PCUG evaluation returns `COMPLETE`, meaning every registered path is closed and every
   mandatory channel passes.

Then no real active residual path exists and every mandatory real-world verification obligation
holds.

The result is intentionally conditional. It turns topology completeness and verifier soundness
into named, auditable proof obligations rather than silently assuming discovery is perfect.

## Theorem F2: finite exact CDC cost optimality

For a finite list of candidate action subsets, an arbitrary deterministic feasibility predicate,
and non-negative natural-number cost, the executable exhaustive selector either:

- returns `none` exactly when no listed candidate is feasible; or
- returns a listed feasible candidate whose cost is no greater than every listed feasible
  candidate.

This theorem covers the optimization contract used by `brute_force_cdc`. Production
`exact_cdc` is a branch-and-bound refinement; repository conformance tests must establish that it
returns the same complete-plan key as the exhaustive oracle over the registered bounded domain.

## Claim boundary

The Lean proof establishes the abstract theorems, not correctness of the Python interpreter,
database drivers, external topology registration, or local verifier implementations. Those links
are tested by executable conformance and replay checks. No production or independently authored
validation is inferred from this formal result.
