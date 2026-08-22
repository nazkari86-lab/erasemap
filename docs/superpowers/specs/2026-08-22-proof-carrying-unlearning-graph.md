# Proof-Carrying Unlearning Graph: research and system specification

Date: 2026-08-22

Status: approved in conversation; deterministic core and development benchmark implemented on
`feat/pcug-cdc`; external and production validation remain open

## 1. Decision

The next EraSeMap research core will be a **Proof-Carrying Unlearning Graph (PCUG)**. Its central
algorithm is the **Counterfactual Deletion Cut (CDC)**: given a committed graph of subject-derived
artifacts, observable sinks, admissible remediation actions, and artifact-specific verification
results, CDC computes the lowest-cost admissible intervention that closes every registered active
path and satisfies a preregistered residual-influence risk budget.

This is a prospective contribution. Until the experiments in this specification are completed,
the repository may say that PCUG is proposed and implemented, but may not say that it improves
detection, resists evasion, generalizes to production systems, or is the first such method.

## 2. Thirty-second explanation

Deleting a face image does not remove the embeddings, indexes, caches, backups, checkpoints, and
models derived from it. EraSeMap maps those paths, chooses the smallest valid set of deletion or
unlearning actions that cuts every path to a usable system output, and attaches independently
checkable evidence to every claim. If one path or proof is missing, it refuses to report complete.

## 3. Research gap and contribution boundary

Existing work separately covers provenance, machine unlearning, exact retraining comparisons,
per-instance deletion risk, and verification attacks. PCUG does not claim to invent any of these.
The research question is whether their composition can be made into a falsifiable system-wide
deletion decision rather than a collection of disconnected checks.

The proposed contribution has three inseparable parts:

1. a typed, path-level definition of registered deletion completeness;
2. an optimizer over actions that change graph reachability **and** quantitative model risk;
3. a proof bundle whose artifact, path, action, and verifier commitments can be replayed by an
   independent checker.

Generic provenance-to-forget-set lookup is outside the novelty claim. Generic set cover over faulty
artifacts is the existing EraSeMap baseline. Early stopping of unlearning is not the contribution.
A single membership-inference score is not a deletion proof.

### 3.1 Prior-art differentiation checklist

The literature review must test the contribution against at least these neighboring categories:

| Neighbor | Established idea | PCUG claim that must remain distinct |
|---|---|---|
| W3C PROV and lineage systems | machine-readable derivation and activity graphs | deletion-specific path feasibility plus replayed evidence semantics |
| SISA and approximate unlearning | reduce the cost of updating one trained model | choose and verify interventions across heterogeneous system artifacts |
| exact-retraining and deletion-privacy work | define or approximate a model-only reference | compose quantitative model evidence with operational path closure |
| per-instance unlearning privacy | estimate deletion difficulty for an item | decide a system-wide action cut and preserve channel-level uncertainty |
| provenance-guided forget sets | identify training items to remove | verify post-action state across model and non-model sinks |
| unlearning verification attacks | show that a known verifier can be gamed | commit a multi-view suite and measure residual false-complete decisions |
| deletion receipts | attest that an actor made a deletion claim | recompute the claim from committed graph, actions, evidence, and metrics |

If a prior work is found that implements all three proposed contribution parts, the novelty claim
must be narrowed or the design changed before submission. Similar terminology is not sufficient to
declare overlap; the comparison must use algorithms, threat models, inputs, outputs, and evaluated
claims.

The working novelty statement is:

> We propose a fail-closed method for registered subject deletion that computes a minimum-cost
> counterfactual cut over operational lineage paths and quantitative residual-influence constraints,
> then emits a replayable, multi-view proof bundle for the resulting system state.

Before external submission, this statement requires a documented literature and patent search. The
phrase "first in the world" is prohibited unless that search supports it.

## 4. Questions and preregistered hypotheses

### RQ1: detection

Does path-aware, typed, multi-view verification reduce false-complete decisions under hidden
single- and multi-artifact residual faults?

- **H1:** PCUG has lower false-complete rate than receipt-only, flat-checklist, untyped-traversal,
  node-set-cover EraSeMap v1, and model-only unlearning verification.

