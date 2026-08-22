# Proof-Carrying Unlearning Graph Protocol v1

Date: 2026-08-22

Status: implemented deterministic core; development-only benchmark registered; external and
production validation not established

## Research question

Can a path-aware, typed, multi-view verifier reduce false declarations of complete registered
subject deletion, and can Counterfactual Deletion Cut find a lower-cost verified intervention than
delete-all without hiding uncertain evidence?

The primary audit endpoint is false-complete rate on registered non-complete trials. A verdict is
false-complete when a method reports `COMPLETE` while the committed simulator state is
`INCOMPLETE` or `UNVERIFIED`. Planning cost is a separate endpoint; audit and planning records are
never pooled.

## Registered system

PCUG uses a typed directed graph with:

- physical nodes such as source, embedding, index, cache, backup, shared model, and API;
- material, processing, and request-scoped influence edges;
- admissible actions with integer costs and observed transitions;
- mandatory verification channels with raw value, one-sided upper bound, threshold, stratum, and
  evidence identifier;
- request-scoped source and terminal sets.

Every active subject-derived physical artifact is a terminal for deletion purposes, even if its
former parent was erased or it is no longer connected to an API. This prevents source deletion from
silently excusing a materialized embedding, index entry, cache, or backup.

A shared model is not labelled erased. The subject-to-model influence edge is instead classified as
`ACTIVE`, `CLOSED`, or `UNKNOWN`. A successful registered model audit may close that edge as
`BOUNDED_INFLUENCE`; it is not proof of zero information or physical model destruction.

## Three-valued composition

Local claims and the global verdict are fail-closed:

- `COMPLETE`: all registered physical terminals are closed, no active or unknown path remains, and
  every mandatory channel passes;
- `INCOMPLETE`: an active residual path or mandatory failed channel is established;
- `UNVERIFIED`: no active failure is established, but at least one path, transition, commitment, or
  mandatory channel is unknown.

Optional exploratory channels remain in the evidence but do not override mandatory passes. Raw
channels are conjunctive and are not collapsed into a weighted average.

## Counterfactual Deletion Cut

For action set `X`, the evaluator applies actions in canonical action-ID order, then recomputes graph
states, request paths, and channel composition. A transition without verified evidence becomes
`UNKNOWN`; declared coverage is not evidence.

CDC minimizes:

`sum(action.cost for action in X)`

subject to the replayed verdict being `COMPLETE`. Ties are resolved by total cost, number of actions,
and lexicographic action IDs.

- `brute_force_cdc` enumerates every permitted subset and acts as the small-case oracle.
- `exact_cdc` uses deterministic branch-and-bound and is property-tested against that oracle,
  including zero-cost and tied plans. The Lean v1 finite-selector theorem proves feasibility and
  minimum natural-number cost for the exhaustive contract; the bounded production conformance
  suite matched `exact_cdc` to that oracle in 3,072/3,072 action-order runs.
- `greedy_cdc` selects measured constraint reduction per unit cost and never claims optimality.
- a solver that cannot establish feasibility returns a non-complete plan rather than an optimistic
  result.

The conditional Lean soundness theorem separates two obligations that the software cannot infer:
every real active residual must be represented in the registered topology, and local path/channel
verifiers must be sound. Given those obligations, replayed `COMPLETE` implies absence of represented
real residuals and success of every mandatory obligation. It makes the claim boundary explicit; it
does not turn an incomplete inventory into global proof of erasure.

Cycles are handled as finite simple paths; revisiting a node within one candidate path is forbidden,
while alternate simple paths remain visible. Unknown edges are treated as potentially active.

## Proof bundle

Schema `erasemap-pcug-proof-v1` contains:

- canonical pre-graph and SHA-256 graph commitment;
- canonical CDC protocol and protocol commitment;
- selected actions, transitions, action costs, and result channels;
- hidden challenge commitment and revealed opening;
- request ID, producer revision, nonce, and optional previous-bundle hash;
- declared verdict and cost;
- Ed25519 key ID and signature.

The independent checker verifies the trusted Ed25519 key, signature, challenge opening, graph root,
protocol hash, request binding, action replay, final paths, mandatory channels, verdict, and cost. It
does not trust producer-supplied derived totals. Unknown JSON fields, missing fields, duplicate IDs,
noncanonical actions, non-finite numbers, and malformed types are rejected.

The demonstration wrapper is labelled `SYNTHETIC_SIMULATOR`. The controlled bundle contains a
pseudonymous request scope, but raw images, embeddings, or unrestricted model outputs are not placed
in the public package.

Development benchmark bundles use a deliberately public deterministic simulator key derived from a
domain-separated protocol hash. This makes benchmark signatures reproducible and is not a production
trust anchor. Interactive demo bundles use an ephemeral key written separately from the bundle.

## Verifier-aware faults

Development protocol `benchmark/pcug-protocol-v1.json` freezes three seeds, four display adapters,
five audit methods, three planning methods, and eight states:

- genuinely complete;
- source-only deletion;
- stale index;
- live backup;
- unknown model influence;
- a public single-view pass with hidden representation-recovery failure;
- artifact displacement into a cache;
- compound backup and model uncertainty.

Audit baselines are receipt-only, flat checklist, typed node audit, model-only, and full PCUG.
Planning comparators are delete-all, greedy CDC, and exact CDC. Application labels share the same
underlying graph semantics and therefore do not count as four independent datasets.

The holdout object is intentionally uncommitted and contains no seeds. The implementation refuses to
run it. Numerical holdout gates will be frozen only after development variance and failure modes are
reviewed.

## Existing model evidence bridge

The PCUG adapter imports the tracked v3 development, locked-internal, and content-unseen summaries.
It verifies the raw protocol SHA-256 and keeps strata separate. Mandatory channels are:

- forgotten embedding MSE ratio to stale, threshold `1.0`;
- largest paired privacy-advantage upper confidence bound, threshold `0.10`;
- retained verification-AUC loss, conservative upper bound threshold `0.01`.

The development and locked LFW strata pass those registered channels. MUFAC remains failed because
its retained-AUC loss exceeds the registered margin. PCUG cannot average that failed external
stratum away. A missing or mismatched protocol hash produces `UNVERIFIED`.

## Reproduction

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,real]'
.venv/bin/ruff check .
.venv/bin/mypy src/erasemap
.venv/bin/pytest

.venv/bin/erasemap pcug demo \
  --adapter faceid_style --seed 4409 \
  --output /tmp/pcug-demo.json \
  --public-key-output /tmp/pcug-public-key.pem
.venv/bin/erasemap pcug verify /tmp/pcug-demo.json \
  --public-key /tmp/pcug-public-key.pem
.venv/bin/erasemap pcug benchmark development \
  --protocol benchmark/pcug-protocol-v1.json \
  --output outputs/pcug-development-v1
```

## Claim boundary

The deterministic tests can establish implementation consistency. The controlled development run
can establish results only for registered simulator semantics. Existing v3 imports establish only
the named models, datasets, splits, and metrics. None of these establishes global deletion,
production security, legal compliance, demographic coverage, or applicability to Apple FaceID,
eGov, a bank, a school, or another operational system.
