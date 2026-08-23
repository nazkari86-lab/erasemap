# Topology-Robust Erasure v1 preregistration

Registration date: 2026-08-23

This document and `benchmark/topology-robust-erasure-v1.json` are frozen before the TRE solver,
physical runner, result verifier, or first result is implemented or executed.

## Hypothesis

An exact robust stabilization plan selected across a finite declared topology envelope will prevent
physical subject-data regeneration in all frozen shifted scenarios, while the exact plan selected
only for the nominal topology will regenerate data after every frozen topology shift.

## Primary endpoints

The only primary endpoints are the machine-readable gates in the protocol. All gates must pass on
the first complete run. A failed first run remains part of project history and cannot be replaced by
an adaptive run under the same version label.

## Baselines

- nominal exact MSC: minimum-cost control for the backup-only topology;
- blanket destruction: removes every latent carrier at declared cost 60;
- TRE: minimum-cost single control set safe in all eight declared scenarios.

## Frozen limitations

Scenarios, mutations, control semantics, costs, seeds, adapters, and execution are project-authored.
The uncertainty envelope is finite and known to the robust solver. The experiment does not measure
probability of real missing transitions and does not establish performance outside the envelope.
It is not an independent hidden challenge or an organization pilot.