### RQ2: remediation

Can CDC find a lower-cost valid intervention than delete-all and greedy node cover while closing
every registered active path and satisfying the model-risk budget?

- **H2:** exact CDC has lower normalized cost than delete-all and no higher cost than greedy CDC on
  every instance where exact optimization completes.
- **H3:** exact CDC never returns a plan labelled complete when an active path or failed risk
  constraint remains under the registered simulator semantics.

### RQ3: verifier robustness

Does a committed hidden multi-view verifier detect deletion claims optimized to pass one known
verification channel?

- **H4:** PCUG has lower false-complete rate than each single-view verifier against verifier-aware
  providers.

### RQ4: transfer

Do the conclusions transfer across unseen graph topologies, identities, datasets, and model seeds?

- **H5:** the Wilson 95% lower bound for detection recall exceeds the preregistered floor on every
  locked transfer stratum.

Every hypothesis may fail. Failed and null results remain part of the project.

## 5. Formal model

### 5.1 Registered system

Let `G = (V, E)` be a directed typed multigraph committed before the deletion operation.

- `S_q` is the set of source artifacts associated with deletion request `q`.
- `O` is the set of observable or operational sinks.
- `P_q` is the set of registered directed paths from `S_q` to `O`.
- `A` is the set of admissible remediation actions.
- `c(a) >= 0` is the preregistered cost of action `a`.
- `T_a(G)` is the graph and artifact-state transition produced by action `a`.
- `Z` is the set of verification channels.

The graph separates **physical artifacts** from **subject-scoped influence claims**. A shared model
is a physical artifact and normally remains active for retained identities. For request `q`, an edge
such as `subject q USED_TO_TRAIN model m` carries an influence claim. Successful unlearning closes
or bounds that subject-scoped edge; it does not falsely label the shared model itself as erased.

An edge has one of three effective states: `ACTIVE`, `CLOSED`, or `UNKNOWN`. A conventional edge is
closed by a verified deletion/block transition at an appropriate cut point. A subject-to-model
influence edge is closed only for registered decision purposes when every mandatory model channel
passes its bound. Statistical closure is explicitly labelled `BOUNDED_INFLUENCE`, never physical
erasure or mathematical proof of zero information.

An artifact is not treated as deleted merely because it is unreachable in the software graph. Its
terminal state must also satisfy the evidence contract for its artifact type. Conversely, a shared
model node is not treated as physically erased merely because a subject-scoped behavioral verifier
passes.

### 5.2 Three-valued local claims

Every local claim has one of three states:

- `PASS`: the committed contract is satisfied;
- `FAIL`: a prohibited residual is established;
- `UNKNOWN`: evidence is missing, stale, malformed, out of scope, or statistically inconclusive.

Composition is fail-closed: `UNKNOWN` can never be promoted to `PASS`. The global verdict is:

- `COMPLETE` only when every registered active path is closed and every required risk constraint
  passes;
- `INCOMPLETE` when at least one active residual or failed risk constraint is established;
- `UNVERIFIED` otherwise.

### 5.3 Residual-influence channels

Each channel `z` produces a preregistered statistic `r_z` and a one-sided upper confidence bound
`U_z`. Initial channels are:

- storage absence and commitment consistency;
- nearest-neighbor recovery from the vector index;
- cache/API response recovery;
- checkpoint or backup accessibility;
- forgotten-identity verification behavior;
- identity-level membership inference;
- representation similarity to exact retraining;
- retained-set utility.

Raw metrics are retained. They are not collapsed into a weighted average that can hide one failed
channel. A model-related claim passes only if every mandatory channel satisfies its own threshold.

### 5.4 Registered deletion completeness

For intervention set `X subseteq A`, let `G_X` be the result of applying the actions in canonical
order. `X` is feasible if and only if:

1. no registered path in `P_q` remains active in `G_X`, with `UNKNOWN` edges treated as potentially
   active;
2. every terminal transition has valid artifact-specific evidence;
3. every mandatory channel has `U_z <= tau_z` or satisfies its registered equivalence margin;
4. every retained-utility lower bound remains above its registered floor;
5. all retention and authorization constraints are satisfied.

