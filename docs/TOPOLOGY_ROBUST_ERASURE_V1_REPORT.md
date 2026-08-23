# Topology-Robust Erasure v1 — frozen result

## Result

The protocol and primary gates were committed at `320e437` before the TRE solver, physical runner,
verifier, and first result were implemented or executed. The first complete run passed every frozen
gate across 35 topology-shift cases.

| Frozen endpoint | Result | Gate |
|---|---:|---:|
| Declared topology scenarios | 8 | 8 |
| Shifted physical cases | 35 | 35 |
| Uncontrolled physical regenerations | 35/35 | 35 |
| Regenerations after nominal MSC | 35/35 | 35 |
| Regenerations after TRE plan | 0/35 | 0 |
| Production/oracle mismatches | 0/35 | 0 |
| Nominal selected cost | 3 | 3 |
| TRE selected cost | 7 | 7 |
| Blanket destruction cost | 60 | 60 |
| Shift-specific adversarial witnesses | 35/35 | 35 |

## Interpretation

The nominal registered map contains backup restore and its downstream ETL, vector rebuild, and
model retraining transitions. Exact nominal MSC selects `backup_restore_filter` at declared cost 3.
Seven shifted scenarios add every non-empty subset of checkpoint redeployment, legacy import, and
retry replay. Five frozen seeds are physically replayed per shift.

The nominal filter remains correct for its nominal topology but fails in 35/35 shifted cases because
at least one added carrier bypasses it. TRE evaluates one control set across all eight scenarios and
selects `persistent_subject_tombstone` at cost 7. It prevents all 35 physical recurrences while
costing 53 units less than blanket carrier destruction. The four-unit robustness premium is the
declared cost of protecting against the finite uncertainty envelope rather than one map.

## Solver verification

The production branch-and-bound selector matched a separately implemented exhaustive subset oracle
in the prospective cases. A separate deterministic conformance audit covers eight uncertainty
envelopes, all 64 permission masks, four adversarial cost catalogues, and both input orders:
**4,096/4,096** configurations with zero differences. This is bounded implementation conformance,
not independent evidence.

Lean checks `selected_tre_safe_for_every_scenario_and_minimum`: if executable robust feasibility
soundly implies temporal safety for each listed scenario, the selected finite candidate is safe in
every scenario and no more expensive than any other listed robust-feasible candidate. It does not
prove that the uncertainty envelope contains the real production topology.

## Claim boundary

TRE does not guarantee safety against arbitrary unknown transitions. The scenario catalogue,
mutation envelope, costs, controls, adapters, and execution are project-authored. Robust
optimization, uncertain set cover, temporal reachability, tombstones, and deletion test subjects are
prior art and are not claimed as inventions. The supported result is a prospective demonstration of
one subject-scoped, fail-closed temporal erasure contract under a finite declared topology envelope.

## Reproduction

```bash
PYTHONPATH=src python experiments/run_topology_robust_erasure_v1.py \
  --output /tmp/erasemap-tre-v1
python scripts/verify_topology_robust_erasure_v1.py \
  --result /tmp/erasemap-tre-v1/result.json
python scripts/verify_tre_conformance.py \
  --expected formal/tre-conformance-v1.json
```
