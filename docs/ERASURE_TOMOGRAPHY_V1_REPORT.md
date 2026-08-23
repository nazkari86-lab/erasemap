# Erasure Tomography v1 report

Date: 2026-08-23

## Result

The prospective bounded local experiment passed every frozen gate without changing the protocol:

| Endpoint | Observed | Gate |
|---|---:|---:|
| Exact support recovery | 8/8 | 8 |
| Safe no-recurrence decisions | 2/2 | 2 |
| Negative cases rejected | 4/4 | 4 |
| False localizations | 0 | 0 maximum |
| Production/oracle mismatches | 0 | 0 maximum |
| Post-control physical recurrences | 0/8 | 0 maximum |
| Retained-subject losses | 0/8 | 0 maximum |
| Coded workflows | 3 | 4 individual checks |

The four negative cases violated sparsity, catalogue closure, workflow completion, or subject
isolation. All returned `UNVERIFIED`; none was converted into a convenient localization.

The exact certificate enumerated five allowed supports (empty plus four single mechanisms), found
minimum outcome distance 1 for `e=0`, and reported no indistinguishable support pair. A separately
implemented integer-bitmask oracle matched the production decoder. The wider conformance sweep
matched on 3,584/3,584 configurations.

## Live stock-service transfer

A separately preregistered opt-in experiment repeated the bounded contract inside the real
digest-pinned Redis image
`redis@sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2`.
Four project-authored Redis recovery workflows used different native data structures and operations.
The one-shot result localized 4/4 mechanisms, correctly handled the safe case, and recorded zero
false localizations, oracle mismatches, post-control recurrences, or retained-subject losses.

This is live stock-service transfer, not an independent or production-organizational experiment.

## What changed scientifically

PCUG, RSE, and TRE previously reasoned over declared transitions or a declared finite uncertainty
envelope. ET adds a bounded topology-acquisition experiment: externally observable coded deletion
workflows can distinguish which candidate recurrence mechanism is active before PCUG/TRE selects
and replays its control.

The new result does not remove the topology-completeness assumption globally. It replaces one
unverifiable open-world statement with a smaller, testable bounded statement: under catalogue
closure, `k=1`, `e=0`, complete workflow execution, isolated synthetic subjects, stable behavior,
and observable recurrence, the frozen signatures identify one active listed mechanism.

## Baselines

The individual audit recovered all four single supports with four checks. ET, the frozen random
matrix, and the greedy separating baseline recovered them with three rows in this small domain.
Therefore v1 demonstrates correctness and a 25% probe-count reduction relative to individual audit,
not superiority over every coded-design heuristic. The novel target is the fail-closed ET-to-PCUG/TRE
composition and physical deletion-recurrence application, not a new group-testing construction.

## Reproduction

```bash
PYTHONPATH=src:. python scripts/verify_erasure_tomography_v1.py
PYTHONPATH=src:. python scripts/verify_erasure_tomography_redis_v1.py
PYTHONPATH=src python scripts/verify_erasure_tomography_conformance.py \
  --expected formal/erasure-tomography-conformance-v1.json \
  --output /tmp/erasemap-et-conformance.json
lake build --wfail
```

## Limitations

- The catalogue and all faults were authored by the project.
- v1 assumes at most one active mechanism and no flipped observation.
- Three probes versus four is a small absolute reduction.
- Redis mechanisms are controlled analogues, not a production eGov or FaceID topology.
- The experiment cannot detect an unknown mechanism whose effect is observationally identical to a
  listed one.
- No independently authored hidden ET challenge or professional patent opinion exists.
