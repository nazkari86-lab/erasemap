# Machine-checked core of the single EraSeMap algorithm

The root [`EraseMapFormal`](../EraseMapFormal/) Lean library checks conditional properties used by
EraSeMap's three public stages: FIND, ERASE, and PROVE. Internal theorem namespaces are evidence
labels, not additional public algorithms.

## FIND: bounded recovery-path evidence

`EraseMapFormal/GhostGraph.lean` proves four contracts for a closed finite graph catalogue with
sound observations:

- a sound listed truth survives version-space filtering;
- a singleton survivor is the true listed graph;
- query-indistinguishable graphs have identical consistency decisions;
- every emitted finite minimax certificate contains the selected query and its exact
  lexicographic-minimum obligation.

These results do not prove that an unknown production topology is present in the catalogue, and
one-step minimax is not claimed to optimize the entire adaptive decision tree.

## ERASE: represented-path soundness and minimum action cost

- `EraSeMap.PCUG.replayed_complete_sound` proves that replayed `COMPLETE` rules out represented real
  residual paths and discharges mandatory channels, assuming topology completeness and sound local
  verifiers.
- `EraSeMap.PCUG.Boundary` contains checked counterexamples showing why those assumptions are
  necessary.
- `EraSeMap.ExactCDC.selected_is_feasible_minimum` proves that the finite selector returns a listed
  feasible candidate whose natural-number cost is no greater than any other listed feasible
  candidate. `select_eq_none_iff` proves the fail-closed no-solution case.

Model influence is a mandatory PCUG channel. Lean checks the composition contract, not the empirical
claim that a particular unlearning method succeeded. That claim is decided by the frozen model
experiment gates, with exact retraining as fallback.

## PROVE: temporal safety

- `EraSeMap.RSE.observed_coverage_lifts_to_real_safety` proves that snapshot absence extends to every
  real reachable state when every real transition is covered by the registered relation and every
  registered transition preserves absence.
- `EraSeMap.RSE.missing_coverage_allows_regeneration` shows why the coverage premise cannot be
  removed.
- `EraSeMap.ExactMSC.selected_msc_safe_and_minimum` combines finite exact selection with the
  replay-feasibility obligation: the selected registered controls are temporally safe under that
  obligation and no more expensive than any other listed feasible set.
- `EraSeMap.ExactMSC.no_msc_iff_no_feasible_candidate` proves the fail-closed no-plan case.

These theorems do not establish that an external organization registered every future transition.

## Build and executable conformance

```bash
lake build --wfail
```

GitHub CI also runs `leanchecker` and an axiom audit that excludes `sorryAx`.

The physical/model action selector is compared with a separately structured exhaustive oracle:

```bash
python scripts/verify_formal_conformance.py \
  --expected formal/conformance-v1.json \
  --output /tmp/formal-conformance.json
```

The committed report covers 512 cost/permission catalogues and all 3,072 action orderings with zero
production/oracle differences.

The temporal selector has a separate conformance gate:

```bash
python scripts/verify_rse_conformance.py \
  --expected formal/rse-msc-conformance-v1.json \
  --output /tmp/rse-msc-conformance.json
```

It covers 16 carrier subsets, 64 permission masks, eight adversarial cost catalogues, and both input
orders: 16,384 configurations with zero production/oracle differences.

Both are bounded implementation-conformance results. They are not proofs of the Python runtime or
of open-world production coverage.