This definition is a guarantee only for the committed, instrumented graph and registered verifier.
It does not establish that no unknown copy exists outside the graph.

## 6. Counterfactual Deletion Cut

### 6.1 Optimization problem

CDC returns:

`argmin_X sum(c(a) for a in X)`

subject to the five feasibility conditions above. Tie-breaking is deterministic: total cost, action
count, then lexicographically sorted action IDs.

The key distinction from the existing planner is that an action is evaluated by the state obtained
after intervention, not solely by a declared set of covered node IDs. An action may:

- erase or cryptographically destroy an artifact;
- block an edge or sink under a policy that permits restriction;
- rebuild an index or invalidate a cache;
- retrain or unlearn a model and produce new measured risk bounds;
- reveal that a supposedly covered downstream artifact remains active.

Coverage declarations are therefore predictions to verify, not proof of successful remediation.

### 6.2 Solver strategy

The reference implementation will have two solvers:

- `exact_cdc`: exhaustive branch-and-bound for small registered action sets, used as the correctness
  oracle and benchmark reference;
- `greedy_cdc`: deterministic marginal feasible-path reduction per unit cost, used as a scalable
  comparator rather than an optimality claim.

Branch-and-bound may prune only with admissible lower bounds. A candidate plan must be replayed
through the transition model and verifier before it can be labelled feasible. Timeout returns
`UNVERIFIED` with the best known upper and lower cost bounds; it never returns an unproven optimum.

### 6.3 Path semantics

CDC operates on active paths rather than treating every descendant as equally prohibited. This is
necessary because:

- one action can close many paths at a shared cut point;
- retained artifacts may legally remain if an enforced block closes all prohibited uses;
- deleting a parent does not retroactively erase an already materialized child;
- unlearning changes a quantitative model claim rather than deleting a conventional node.

For a shared model, the solver may select among retraining, approximate unlearning, enforced
purpose-level blocking, or no feasible action. It changes only the request-scoped influence edge and
associated evidence. Retained identities and the physical model state remain explicitly represented.

Cycles are permitted only when graph decoding marks the involved edges as operationally meaningful.
The solver uses strongly connected components to construct a finite condensation DAG. Silent cycle
dropping is prohibited.

## 7. Proof-Carrying Unlearning Bundle

### 7.1 Commit-before-remediate protocol

Before an action executes, the system commits to:

- canonical pre-deletion graph root;
- request and pseudonymous subject scope;
- action catalogue, costs, and policy constraints;
- verifier code/version and protocol hash;
- mandatory channel names and thresholds;
- hidden challenge-set commitment;
- randomization seeds or a public randomness commitment;
- exact-retraining reference recipe.

After remediation, the hidden challenge set is revealed and checked against its prior commitment.
This prevents selecting only favorable probes after observing the updated system. It does not stop
an operator from bypassing all trusted instrumentation; that remains out of scope.

### 7.2 Bundle contents

The canonical bundle contains:

- schema version and algorithm version;
- pre- and post-intervention graph roots;
- selected actions and replay order;
- before/after path counts and shortest remaining counterexample, if any;
- artifact evidence envelopes and their hashes;
- verifier inputs or licensed reproducibility references;
- raw channel outputs, confidence bounds, thresholds, and pass states;
- retained-utility results;
- solver optimality status and cost bounds;
- environment, code revision, protocol, and dataset-manifest hashes;
- limitations and any `UNKNOWN` claims;
- signature and append-only receipt-chain link.

Sensitive images, embeddings, subject identifiers, and unrestricted model responses must not appear
in a public receipt. The public receipt contains commitments and aggregate results; the controlled
verification bundle may contain access-restricted evidence.

### 7.3 Independent checker

The checker must be smaller and less stateful than the producer. It verifies canonical encoding,
hashes, signatures, nonce replay, commitment openings, graph transitions, path closure, channel
thresholds, confidence-bound calculations, retained utility, and verdict composition. It does not
trust a producer-supplied `COMPLETE` field.

## 8. Verifier-aware threat model

The benchmark includes five provider behaviors:

