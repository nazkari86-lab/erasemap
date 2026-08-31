# EraSeMap

**One algorithm that finds, erases, and proves deletion of personal data.**

A successful local deletion response does not prove that a person's data disappeared. A usable copy may
remain in a cache, replica, vector index, backup, export, derived biometric template, or trained
model. It may also reappear later through restore, synchronization, or model deployment.

EraSeMap answers one stricter question:

> After a deletion request, can any registered copy, derivative, model influence, or recovery path
> still use this person's data?

## One algorithm, three steps

```text
Deletion request
      │
      ▼
┌─────────────┐   copies, derivatives, model influence,
│  1. FIND    │   and bounded hidden recovery paths
└──────┬──────┘
       ▼
┌─────────────┐   minimum sufficient physical actions plus
│  2. ERASE   │   machine unlearning or exact retraining fallback
└──────┬──────┘
       ▼
┌─────────────┐   recovery replay over time and a
│  3. PROVE   │   replayable, scope-bounded certificate
└──────┬──────┘
       ▼
COMPLETE_WITHIN_ENVELOPE / INCOMPLETE / UNVERIFIED
```

`EraSeMap` is the only public algorithm name. PCUG, CDC, GhostGraph, RSE, and MSC remain internal
implementation components and evidence labels, not separate algorithms a student must present.

### 1. FIND

EraSeMap builds a typed graph for one subject. Nodes represent raw records, biometric templates,
indexes, caches, backups, exports, and model influence. Edges represent copying, derivation,
synchronization, restoration, or deployment. When the registered map may be incomplete, bounded
safe probes filter possible recovery graphs. The result is either a graph, a full observable path
class, an out-of-catalogue warning, or `UNVERIFIED`.

### 2. ERASE

EraSeMap chooses the least-cost registered action set that closes every active physical and model
path. Physical actions can delete a row, vector, cache entry, export, or backup lineage. The model
action is machine unlearning evaluated against exact retraining. If a fast unlearning candidate
fails any frozen forgetting, retained-utility, privacy-proxy, or reload gate, EraSeMap does not call
the model erased; it falls back to exact retraining or returns `INCOMPLETE`.

### 3. PROVE

EraSeMap replays registered future operations such as restore, replica synchronization, cache
warming, index rebuild, and model redeployment. A certificate is ready only when the physical plan,
model channel, topology evidence, and temporal replay all pass. Missing evidence is never converted
into success.

## Decision rule

Let `P` mean that physical and model paths are closed, `D` that recovery-path evidence is actionable,
and `T` that registered temporal replay remains safe:

```text
COMPLETE_WITHIN_ENVELOPE  iff  P ∧ D ∧ T
INCOMPLETE                if   a residual or unstable path is demonstrated
UNVERIFIED                otherwise
```

The phrase *within envelope* matters: the certificate is limited to the registered topology,
verifiers, model, policy, and observation window. A relevant change invalidates it and requires a
new run.

## What is actually implemented

The production entry point is [`run_erasemap`](src/erasemap/unified.py). It exposes only the three
public stages above while composing:

- typed physical, derivative, and model paths;
- exact minimum-cost action selection;
- active recovery-path discovery under a bounded hypothesis catalogue;
- temporal stabilization and replay;
- fail-closed verdicts and certificate readiness;
- machine-unlearning experiments with exact-retraining reference and safe fallback.

The repository also includes real PostgreSQL/Redis/Qdrant process experiments, stock-service transfer
adapters, face-unlearning experiments, a Qwen2.5-1.5B adapter-unlearning study, formal Lean statements,
and offline verifiers.

## Strongest current evidence

These results test different parts of the same algorithm. They are not pooled into a misleading
single leaderboard.

