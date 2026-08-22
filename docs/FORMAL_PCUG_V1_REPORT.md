# Formal PCUG/CDC v1 report

## Result

**PASS.** The frozen claims in `FORMAL_PCUG_V1_SPEC.md` were implemented in Lean 4.33.1 and
machine-checked with no `sorry` or `admit` placeholders.

The specification was committed first as `f79940e`. The proof implementation does not weaken its
claim boundary.

## Checked contributions

### F1: conditional replay soundness

`EraSeMap.PCUG.replayed_complete_sound` proves both conclusions of a replayed `COMPLETE`:

1. no real active residual path remains; and
2. every mandatory real-world channel obligation holds.

The proof consumes three explicit assumptions rather than hiding them:

- active real residuals are represented in the registered topology;
- closing a represented path is sound for the corresponding real residual;
- a mandatory channel pass implies its real-world obligation.

The accompanying checked witnesses show why the boundary matters:

- `unregistered_residual_counterexample` closes every registered path while a hidden residual
  remains when topology completeness is absent;
- `unsound_channel_counterexample` declares every channel passed while a real obligation fails
  when channel soundness is absent.

### F2: finite CDC optimality

`EraSeMap.ExactCDC.selected_is_feasible_minimum` proves that the executable finite selector returns
a listed feasible candidate whose non-negative cost is no greater than every listed feasible
candidate. `select_eq_none_iff` proves that `none` is returned exactly when no listed candidate is
feasible.

This is an algorithmic theorem over arbitrary candidate types, feasibility predicates, and natural-
number costs. It is not a theorem obtained by defining “optimal” to mean “whatever the selector
returned.”

## Production conformance

The Python branch-and-bound implementation was compared with its exhaustive oracle across:

- 512 cost/permission catalogs;
- all six input orderings for each catalog;
- 3,072 total exact/oracle runs;
- zero-cost, tied-cost, forbidden-action, feasible, and infeasible catalogs.

Result: **3,072/3,072 exact matches, zero mismatches**. The canonical record digest is
`29009b11fc3228f7458ab7e8f66fb58e4247c0b4bdfea9195e4d7f5e4fbe30fe`.

## Reproduction

```bash
lake build
python scripts/verify_formal_conformance.py \
  --expected formal/conformance-v1.json \
  --output /tmp/formal-conformance.json
```

GitHub CI pins Lean 4.33.1, runs `leanchecker`, treats warnings as errors, and audits the compiled
environment against an axiom allowlist that excludes `sorryAx`, in addition to the Python
conformance gate.

## Limitations

- Lean checks the abstract PCUG/CDC core, not CPython, external drivers, or organization systems.
- The Python bridge is bounded systematic conformance, not a formal semantics proof of Python.
- Topology completeness and local verifier soundness remain deployment proof obligations.
- No independent evaluator or production FaceID/eGov organization is claimed.
- The result does not repair or relabel the separate MUFAC approximate-unlearning utility result.
