# Machine-checked PCUG/CDC core

The root [`EraseMapFormal`](../EraseMapFormal/) Lean library contains the formalization frozen in
[`docs/FORMAL_PCUG_V1_SPEC.md`](../docs/FORMAL_PCUG_V1_SPEC.md); this directory holds its
reproduction guide and bounded production-conformance record.

The machine-checked contribution has two parts:

- `EraSeMap.PCUG.replayed_complete_sound`: under explicit topology-completeness and verifier-
  soundness obligations, replayed `COMPLETE` rules out represented real residual paths and
  discharges every mandatory channel obligation;
- `EraSeMap.ExactCDC.selected_is_feasible_minimum`: the executable finite selector returns a
  listed feasible candidate whose natural-number cost is no greater than any other listed
  feasible candidate. `select_eq_none_iff` proves the fail-closed no-solution case.
- `EraSeMap.PCUG.Boundary` contains checked counterexamples showing that a hidden residual can
  survive without topology completeness and that a channel pass is meaningless without channel
  soundness. These demonstrate that the main theorem's assumptions are necessary claim boundaries.

Build locally with the pinned Lean toolchain:

```bash
lake build
```

GitHub CI additionally runs `leanchecker`, treats warnings as errors, and audits the compiled
environment against a strict axiom allowlist that excludes `sorryAx`. The production Python
branch-and-bound implementation is linked to the exhaustive optimization contract by:

```bash
python scripts/verify_formal_conformance.py \
  --expected formal/conformance-v1.json \
  --output /tmp/formal-conformance.json
```

The committed v1 report covers 512 cost/permission catalogs and all 3,072 action orderings with
zero differences between `exact_cdc` and `brute_force_cdc`. This is bounded implementation
conformance, not a proof of the Python runtime or an external deployment.
