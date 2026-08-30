# Open Transfer Challenge v1 preregistration

Registration date: 2026-08-23

This document and `benchmark/open-transfer-v1.json` are frozen before the transfer scoring module,
stock-service adapters, live runner, offline verifier, or first complete run is implemented or
executed. Container tags were resolved to immutable multi-platform OCI digests at registration.

## Research question

Can one unchanged subject-erasure decision contract avoid false-complete deletion decisions across
three stock open-source service families—Keycloak identity lifecycle, MLflow run/artifact lineage,
and Qdrant biometric-vector retrieval—when every method receives the same registered observations?

## Confirmatory matrix

The matrix contains exactly 60 cases: three families crossed with five frozen seeds and four fault
states. The states are safe native deletion, a surviving materialized derivative, regeneration from
a registered recovery carrier, and incomplete observation coverage. The five Qdrant inputs are
unmodified normalized 64×64 samples from five held-out Olivetti subjects, flattened row-major. The
MLflow cases attach the same public-input lineage to real run artifacts. Keycloak users are synthetic.

Development Olivetti subjects 35–39 and confirmatory subjects 0–4 are disjoint. No learned transform
is fitted to the public face vectors. Source URL, checksum, selection, and preprocessing are frozen
in the machine protocol.

## Comparators

- `native-success` trusts the documented deletion response and primary-object absence;
- `typed-node-audit` inspects the same registered nodes but does not replay transitions;
- EraSeMap evaluates proof channels and registered temporal transitions and must fail closed when a
  mandatory observation is unavailable.

## Primary gates

All gates must pass together:

- exactly 60 valid cases from three families and three leave-one-family-out rotations;
- zero EraSeMap false-complete decisions;
- all 15 coverage-fault cases return `UNVERIFIED`;
- zero physical recurrences after the selected control;
- zero retained-subject losses;
- at least one witnessed native false-complete decision in every family;
- no specificity loss relative to typed-node audit on safe cases;
- zero exact-control/oracle mismatches;
- one identical frozen core hash in every family and rotation.

Secondary latency, bytes, path length, adapter size, or robustness-premium measurements cannot
rescue a failed primary gate. A failed first complete run remains part of history; any adaptive
change to the matrix, truth, or thresholds requires a new protocol version.

## Leave-one-family-out boundary

Each family is held out in one rotation. The held-out run may use its already frozen declarative
adapter but may not change the registered path, temporal replay, mandatory channels, comparator
rules, metrics, or
gates. A changed core hash is a transfer failure.

## Claim boundary

All mappings, faults, case construction, and execution are project-authored. A passing result would
show bounded transfer across three real stock service processes and public/synthetic inputs; it
would not establish independent generalization, production FaceID/eGov/KYC behavior, legal
compliance, organization deployment, or coverage of arbitrary unknown transitions. The human
usability and independent evaluator packages are readiness artifacts until real signed submissions
exist.
