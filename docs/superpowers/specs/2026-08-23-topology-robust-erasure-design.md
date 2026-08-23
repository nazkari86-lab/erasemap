# Topology-Robust Erasure design

Date: 2026-08-23
Status: approved for implementation

## Research question

Can a subject-scoped erasure plan remain safe when the registered system map is not a single
topology but a finite, explicitly declared envelope of plausible missing regeneration transitions?

EraSeMap's existing Minimal Stabilization Cut (MSC) is exact for one registered transition system.
Topology-Robust Erasure (TRE) strengthens the decision object: it selects one permitted control set
that prevents regeneration in every topology inside a declared uncertainty envelope. It does not
claim safety for arbitrary unknown transitions.

## Decision contract

An envelope contains a nominal scenario, a finite set of alternative scenarios, and a maximum
mutation budget. Every scenario contains an initial state, transition catalogue, coverage record,
and the same residual semantics. A scenario is eligible only when its transition coverage is
complete and its mutation count is within the declared budget.

For controls `C`, scenarios `U`, declared costs `c`, and residual set `R_q`, TRE returns

```text
A* = arg min sum(c(a), a in A)
     subject to Reach_T(Apply(s_T, A)) intersect R_q = empty
     for every T in U.
```

The deterministic tie-break is total cost, number of controls, then lexicographic control IDs.
The result is one of:

- `OPTIMAL`: every eligible scenario reaches `RSE_VERIFIED` after the selected controls;
- `INFEASIBLE`: coverage is complete but no permitted registered control set protects all scenarios;
- `UNVERIFIED`: the envelope, coverage, or scenario semantics are insufficient for a robust claim.

The report includes the nominal MSC, robust MSC, robustness premium, per-scenario reports, and the
shortest adversarial regeneration witness defeated by the robust plan.

## Components

1. `temporal_robust.py`: immutable domain objects, validation, deterministic branch-and-bound exact
   selector, and adversarial-witness selection.
2. `temporal_robust_lab.py`: eight frozen topology scenarios formed by a nominal backup path and all
   subsets of three additional carrier paths; real local storage adapters replay the selected paths.
3. A separately implemented exhaustive subset oracle used only for comparison.
4. A prospective runner and independent result verifier. The protocol and gates are committed
   before implementation and first execution.
5. A deterministic conformance audit over uncertainty envelopes, permission masks, adversarial cost
   catalogues, and input orderings.
6. Lean theorems: selected robust feasibility implies safety for every listed scenario, the selected
   candidate is minimum-cost among robust-feasible candidates, and `none` is equivalent to absence
   of any listed robust-feasible candidate.

## Prospective experiment

The nominal map contains only `backup_restore`; its exact MSC is the path-specific backup filter at
cost 3. Seven shifted scenarios add one or more of legacy import, retry replay, and checkpoint
redeployment. Five frozen seeds are executed per shifted scenario.

For each case, the same physical carrier state is replayed three ways:

1. without controls, to establish a real regeneration path;
2. after the nominal MSC, to test failure under topology shift;
3. after the TRE plan, to test physical non-regeneration inside the frozen envelope.

The expected TRE solution is the shared persistent subject tombstone at declared cost 7. The
blanket carrier destruction baseline costs 60. These costs are declared experimental units, not
currency or measured production cost.

## Error handling and claim boundary

- Duplicate scenarios, transitions, or controls are rejected.
- A control may guard transitions present in only some scenarios; each replay uses the intersection
  with that scenario's transition IDs.
- Any incomplete scenario coverage makes the result `UNVERIFIED`, even if no residual is reached.
- Exceeding the exact-control limit fails rather than silently approximating.
- No passing result establishes discovery of real unknown transitions, production FaceID/eGov
  behavior, legal compliance, or independent confirmation.

## Testing

- unit tests for validation, tie-breaking, shortest witnesses, nominal failure, robust success,
  incomplete coverage, infeasibility, and order invariance;
- property tests over costs and permissions;
- exact solver versus separately implemented exhaustive oracle;
- physical local replay for every frozen shifted case;
- Lean build with warnings as errors;
- inclusion in the release reproduction script and GitHub Actions.

## Novelty boundary

TRE does not claim to invent robust optimization, set cover, network interdiction, uncertainty
sets, temporal reachability, tombstones, canary deletion tests, or lineage. The research hypothesis
is the composition of a subject-scoped temporal erasure contract, finite topology uncertainty,
fail-closed evidence coverage, shortest adversarial regeneration witnesses, and an exact
minimum-cost stabilization plan checked against every declared topology. No worldwide-first or
freedom-to-operate claim is made.