1. **honest complete:** all required actions are applied;
2. **honest incomplete:** one or more actions fail or remain pending;
3. **receipt-only deception:** a validly signed completion statement is issued without remediation;
4. **single-view optimization:** the model is updated to pass a known forgotten-accuracy or MIA
   threshold while retaining signal detectable through another channel;
5. **artifact displacement:** influence is removed from one visible sink but preserved in an index,
   cache, checkpoint, alternate model, or backup.

PCUG is not claimed to resist a fully malicious operator controlling the instrumentation, checker,
keys, and all evidence sources. The experiment tests verifier-aware behavior inside a committed
controlled environment.

## 9. Experimental programme

### 9.1 Phase A: deterministic correctness

Use enumerated small graphs where every action subset can be evaluated. Required properties:

- exact CDC equals brute-force optimum;
- action-order canonicalization is deterministic;
- any surviving active path prevents `COMPLETE`;
- any mandatory `UNKNOWN` prevents `COMPLETE`;
- declared coverage without successful transition evidence does not count;
- graph encoding, bundle encoding, and checker verdict are reproducible.

Property-based tests vary branching, shared descendants, cycles, blocked edges, multi-action
interactions, zero-cost actions, infeasible cases, and tied optima.

### 9.2 Phase B: controlled system benchmark

Generate development and locked holdout graphs with:

- one and multiple subjects;
- 10 to 10,000 artifacts;
- shared indexes, caches, backups, and models;
- unseen topology templates in holdout;
- single and compound residual faults;
- misleading action-coverage declarations;
- verifier-aware provider behaviors.

Primary endpoint: false-complete rate on fault-positive trials.

Secondary endpoints:

- fault recall with Wilson 95% intervals;
- exact residual-path recall;
- false-alarm rate on genuinely complete trials;
- normalized remediation cost and exact-solver optimality gap;
- runtime and peak memory;
- proportion of honest `UNVERIFIED` outcomes;
- bundle replay agreement across clean environments.

### 9.3 Phase C: real-data model branch

Use the existing licensed/open face datasets and owner/identity-disjoint splits. For each registered
forget identity compare:

- no deletion;
- source-file deletion only;
- model-only approximate unlearning;
- deletion-matched retained-only restart;
- exact retraining without the identity;
- PCUG-selected system-wide plan.

The model verifier must report forgotten behavior, retained behavior, identity-level privacy attack,
representation comparison, compute, and uncertainty. Development, locked internal holdout, and
content-unseen external evidence remain separate strata. Results may not be pooled to conceal a
failed stratum.

### 9.4 Phase D: adversarial verifier evaluation

Construct attacks against each public single-view check without using hidden evaluation probes.
Measure how often:

- the attacked public check passes;
- another committed hidden channel detects the residual;
- the full PCUG composition incorrectly returns `COMPLETE`.

The adversarial transformation and attack budget must be frozen before hidden-set inspection.

### 9.5 Phase E: application adapters

Demonstrate the same core semantics through synthetic adapters for:

- FaceID-style access control;
- eGov-style identity verification;
- bank KYC;
- school access.

These are architecture simulators, not integrations with Apple, eGov, banks, or government
infrastructure. Application labels must not be counted as independent scientific datasets when the
underlying graph generator is shared.

## 10. Baselines and ablations

Required baselines:

- signed receipt only;
- flat store checklist;
- untyped descendant traversal;
- EraSeMap v1 typed node audit plus set-cover planner;
- model-only unlearning verifier;
- delete-all;
- greedy CDC;
- exact retraining reference where computationally feasible.

Required ablations:

- no path constraints, node coverage only;
- no hidden commitment, public verifier only;
- one verification channel at a time;
- no confidence bounds, point estimates only;
- no `UNKNOWN` state;
- no post-action replay, trust declared coverage;
- no external/content-unseen stratum.

An ablation is informative even when it matches the full method. Results must not be omitted because
they weaken the narrative.

## 11. Statistical protocol

- Freeze endpoints, directions, thresholds, seeds, exclusions, and stopping rules before holdout.
- Use identity/owner-disjoint splits whenever identities are the deletion unit.
- Report trial counts and denominators for every metric.
- Use Wilson intervals for binomial rates and paired bootstrap intervals for paired continuous
  differences.