| Question | EraSeMap result | Comparison | Scope |
|---|---:|---:|---|
| Does the audit avoid false deletion success? | `0/60` false `COMPLETE` | native status `45/60`; full typed audit `5/60` | project-authored frozen stock-service transfer |
| Can bounded hidden recovery paths be found efficiently? | `7` active probes | frozen random `13`; exhaustive `49` | project-authored frozen graph catalogue |
| Is targeted deletion cheaper than rebuild-all? | `17.64×` geometric-mean speedup; `94.62%` fewer written bytes | delete/rebuild-all | 20 paired local real-process trials |
| Can data return later? | `30/30` risks detected; `0/30` post-control recurrence | snapshot audit detects `0/30` latent risks | project-authored prospective temporal lab |
| Does the exact action solver match exhaustive search? | `3,072/3,072` orderings, `0` mismatches | separate brute-force oracle | bounded executable conformance |
| Does the temporal solver match exhaustive search? | `16,384/16,384` configurations, `0` mismatches | separate exhaustive oracle | bounded executable conformance |
| Did fast Qwen unlearning pass every gate? | **No** | exact adapter retraining remained the safe reference | real open 1.5B model; project-authored Kaggle trials |

The negative Qwen result is intentional evidence of the fail-closed rule: being faster is not enough
when forgetting or retained utility does not match the preregistered acceptance region.

Detailed evidence boundaries are in
[`docs/SCIENTIFIC_CLAIM_MATRIX.md`](docs/SCIENTIFIC_CLAIM_MATRIX.md) and
[`docs/COMPETITION_EVIDENCE_SCORECARD.md`](docs/COMPETITION_EVIDENCE_SCORECARD.md).

## Quick demonstration

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev,real]'
.venv/bin/erasemap showcase --repo-root . --output outputs/jury-showcase-v1
open outputs/jury-showcase-v1/index.html
```

The page begins with a deliberately incomplete example: the source row is deleted while a usable
template remains. It then shows evidence for FIND, ERASE, and PROVE with the scope beside each
number.

## Reproduce the checked release

```bash
./scripts/reproduce_release.sh core
```

Optional live profiles are:

```bash
./scripts/reproduce_release.sh transfer-live
./scripts/reproduce_release.sh ghostgraph-live
./scripts/reproduce_release.sh face-open
```

The core profile runs Ruff, strict mypy, the full pytest suite with at least 90% coverage, package
build, evidence verifiers, bounded oracle comparisons, and Lean.

## Formal scope

Lean proves conditional properties of the internal machinery:

- replayed completion excludes represented residual paths when topology coverage and local verifier
  soundness hold;
- the selected physical/model action set is minimum-cost among the registered permitted candidates;
- registered transition coverage lifts snapshot absence to temporal safety;
- the selected temporal control set is safe and minimum-cost under its explicit replay obligation;
- bounded recovery-graph filtering and minimax certificates are sound for a closed catalogue with
  sound observations.

These are not proofs that an unknown organization has exposed every store or transition. The exact
assumptions and counterexamples are documented in [`formal/README.md`](formal/README.md).

## Honest limits

- No production deployment in Face ID, eGov, a bank, or a government system is claimed.
- The public bank contains synthetic people and synthetic personal data.
- Stock services are real software, but mappings, faults, and execution are project-authored.
- The independently authored hidden challenge remains `NOT_COLLECTED`.
- The fast Qwen v1 and v2 candidates failed their conjunctive scientific gates; exact retraining is
  therefore still the safe model-erasure path.
- A certificate cannot cover stores or transitions that trusted instrumentation never registered.

## Project map

- [`src/erasemap/unified.py`](src/erasemap/unified.py) — one public algorithm.
- [`docs/ERASEMAP_UNIFIED_ALGORITHM.md`](docs/ERASEMAP_UNIFIED_ALGORITHM.md) — precise three-stage
  specification.
- [`docs/JURY_DEFENSE_RU.md`](docs/JURY_DEFENSE_RU.md) — short Russian defense script.
- [`competition/paper/EraSeMap_scientific_paper_RU.md`](competition/paper/EraSeMap_scientific_paper_RU.md)
  — Russian scientific paper.
- [`competition/paper/EraSeMap_scientific_paper_EN.md`](competition/paper/EraSeMap_scientific_paper_EN.md)
  — English scientific paper.
- [`formal/README.md`](formal/README.md) — formal claims and their assumptions.
- [`external_ghostgraph_challenge/README.md`](external_ghostgraph_challenge/README.md) — independent
  hidden-evaluation handoff.

The removed Erasure Tomography, GhostGraph-T, and standalone topology-robust experiment branches
remain recoverable from Git history. Their useful ideas are represented by the single FIND/ERASE/
PROVE pipeline; their separate names are no longer part of the active project.

## License

MIT.
