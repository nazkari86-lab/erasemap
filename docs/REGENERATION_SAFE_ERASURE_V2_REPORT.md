# Regeneration-Safe Erasure multi-path v2

## Prospective result

The v2 protocol and all primary gates were committed to public `main` at `110bb63` before the
multi-path adapters were implemented or executed. The first run passed every frozen gate across 50
cases.

| Frozen endpoint | Result | Gate |
|---|---:|---:|
| Registered risk cases | 30 | 30 |
| RSE risk detections | 30/30 | 30 |
| Snapshot-PCUG false-complete after future replay | 30/30 | 30 |
| Safe guarded-carrier specificity | 10/10 | 10 |
| Blanket-carrier false-incomplete on safe cases | 10/10 | 10 |
| Coverage faults returned fail-closed | 10/10 | 10 |
| Post-MSC physical recurrences | 0/30 | <= 0 |
| Exact production/oracle mismatches | 0/30 | <= 0 |
| Maximum selected control cost | 7 | <= 7 |

## What changed from v1

V1 established a minimal backup-restore mechanism. V2 adds four physically different latent
carriers: an AES-GCM backup, legacy export, retry queue, and old model checkpoint. It contains five
single-carrier trials per family and ten mixed-carrier trials. Single paths select their cheaper
path-specific filter (declared cost 2–5); mixed cases select the persistent subject tombstone at
cost 7 instead of four path filters costing 14 or destroy-all costing 60.

The production MSC solver is now branch-and-bound. A separately implemented exhaustive subset
oracle matched its action identifiers and costs in all 30 prospective risk cases. Hypothesis-based
tests additionally vary every control cost and permission mask.

A separate deterministic conformance audit covers the complete frozen finite domain formed by all
16 carrier subsets, all 64 permission masks, eight cost catalogues designed to exercise ties,
zero-cost controls and shared-versus-path-specific trade-offs, and both input orders. Production
branch-and-bound matched the separately implemented exhaustive subset oracle in **16,384/16,384**
configurations. This is bounded software verification, not another prospective experiment or
external evidence.

Lean additionally checks `selected_msc_safe_and_minimum`: if replay feasibility soundly implies
temporal safety for the registered transition semantics, the exact finite selector returns a safe
listed candidate no more expensive than any other feasible listed candidate. The theorem preserves
the coverage and local-soundness assumptions rather than claiming they hold automatically.

## Baseline interpretation

The snapshot PCUG baseline is intentionally strong for its stated snapshot claim: every online
residual and request-scoped influence is closed and a mandatory absence channel passes. Dormant
carriers are represented but closed at that instant. It therefore returns `COMPLETE`; future replay
then recreates an online residual in all 30 risk cases. This does not show that PCUG is defective or
that it would ignore an active backup. It shows that a snapshot property and a temporal invariant
are different claims.

The blanket-carrier baseline safely rejects every latent carrier, but also rejects all ten safe
cases where a persistent tombstone guards every registered reactivation transition. RSE separates
carrier existence from carrier reachability.

## Claim boundary

The topologies, adapters, costs, vectors, controls, sensors, and execution are project-authored.
The result is prospective with respect to the v2 endpoints, but not independent. It demonstrates
the registered mechanism in local formats; it does not establish complete discovery of real
organizational transitions, production FaceID/eGov behavior, legal compliance, or permanent global
erasure. The next evidence-changing event remains an externally authored temporal hidden challenge
or authorized organization pilot.

## Reproduction

```bash
PYTHONPATH=src python experiments/run_regeneration_safe_erasure_v2.py
python scripts/verify_regeneration_safe_erasure_v2.py
```