- Treat a zero denominator as `null`, never as zero.
- Correct or hierarchically gate confirmatory multiple comparisons.
- Report per-identity distributions and worst-stratum results, not averages alone.
- Treat confidence intervals crossing a registered margin as `UNKNOWN`, not `PASS`.
- Do not tune on the locked holdout after any outcome is revealed.

The primary success criterion and numerical margins will be frozen in a separate protocol only
after development variance is measured. Choosing thresholds now without variance evidence would be
false precision.

## 12. Acceptance gates

### Engineering gate

- canonical schemas reject unknown, missing, duplicated, or non-finite fields;
- exact solver agrees with brute force on all enumerated small cases;
- checker independently recomputes the verdict;
- deterministic replay is byte-identical apart from explicitly excluded timestamps;
- full lint, type, unit, property, package, and CI checks pass.

### Scientific gate

- protocol and hidden commitments predate holdout results;
- all required baselines and ablations run;
- no holdout or external stratum is silently excluded;
- primary and safety outcomes include uncertainty;
- negative results and deviations are published.

### Claim gate

The strongest permitted claim is selected from evidence:

- implementation only: "we implemented";
- controlled validation: "reduced false-complete decisions in the registered simulator";
- real-data validation: add only the exact datasets/models tested;
- external generalization: allowed only after a separately sourced locked evaluation passes;
- production applicability: requires authorized instrumentation and evaluation in that production
  system.

## 13. Planned repository boundaries

The implementation should add isolated modules rather than overload the current v1 types:

- `src/erasemap/pcug_domain.py`: protocol, channel, transition, and proof types;
- `src/erasemap/cdc.py`: path semantics and exact/greedy solvers;
- `src/erasemap/proof_bundle.py`: canonical bundle and independent checking;
- `src/erasemap/multiview_verifier.py`: channel composition and confidence decisions;
- `benchmark/pcug-protocol-v1.json`: frozen benchmark configuration;
- `experiments/run_pcug_benchmark.py`: controlled experiment entry point;
- `tests/test_cdc.py`, `tests/test_cdc_properties.py`, `tests/test_proof_bundle.py`, and
  `tests/test_multiview_verifier.py`.

Existing `planning.py` remains the node-set-cover baseline. Existing v1 and v3 reports remain
historical evidence and must not be rewritten as PCUG results.

## 14. Demonstration contract

The visual demonstration has one deletion request and three columns:

1. **Before:** registered paths from one pseudonymous identity to source, embedding, index, cache,
   backup, checkpoint, model, and API sink;
2. **Naive deletion:** source is green but surviving paths remain red;
3. **PCUG:** selected actions, closed paths, channel results, cost, and signed proof status.

Clicking any verdict reveals the evidence or the shortest counterexample. The interface must visibly
distinguish measured, simulated, pending, and unavailable evidence. It may never display a production
eGov or FaceID badge for a simulator result.

## 15. Known limitations

- Registered completeness cannot detect unknown artifacts outside trusted instrumentation.
- Behavioral similarity to exact retraining is not a universal privacy proof.
- Hidden probes reduce one class of verifier gaming but do not defeat a fully malicious evidence
  provider.
- Minimum-cost results depend on the declared action model and cost semantics.
- Exact CDC is exponential in the worst case and is intended only for bounded benchmark instances.
- Simulator transfer does not establish production transfer.
- Face datasets do not represent every demographic or acquisition condition.

## 16. Implementation sequence

1. Freeze the v0 schema and deterministic graph transition semantics.
2. Implement brute-force feasibility evaluation as an oracle.
3. Implement exact CDC and prove it against the oracle through enumeration/property tests.
4. Implement greedy CDC as a named approximation baseline.
5. Implement proof commitments, canonical bundle encoding, and the independent checker.
6. Add deterministic non-ML channels and adversarial fixtures.
7. Add model channels using existing v3 artifacts without changing historical results.
8. Run development experiments and estimate variance.
9. Preregister numerical gates and create a hidden holdout commitment.
10. Run holdout once, preserve all outcomes, and render the demonstration from exported evidence.
