# EraSeMap: Proof-Carrying, Regeneration-Safe Erasure Auditing for Biometric Systems

**Research paper — English version**
**Author:** ____________________
**Affiliation:** ____________________
**Supervisor:** ____________________
**Year:** 2026

## Abstract

Deleting a biometric record from the primary database does not necessarily remove its derived template, search index entry, cache copy, backup, audit replica, or influence on a trained model. This paper presents EraSeMap, a subject-scoped erasure auditor built around a Proof-Carrying Unlearning Graph (PCUG). It refuses to report completion while a residual path, failed verifier, unknown mandatory channel, or unsuccessful action replay remains. The method produces one of three verdicts—COMPLETE, INCOMPLETE, or UNVERIFIED—together with the shortest residual counterexample and a minimum-cost Counterfactual Deletion Cut (CDC). Residual paths define what may still be usable; typed verifier channels define required evidence; and a finite optimization problem selects the least-cost permitted action set whose simulated post-action state passes the same frozen audit. Lean 4 machine-checks conditional replay soundness and finite CDC optimality. The production branch-and-bound selector matched an exhaustive oracle in 3,072 of 3,072 systematic runs. In a project-authored mechanism stress test, EraSeMap produced 0/75 false-complete verdicts while a node-state-only typed audit produced 75/75. On a source-locked benchmark derived from five official external structures, EraSeMap produced 0/100 false completes and 25/25 correct completes, but tied the strongest typed baseline. In a preregistered local multi-service experiment using real PostgreSQL, Redis, and Qdrant processes, encrypted backups, and a ridge model, targeted CDC reached verified completion in 20/20 paired trials, retained all 249 non-deleted records per trial, matched rebuild-all ridge weights within 2.22 × 10⁻¹⁵, reduced written bytes by 94.62%, and achieved a 17.64× geometric-mean speedup over rebuild-all (paired bootstrap 95% CI: 16.39×–18.98×). A bounded adaptive face-unlearning experiment passed its frozen utility, privacy, and speed gates, but is not independent confirmation. The results support the feasibility and internal correctness of proof-carrying erasure auditing while leaving topology completeness, independent hidden evaluation, and production deployment as explicit open obligations.

A separately preregistered first-run sequential study passed all six frozen gates over 25 release transitions; the largest upper 95% confidence bound for additional retained-user membership advantage relative to exact retraining was 0.00624 against a 0.05 limit. This bounded result is not independent confirmation or certified privacy.

The Regeneration-Safe Erasure (RSE) extension tests a different failure mode: data absent now can return after backup restore, legacy import, retry replay, or checkpoint redeployment. Its multi-path v2 protocol was publicly committed before implementation. The first run detected 30/30 registered temporal risks, verified 10/10 guarded safe cases, failed closed on 10/10 coverage faults, and produced 0/30 physical recurrences after the exact Minimal Stabilization Cut (MSC). Lean checks conditional MSC safety and minimum cost, while production branch-and-bound matched a separate exhaustive oracle in 16,384/16,384 finite-domain configurations. These are project-authored prospective and verification results, not independent or production evidence.

Topology-Robust Erasure (TRE) strengthens MSC from one map to a finite declared uncertainty envelope. Its protocol was also committed before implementation. In the first run, nominal MSC regenerated data in 35/35 topology shifts, whereas one exact TRE plan regenerated data in 0/35, cost 7 versus blanket destruction at 60, and matched an exhaustive oracle. Production TRE additionally matched the oracle in 4,096/4,096 systematic configurations. The guarantee is conditional on the real topology belonging to the declared envelope.

Erasure Tomography (ET) adds a bounded topology-acquisition layer. Three coded synthetic-subject workflows distinguish the empty support and four single recurrence mechanisms. The frozen first run recovered 8/8 valid supports, rejected 4/4 assumption violations, and recorded zero false localization, oracle mismatch, post-control recurrence, or retained-subject loss. A separate preregistered digest-pinned Redis run recovered 4/4 mechanisms and the safe case. Lean checks zero-error separation and limits ET-to-TRE safety to listed localized mechanisms. These results require catalogue closure, `k=1`, `e=0`, complete workflows, isolated synthetic subjects, stable behavior, and observable recurrence.

A further preregistered transfer study executed one frozen contract in 60 cases on digest-pinned stock Keycloak, MLflow, and Qdrant services. EraSeMap produced 0 false-complete decisions, failed closed on 15/15 coverage faults, matched a separate exhaustive control oracle in 60/60 cases, and produced no retained-subject loss or post-control recurrence. Native-success produced 45 false completes and the typed-node snapshot audit produced 5. Qdrant used preregistered public Olivetti face vectors; identities, commitments, mappings, faults, and execution remained project-authored, so this is live stock-service transfer evidence rather than independent or production validation.

GhostGraph adds active topology discovery when the registered recurrence map itself is uncertain. It maintains a finite version space of candidate graphs and selects the next synthetic intervention by an exact minimax partition rule. In the frozen v2 comparison, active minimax used 7 probes, returned 3 exact graph and 2 path-class recoveries, detected the outside-catalogue case, failed closed on missing evidence, and produced no false-confident output, oracle mismatch, recurrence after control, or retained-subject loss. Frozen random required 13 probes and exhaustive nonadaptive testing 49; passive declared lineage and flat tomography each produced one false-confident output. A separate run over digest-pinned Redis, Keycloak, MLflow, and Qdrant used 5 probes across 5 cases with the same safety endpoints. These remain project-authored bounded and local results. An independently signable blind challenge v2 is executable but has status `NOT_COLLECTED` until an outside evaluator authors and runs it.

**Keywords:** biometric erasure; machine unlearning; data lineage; temporal erasure; regeneration witness; verifiable deletion; residual path; minimum-cost remediation; fail-closed audit.

## 1. Introduction

Biometric systems rarely store a person’s data in one place. An enrollment image can generate a face template; the template can be indexed in a vector database and cached; training records can influence a model; backups can preserve earlier states; and an audit service can retain metadata. Removing only the source row can therefore create a dangerous false-complete claim: the interface says “deleted,” while a usable derivative remains.

This problem matters beyond one application. Identity proofing, border control, banking KYC, school access, and face verification use different infrastructure, but they share the same operational question: after a subject requests erasure, which reachable artifacts can still reproduce, match, restore, or statistically reveal the subject’s information? A deletion receipt alone cannot answer that question. A valid signature proves who signed a statement and that the statement was not altered; it does not prove that every underlying deletion action succeeded.

Machine unlearning addresses removal of training-data influence from models. Data provenance represents how entities and activities are connected. Proof-of-deletion research studies verifiable claims. Optimization methods can choose low-cost action sets. Each area solves part of the problem. EraSeMap studies a narrower systems question: can these components be combined into one subject-scoped, fail-closed contract that returns a reproducible verdict and an actionable correction instead of an unsupported promise? The core representation is the **Proof-Carrying Unlearning Graph (PCUG)**; its remediation object is the **Counterfactual Deletion Cut (CDC)**.

The research question is:

> Can a proof-carrying residual-path audit prevent false claims of complete biometric erasure and select a verified minimum-cost remediation plan across heterogeneous storage and model artifacts?

**Objective.** Develop and test a reproducible method that detects unresolved subject-level erasure obligations, explains the shortest known failure path, and selects a permitted low-cost correction that must pass a repeated audit.

**Object of study.** Operational data-erasure workflows in heterogeneous biometric information systems.

**Subject of study.** The relationship between typed lineage, mandatory quantitative evidence, replayed actions, false-complete decisions, and remediation cost.

**Hypothesis H1.** On cases where physical node states appear closed but a mandatory evidence or replay obligation fails, PCUG has a lower false-complete rate than an audit based only on typed node states. The null hypothesis is that PCUG provides no reduction.

**Hypothesis H2.** In a registered multi-service topology, exact CDC can use less measured time and fewer written bytes than rebuild-all while reaching the same replayed COMPLETE verdict and retaining the same non-deleted identities. The null hypothesis is that targeted CDC has no efficiency advantage under equal completion requirements.

**Hypothesis H3.** In a registered temporal topology, RSE can distinguish latent carriers that can regenerate a residual from guarded carriers that cannot, while snapshot-only and blanket-carrier baselines each fail on one side of this distinction. The null hypothesis is that RSE provides no improvement in risk detection or safe-case specificity.

**Hypothesis H4.** Across a finite declared topology envelope, one exact TRE plan can prevent every registered regeneration path at lower declared cost than blanket destruction, while a nominal MSC can fail after topology shift. The null hypothesis is that robust replay offers no safety/cost advantage over the fixed baselines.

**Hypothesis H6.** Within a frozen finite candidate catalogue, adaptive minimax interventions can recover an exact graph or erasure-relevant path class with fewer probes than frozen random or exhaustive testing while failing closed on missing evidence and outside-catalogue behavior. The null hypothesis is that active selection provides no probe or safety advantage under the same catalogue and evidence contract.

The tasks are to formalize residual completion, implement the evaluator and optimizer, machine-check the bounded guarantees, compare against fixed baselines, measure a real-process system, and state the external-validity boundary.

The paper makes seven bounded contributions:

1. A typed residual-path model that keeps physical artifacts, model influence, unknown evidence, and policy blocks semantically distinct.
2. A three-valued completion rule that fails closed, returns the shortest counterexample, and requires successful replay before accepting a correction.
3. A finite minimum-cost CDC formulation with a machine-checked optimality theorem and executable oracle conformance.
4. A layered evaluation covering controlled faults, official external structures, real local services, and a bounded face-unlearning channel, with negative results and independence limits preserved.
5. A temporal RSE layer that computes registered reachable closure, returns a shortest regeneration witness, fails closed on transition-coverage gaps, and selects an exact minimum-cost stabilization cut.
6. A topology-robust TRE layer that selects one minimum-cost plan across a finite declared uncertainty envelope and reports the shortest adversarial witness and robustness premium over nominal MSC.
7. A GhostGraph layer that actively shrinks a finite topology version space, independently checks each minimax choice against a separate oracle, and exposes a blind signed protocol for future external evaluation.

## 2. Related Work and Novelty Boundary

Cao and Yang introduced machine unlearning as a way to remove data and its lineage from learning systems [1]. Bourtoule et al. proposed SISA training to reduce retraining cost by isolating training state [2]. Sommer et al. framed unlearning verification as hypothesis testing [3]. Weng et al. proposed algorithm-level proof of unlearning with authenticated lineage [4], while Eisenhofer et al. studied cryptographically verifiable unlearning [5]. Chourasia and Shah showed that similarity to retraining is not automatically a complete privacy guarantee, especially across releases [6]. Zhang et al. demonstrated that verification mechanisms can be evaded by a dishonest provider [7]. Koloskova et al. developed certified neural-network unlearning under a separate formal guarantee model [8]. W3C PROV provides a standard vocabulary for entities, activities, agents, and derivations [9].

EraSeMap therefore does **not** claim to invent provenance graphs, lineage traversal, machine unlearning, exact retraining, proofs of deletion, signatures, shortest paths, set cover, or minimum cuts. Patent review also found prior claims covering lineage-aware deletion, derived locations, backups, and auditable deletion [10–12].

Robust and probabilistic set covering already optimize coverage under uncertainty [17]. Synthetic test subjects and unique-token deletion checks also appear in prior patent claims [18]. TRE therefore claims neither robust optimization nor deletion canaries; its working contribution is their exclusion-aware composition with temporal subject erasure, fail-closed scenario evidence, exact all-scenario replay, and an adversarial regeneration witness.

The working novelty claim is the tested composition:

> A subject-scoped, fail-closed residual-path contract combines registered physical artifacts, request-scoped model influence, mandatory quantitative verifier channels, replayed actions, and independently recomputed evidence into one three-valued verdict, shortest residual counterexample, and minimum-cost remediation plan.

This is a research hypothesis, not a “first in the world” declaration. A stronger novelty claim requires an independently authored hidden benchmark and a wider professional patent search.

## 3. System and Threat Model

### 3.1 Scope

The audited unit is one erasure request for one subject. The trusted boundary contains a registered topology, artifact-specific local verifiers, a frozen audit policy, and an evaluator that recomputes the result from canonical evidence. The operator may make mistakes, omit actions, or supply incomplete evidence. The model does not guarantee discovery of an unregistered service controlled by the same malicious provider. Topology completeness and verifier soundness are explicit assumptions rather than hidden promises.

### 3.2 Typed operational graph

Let the registered erasure topology be a finite directed graph

**G = (V, E, τ, s),**

where **V** is the set of artifacts, **E** is the set of propagation or derivation edges, **τ(v)** is the artifact type, and **s(v)** is its observed lifecycle state. Types include source record, biometric template, search-index entry, cache entry, backup copy, model influence, and audit receipt. Edges describe copying, derivation, indexing, backup, training use, or supersession.

For a subject **u**, let **Sᵤ ⊆ V** be the subject’s registered origins and let **Tᵤ ⊆ V** be artifacts that can still be used to match, restore, process, or reveal the subject. A path

**π = (v₀, v₁, …, vₖ)**

is an active residual path when **v₀ ∈ Sᵤ**, **vₖ ∈ Tᵤ**, every edge on the path is active under policy, and the terminal artifact has not been proven erased, safely blocked, expired, or unlearned. The residual set is

**Rᵤ(G) = {π | π is an active residual path for u}.**

This definition turns “something may remain” into a concrete counterexample. EraSeMap returns a shortest residual path

**π* = arg min₍π∈Rᵤ(G)₎ |π|,**

with deterministic tie-breaking. The shortest path is not claimed to be the most harmful path; it is the smallest actionable explanation.

### 3.3 Artifact-specific evidence

One generic receipt is insufficient because evidence depends on artifact type. A source row, template, or index entry requires a matching pre-deletion commitment and observed absence. A cache requires invalidation, propagation time, and observed absence. A backup requires expiry under policy or destruction of its encryption key. A model-influence node requires a frozen protocol, an exact-retraining reference, and quantitative utility/privacy checks. A blocked artifact requires an enforced processing control. A receipt requires a valid envelope, nonce, graph-root commitment, and chain.

Let **Cᵤ** be the mandatory verifier channels for request **u**. Each channel returns

**q(c) ∈ {PASS, FAIL, UNKNOWN}.**

UNKNOWN is not converted to success. It represents missing, expired, inaccessible, or not-yet-mature evidence.

### 3.4 Three-valued verdict

The verdict is

**INCOMPLETE**, if **Rᵤ(G) ≠ ∅** or at least one mandatory channel is FAIL;

**COMPLETE**, if **Rᵤ(G) = ∅** and every mandatory channel is PASS;

**UNVERIFIED**, otherwise—there is no established active residual, but at least one mandatory channel is UNKNOWN.

The order is deliberate. A known residual cannot be hidden by missing evidence elsewhere. COMPLETE requires both path closure and positive evidence. This is the fail-closed property.

## 4. Minimum-Cost Counterfactual Deletion Cut

When the verdict is not COMPLETE, the system constructs a finite catalog **A** of candidate actions. An action can delete a record, invalidate a cache, erase a backup key, rebuild an index, retrain or unlearn a model, or enforce a processing block. Each action **a** has a non-negative cost **c(a)** and a permission flag **p(a) ∈ {0,1}**.

For an action subset **B ⊆ A**, let **Apply(G,B)** denote the deterministically simulated post-action graph and evidence. Let **F** be the same frozen three-valued evaluator used for the original request. Feasibility is defined by replay, not by declared action coverage:

**Feasible(B) ⇔ (∀a ∈ B, p(a)=1) ∧ F(Apply(G,B)) = COMPLETE.**

The exact CDC is

**B* ∈ arg min₍B⊆A : Feasible(B)₎ Σₐ∈B c(a).**

Residual-coverage abstractions can help explain candidate actions, but set coverage alone is not accepted as proof: channel dependencies and interactions between actions can make nominal coverage insufficient. The frozen evaluator is therefore the authoritative feasibility predicate.

For at most 30 permitted actions, EraSeMap uses deterministic exact branch-and-bound over replay feasibility. Larger catalogs use a deterministic greedy fallback and are labeled non-optimal. Costs are fixtures unless a measured experiment explicitly calibrates them. A plan remains a counterfactual recommendation until its actions are executed in a disposable or authorized environment, topology and evidence are recollected, and the same audit is replayed. Only an observed replayed COMPLETE is accepted as completed remediation.

## 5. Formal Guarantees

### 5.1 Conditional replay soundness

Let **Rᵣₑₐₗ(u)** be the set of real active residuals and **Rᵣₑg(u)** the registered residuals. Assume:

1. **Topology completeness:** every real active residual is represented by an active registered residual.
2. **Path-closing soundness:** if a registered residual is declared closed, its represented real residual is inactive.
3. **Channel soundness:** PASS on a mandatory verifier implies the corresponding real-world obligation holds.
4. Replayed evaluation returns COMPLETE.

Then **Rᵣₑₐₗ(u) = ∅**, and every mandatory real-world obligation holds.

*Proof sketch.* COMPLETE implies that all registered residuals are closed and every mandatory channel passes. If a real active residual remained, topology completeness would map it to an active registered residual, contradicting closure plus path-closing soundness. Channel soundness transfers every registered PASS to its real obligation. Q.E.D.

This theorem is conditional by design. Without topology completeness, an omitted backup can remain while every registered path is closed. Without channel soundness, a verifier can return PASS while the obligation is false. Lean 4 contains checked counterexamples for both missing assumptions.

### 5.2 Finite CDC optimality

For a finite list of candidate action subsets, a deterministic feasibility predicate, and non-negative costs, the exhaustive selector returns no plan exactly when no listed plan is feasible; otherwise it returns a feasible plan whose cost is no greater than every listed feasible plan.

*Proof sketch.* The selector folds over a finite list while maintaining the cheapest feasible candidate observed so far. The invariant is true initially and preserved at every comparison. At termination, the stored candidate is feasible and no listed feasible candidate has smaller cost. Q.E.D.

Lean 4.33.1 machine-checks these results without `sorry` or `admit`. For MSC, `selected_msc_safe_and_minimum` proves that when replay feasibility soundly implies temporal safety, the selected listed control set is temporally safe and no more expensive than another listed feasible set; the no-plan theorem preserves fail-closed behavior. For TRE, `selected_tre_safe_for_every_scenario_and_minimum` proves safety for every listed scenario and minimum cost among robust-feasible candidates under the corresponding soundness obligation. These theorems cover the abstract core, not Python semantics, driver correctness, real topology discovery, or membership of the real topology in the uncertainty envelope. The production Python selectors are therefore tested separately against exhaustive oracles.

### 5.3 Temporal composition

Let **Q** be a finite state space, **δᵣ** the registered transition relation, **δₜ** the real data-bearing transition relation, and **Residualᵤ(q)** the subject-residual predicate. Assume the post-deletion state **q₀** is residual-free, every real transition is covered by a registered transition, and every registered transition preserves residual absence. Then every state reachable from **q₀** under **δₜ** remains residual-free.

Lean checks this induction over reflexive-transitive reachability. A separate checked counterexample constructs a hidden real transition that regenerates a residual when the coverage premise is removed. The theorem makes transition coverage an explicit deployment obligation rather than claiming it automatically.

## 6. Implementation

EraSeMap is implemented as a reproducible Python package with canonical JSON inputs and outputs. Decoding rejects missing or unknown fields, duplicate nodes or edges, unknown endpoints, and implicit cross-subject edges. Canonical sorting makes graph roots, receipts, and evidence bundles deterministic.

The output proof bundle includes the request and protocol identifiers, registered graph commitment, three-valued verdict, shortest residual path, verifier-channel decisions, selected actions and costs, replay result, evidence hashes, and an Ed25519 receipt chain. The signature covers a minimal envelope and intentionally excludes subject identifiers, biometric values, raw paths, and free text. The evaluator recomputes the verdict and plan from the evidence rather than trusting cached labels.

The repository includes 265 tests with at least 90% measured coverage in the full CI-equivalent test command, a pinned build backend, exact runtime/test constraints, SHA-pinned workflow actions, locked protocols, raw records, manifests, preregistrations, negative-result reports, a Lean project, command-line demonstrations, and CI gates. Engineering verification increases reproducibility but is not counted as independent scientific validation.

## 7. Experimental Methodology

### 7.1 Primary metric

The principal safety metric is the false-complete rate

**FCR = N(false COMPLETE on a non-complete case) / N(non-complete cases).**

Lower is better. A false complete is more dangerous than UNVERIFIED because it can stop remediation while a residual remains. For binomial endpoints, the reports use Wilson 95% intervals. For paired performance ratios, the multi-service experiment uses a deterministic paired bootstrap and reports the geometric mean because ratios are multiplicative.

### 7.2 Layer A: controlled mechanism stress

The project-authored stress set contains 100 cases: 25 genuinely complete and 75 non-complete. In every non-complete case, all subject-scoped physical nodes appear closed, but a mandatory model-evidence, unknown-verifier, or action-replay channel prevents completion. This isolates the mechanism that a node-state audit cannot express. Because the cases and algorithm share project authorship, the layer demonstrates internal mechanism behavior, not external generalization.

### 7.3 Layer B: source-locked external structures

The source-locked benchmark contains 125 unique cases derived from official structures in NIST SP 800-63A, W3C PROV-O, OpenSearch, MLflow, and PostgreSQL. There are 25 cases in each family; 100 are INCOMPLETE or UNVERIFIED and 25 are COMPLETE. Source excerpts, mappings, commitments, labels, raw records, and hashes are stored. The documents are external, but mappings, case construction, labeling, and execution are project-authored.

Comparators are PCUG, a complete typed-node audit, a flat checklist, a model-only check, and a receipt-only check. The preregistered primary gate requires the pooled false-complete Wilson upper bound to be at most 0.05.

### 7.4 Layer C: real-process multi-service experiment

The preregistered paired experiment launches PostgreSQL 15.18, Redis 8.8, and Qdrant 1.15.4; creates AES-GCM encrypted backup files; and trains a ridge model. Each trial contains 250 deterministic synthetic identities. After deleting one source identity from PostgreSQL, two strategies are compared on identical retained state:

- **Targeted CDC:** delete the vector, invalidate the cache, destroy the backup key, and remove exact ridge sufficient statistics.
- **Rebuild-all:** reconstruct every registered component from retained source data.

Five calibration seeds convert measured component time into integer microsecond costs. Twenty holdout seeds are then run once, with strategy order alternating by seed parity. Frozen gates require 20/20 replayed COMPLETE, no retained-identity loss, ridge weights matching rebuild-all within tolerance, and a paired-bootstrap speedup lower bound above 1.25×.

### 7.5 Layer D: bounded model-unlearning channel

The face experiment uses a trainable local embedding encoder over an external face dataset and compares stale, exact retraining, simple approximate baselines, and deletion-matched restart. The forgotten identity is excluded from every candidate optimization step. The adaptive MUFAC v3.2 run uses 120 candidate epochs versus 200 for exact retraining and evaluates 100 deletion requests, producing 500 method-trials on a frozen 572-image, 60-identity subset. Its six paired privacy statistics use confidence, negative entropy, margin, energy, identity-deletion likelihood ratio, and nearest-embedding signals; the protocol uses zero shadow models, so this is a bounded attack panel rather than a full adaptive shadow-model privacy audit.

Frozen gates include retained verification AUC difference of at least −0.01, mean speedup of at least 1.5×, maximum paired privacy-advantage upper confidence bound at most 0.10, and bounded embedding-error ratios. The 120-epoch budget was selected after earlier MUFAC results were known; v3.2 is therefore a method-improvement result, not untouched confirmation. Exact retraining remains the mandatory fallback when any dataset-specific gate fails.

### 7.6 Layer E: preregistered sequential-release privacy

Before the first confirmatory run, the repository froze five seeded deletion orders with five consecutive identity deletions each on Olivetti Faces. At every transition, exact retraining uses 100 epochs and a deletion-matched candidate restarts from the registered seed for 60 epochs using retained identities only. An observer compares two consecutive releases and attacks retained-user membership using absolute changes in confidence, energy, margin, and negative entropy. Candidate-minus-exact advantage is paired across all 25 transitions with deterministic bootstrap 95% intervals.

All six gates were frozen before execution: deleted classes absent; epoch-budget ratio at least 1.5×; retained-accuracy difference at least −0.02 on every transition; retained embedding MSE to exact at most 0.001; forgotten-verification AUC gap at most 0.05; and the largest upper confidence bound for additional privacy advantage at most 0.05. The run refuses a dirty worktree and records the pre-result commit, raw transitions, and artifact hashes.

### 7.7 Layer F: preregistered multi-path temporal erasure

RSE v2 was committed at `110bb63` before implementation of its new adapters or first execution. Thirty risk cases cover AES-GCM backup restore, legacy export import, retry-queue replay, old-checkpoint redeployment, and mixed carriers. Ten safe cases retain all carriers but install a persistent subject tombstone. Ten coverage-fault cases invalidate a required transition attestation.

The snapshot PCUG baseline closes every currently online residual and passes a mandatory absence channel but has no future-transition semantics. The blanket-carrier baseline rejects every latent carrier regardless of guards. Primary gates require 30/30 RSE risk detections, 10/10 safe specificity, 10/10 coverage fail-closed decisions, zero post-MSC physical recurrences, zero exact/oracle mismatches, and selected cost at most 7.

### 7.8 Layer G: preregistered topology-robust erasure

TRE v1 was committed at `320e437` before solver, runner, verifier, or first result implementation. The nominal scenario contains backup restore. Seven shifted scenarios add every non-empty subset of checkpoint redeployment, legacy import, and retry replay; five frozen seeds produce 35 physical cases. The nominal exact MSC, exact all-scenario TRE, and blanket carrier destruction are compared under the same declared costs. Gates require 35/35 nominal-plan recurrences, zero TRE recurrences, zero oracle mismatches, cost 3 for nominal MSC, cost 7 for TRE, blanket cost 60, and a shift-specific witness in every case.

### 7.9 Layer H: open stock-service transfer

Before implementation and the first complete run, v1 froze three immutable container images, five seeds, four fault states, public-input selection, equal-budget comparator rules, exact-control gates, and the core source hash. The services are Keycloak identity lifecycle, MLflow run/artifact lineage, and Qdrant biometric-vector retrieval. The 60-cell matrix contains safe native deletion, a surviving derivative, recovery regeneration, and missing mandatory coverage in every family.

The Qdrant confirmatory split uses five preregistered subjects from public Olivetti Faces, preserving the normalized 64×64 samples as untrained 4,096-dimensional vectors. Keycloak names and MLflow subject commitments are deterministic synthetic inputs. Every HTTP observation is redacted before append-only persistence; a provenance manifest hashes the public asset, all evidence ledgers, trials, and result. An offline verifier reparses the serialized trials, recomputes every gate, and rejects missing, extra, changed, or core-drifted artifacts.

### 7.10 Layer I: active GhostGraph topology discovery

The v2 protocol freezes five graph hypotheses, six allowed experiments, seven hidden cases, an exact trace model, an evidence contract, and six strategies before reveal. At each step, active minimax partitions the version space by predicted trace and minimizes, in order, the largest remaining bucket, squared bucket sizes, declared cost, and experiment ID. A separately implemented bitmask oracle recomputes each choice. The runner stops with an exact graph, erasure-relevant path class, OUT_OF_HYPOTHESIS, or UNVERIFIED; incomplete evidence never becomes confidence.

The live transfer freezes four digest-pinned stock services—Redis, Keycloak, MLflow, and Qdrant—and executes native API observations using isolated synthetic commitments. Five cases cover direct recurrence, multi-hop recurrence, an outside-catalogue graph, a path-equivalent graph, and a safe graph. The external v2 protocol removes pre-disclosed traces: the project receives case IDs and evidence flags, sends one adaptively selected experiment to an evaluator-controlled adapter, and receives only its trace. After reveal, verification recomputes every trace, version space, planner/oracle choice, source hash, commitment, and Ed25519 signature. No external submission is currently claimed.

## 8. Results

### 8.1 Mechanism and transfer

| Evaluation | EraSeMap / PCUG | Strongest comparison | Interpretation |
|---|---:|---:|---|
| Mechanism stress, 75 non-complete cases | 0/75 false complete | Typed node state: 75/75 | Shows value of mandatory channel and replay semantics on project-authored faults |
| Source-locked benchmark, 100 non-complete cases | 0/100; Wilson 95%: 0.0000–0.0370 | Complete typed audit: 0/100 | Passes transfer gate but does not beat the strongest baseline |
| Source-locked complete cases | 25/25 correct complete | Typed audit: 25/25 | No over-conservative failure on complete cases |
| Open stock services, 60 cases | 0 false complete; 15/15 coverage faults fail closed; 0 retained loss/recurrence | Native-success: 45 false complete; typed-node audit: 5 | One frozen contract transfers across three live stock families; mappings and faults remain project-authored |

Flat checklist, model-only, and receipt-only methods each produced 100/100 false completes in the source-locked non-complete cases. This establishes that narrow component checks are insufficient. The tie with the complete typed audit is a scientifically important negative result: external-structure transfer is supported, but superiority of PCUG’s composition is not yet independently established.

### 8.2 Optimization correctness

The production branch-and-bound exact CDC selector was compared with an exhaustive oracle across 512 cost/permission catalogs and all six input orders, including zero-cost, tied-cost, forbidden-action, feasible, and infeasible cases. It matched the oracle in **3,072/3,072** runs with zero mismatches.

### 8.3 Measured multi-service performance

Targeted CDC reached replayed COMPLETE in **20/20** paired trials and preserved all **249** retained identities per trial. Ridge-model weights matched rebuild-all within **2.22 × 10⁻¹⁵**. The geometric-mean wall-clock speedup was **17.64×**, with paired-bootstrap 95% CI **[16.39×, 18.98×]**. Targeted remediation wrote **691,780 bytes**, compared with **12,849,080 bytes** for rebuild-all, a **94.62% reduction**.

These measurements show that minimum-cost targeted remediation can substantially reduce work in the registered local topology without weakening the same replayed completion criterion. They do not estimate cloud latency, block-device write amplification, network traffic, energy, or organizational downtime.

### 8.4 Model channel

MUFAC v3.2 passed all unchanged gates. Retained verification AUC was 0.91912, compared with 0.92565 for exact retraining, a difference of **−0.00653**. Mean speedup was **1.593×**. The maximum paired privacy-advantage upper confidence bound was **0.04091**. Forgotten and retained embedding-MSE ratios to stale were 0.03064 and 0.03348. These numbers support the bounded policy on the exposed subset, not general equivalence to exact retraining or a production privacy guarantee.

### 8.5 Sequential-release privacy

The first confirmatory run at the preregistration commit passed all six gates. Across 25 transitions, every deleted classifier class was absent. The worst retained-accuracy difference was **−0.00952**, retained embedding MSE to exact was at most **0.00000823**, and the forgotten-verification AUC gap was at most **0.00395**. The 60/100 epoch-budget ratio was **1.667×**.

The largest paired privacy upper 95% confidence bound was **0.00624**, below the frozen 0.05 limit. Paired candidate-minus-exact mean advantages and intervals were confidence −0.08370 [−0.11263, −0.05977], energy −0.00144 [−0.00781, 0.00624], margin −0.07687 [−0.10252, −0.05515], and negative entropy −0.08512 [−0.11802, −0.05614]. Absolute membership advantages remained substantial for several attacks. Thus the result bounds additional exposure relative to exact retraining under the registered panel; it does not establish that either release is private.

### 8.6 Regeneration-Safe Erasure

The first prospective v2 run passed every frozen gate. RSE detected **30/30** temporal risk cases, verified **10/10** guarded safe cases, and returned incomplete coverage for **10/10** attestation faults. Snapshot PCUG returned current-state COMPLETE before all **30/30** later physical regenerations. The blanket-carrier baseline rejected all **10/10** safe guarded cases.

Single-carrier cases selected path-specific controls costing 2–5. Mixed cases selected the shared persistent tombstone at cost **7**, compared with four separate filters costing 14 or destroy-all costing 60. Physical replay after MSC caused **0/30** recurrences. Beyond the 30 prospective cases, branch-and-bound MSC matched a separately implemented exhaustive oracle in **16,384/16,384** deterministic configurations: all 16 carrier subsets, all 64 permission masks, eight adversarial cost catalogues, and both input orders.

### 8.7 Topology-Robust Erasure

The first prospective TRE run passed every frozen gate. The backup-only nominal MSC selected a path filter at cost **3**. After each of the 35 frozen topology shifts, at least one added carrier bypassed that filter and physically regenerated subject data: **35/35** recurrences. TRE selected one persistent subject tombstone at cost **7**, returned a shift-specific adversarial witness in **35/35** cases, and produced **0/35** post-control recurrences. Blanket destruction cost 60, so the declared robustness premium over nominal MSC was 4 while the saving relative to blanket action was 53.

Production TRE matched the separately implemented exhaustive oracle in the prospective run and in **4,096/4,096** deterministic configurations spanning eight uncertainty envelopes, all 64 permission masks, four adversarial cost catalogues, and both input orders.

### 8.8 Erasure Tomography

**Hypothesis H5.** Within a frozen candidate catalogue, coded deletion/recovery workflows can
localize one active recurrence mechanism using fewer rounds than individual testing, while
returning UNVERIFIED when catalogue, sparsity, execution, or isolation assumptions fail.

The prospective bounded run recovered **8/8** valid supports with three coded workflows rather than
four individual checks, returned NO_OBSERVED_RECURRENCE in **2/2** safe cases, and returned
UNVERIFIED for **4/4** assumption violations. False localization, production/oracle mismatch,
post-control recurrence, and retained-subject loss were all zero. Production decoding matched a
separately implemented bitmask oracle in **3,584/3,584** configurations.

A separately preregistered live transfer used the digest-pinned Redis image and four
project-authored native recovery workflows. It recovered **4/4** mechanisms and the safe case with
zero false localization, recurrence, or retained loss. Random and greedy three-row coded baselines
also recovered every singleton in this small domain. Therefore the supported novelty is the
fail-closed erasure-specific acquisition-to-PCUG/TRE-repair composition, not a new or superior
general group-testing code.

Boolean network tomography and nonadaptive group testing already localize defective components
from coded Boolean outcomes [19,20], and dependency-aware P2E2 computes meaningful additional
erasure when semantic rules are supplied [21]. The targeted review found no identical end-to-end ET
contract, but this is not a world-priority or patentability claim.

### 8.9 GhostGraph active discovery

The frozen v2 run passed every gate. Active minimax required **7** probes across seven cases, achieved **3** exact graph and **2** path-class recoveries, detected **1/1** outside-catalogue case, returned UNVERIFIED for missing evidence, and recorded zero false confidence, planner/oracle mismatch, post-control recurrence, or retained-subject loss. Frozen random required **13** probes for the same endpoints; nonadaptive exhaustive testing required **49**. Greedy separated-pairs tied active minimax at 7 probes in this small catalogue, so global query optimality is not claimed. Passive declared lineage and flat tomography each produced **1** false-confident output; flat tomography also missed the outside-catalogue case.

The digest-pinned four-service run used **5** probes across five cases, recovered three exact-or-path-class cases, detected the outside-catalogue case, recognized the safe case, and recorded zero false confidence, mismatch, recurrence, retained loss, or cleanup failure. This is stronger transfer evidence than an in-memory simulator but remains a project-operated local test. The external blind protocol is technically complete and adversarially tested, but its evidence status remains **NOT_COLLECTED**.

## 9. Discussion

The main practical result is not merely detection. A useful erasure system must answer three questions in one reproducible chain: What remains? Why is completion blocked? What is the least expensive permitted action set that actually reaches completion? The residual path answers the first two; CDC and replay answer the third.

The three-valued verdict also separates absence of evidence from evidence of absence. A binary system is tempted to treat “not observed” as “gone.” UNVERIFIED preserves uncertainty and keeps the request open. This matters for delayed backup expiry, unreachable services, missing model audits, and asynchronous cache invalidation.

The formal theorem clarifies rather than eliminates operational risk. It shows that COMPLETE is sound **if** the topology represents real residuals and local verifiers are sound. These conditions become deployment obligations that an organization can test, assign, and audit. The theorem does not make invisible infrastructure visible.

RSE adds a time dimension to the same principle. A recoverable carrier is not automatically a current residual, and current absence is not automatically stable. The shortest regeneration witness explains how a normal future operation can reopen the subject; MSC separates safe guarded retention from destructive carrier removal.

TRE addresses a different boundary: a plan optimized for one correct nominal map can be brittle when the map evolves. Optimizing one plan over an explicit scenario envelope makes that uncertainty auditable and quantifies its cost, but does not turn bounded scenarios into knowledge of arbitrary unknown infrastructure.

GhostGraph addresses how to reduce a declared topology uncertainty envelope before repair. Its value is not a promise to discover arbitrary hidden infrastructure; it makes every intervention, version-space reduction, stopping decision, and outside-catalogue failure inspectable. The greedy tie shows that the present catalogue is too small to establish a universal adaptive advantage, while the false-confidence failures show why passive declarations and closed-catalogue localization require explicit fail-closed checks.

The strongest current evidence for added composition value remains internal: the mechanism stress set was designed to exercise mandatory channels and replay. The external-structure benchmark tied the strongest typed audit. Therefore, the next decisive experiment is not another feature or larger project-authored simulator. It is an independently authored hidden challenge containing edge, channel, replay, and hidden-artifact interactions, executed once against a frozen evaluator.

## 10. Threats to Validity and Limitations

**Topology completeness.** EraSeMap cannot prove deletion from an artifact absent from trusted instrumentation. A provider controlling topology, evidence, signer, and evaluator can hide a residual.

**Independence.** Official structures are externally sourced, but mappings and labels are project-authored. No independently authored hidden challenge has been completed.

**Baseline result.** PCUG did not outperform the strongest typed-node audit on the source-locked primary endpoint. Claims of general superiority are unsupported.

**Production transfer.** No Apple Face ID, Kazakhstan eGov, bank, school, border, or government production environment was accessed. Local real-process tests use synthetic identities.

The open-transfer study uses real stock Keycloak, MLflow, and Qdrant processes and public Olivetti
vectors, but not production records or independently authored faults. It therefore strengthens
service-family portability without establishing operational deployment or external independence.

**Model scope.** The adaptive MUFAC result follows exposed earlier runs. The sequential Olivetti result was preregistered and first-run, but uses a shallow classifier over frozen embeddings and four no-shadow-model release-difference attacks. Deep end-to-end models, adaptive shadow-model attacks, reconstruction, longer deletion sequences, population shift, and production threat models remain untested.

**Performance scope.** The 17.64× result is local wall-clock performance on one Apple M4 laptop. The byte count measures application payload and replaced files, not full storage or network I/O.

**Temporal scope.** RSE v2 uses four project-authored carrier families, deterministic synthetic vectors, declared costs, and local adapters. It does not prove observation of unknown future operations or organization-wide transition coverage. Snapshot PCUG and RSE answer different claims; the v2 comparison must not be presented as general PCUG failure.

**Topology-uncertainty scope.** TRE uses eight project-authored scenarios, a three-transition mutation catalogue, and declared costs. The solver sees the complete finite envelope before selection. Zero recurrence inside this envelope is not evidence of safety outside it or of the probability that a real organization satisfies the envelope.

**Active-discovery scope.** GhostGraph uses a finite project-authored catalogue, deterministic traces, and declared experiment costs. The live services are real processes, but their hidden graphs and orchestration are internal. Active minimax tied one greedy baseline and has no global decision-tree optimality theorem. The external blind challenge is protocol-ready but not yet independently authored or executed.

**Novelty search.** The review is structured but not a complete systematic review or legal freedom-to-operate opinion. New publications and patents can narrow the claim.

## 11. Ethics and Responsible Use

Biometric data are sensitive and difficult to replace after compromise. A deletion auditor should minimize additional exposure. EraSeMap receipts exclude biometric values and subject identifiers; experiment records use synthetic identities where possible; face datasets are used only for bounded model evaluation; and production access requires authorization. The tool should not be presented as legal certification. It is an engineering and research mechanism for producing auditable evidence and explicit uncertainty.

A production deployment should separate the topology registrar, evidence producer, and evaluator; use least-privilege service accounts; rotate signing keys; log verifier versions; protect proof bundles; define backup expiry; and obtain institutional approval for human biometric data.

## 12. Reproducibility

The public repository contains code, frozen protocols, raw records, manifests, reports, Lean proofs, and CI configuration. The evidence evaluated in this paper is preserved in the public v0.5.0 history; protocol and raw-record manifests carry cryptographic hashes. Core reproduction commands are:

```bash
python -m pytest
lake build
python scripts/verify_formal_conformance.py --expected formal/conformance-v1.json --output /tmp/formal-conformance.json
python scripts/verify_rse_conformance.py --expected formal/rse-msc-conformance-v1.json --output /tmp/rse-msc-conformance.json
python scripts/verify_topology_robust_erasure_v1.py
python scripts/verify_tre_conformance.py --expected formal/tre-conformance-v1.json
python scripts/verify_measured_multiservice_v1.py
python scripts/verify_sequential_deletion_privacy_v1.py
python scripts/verify_regeneration_safe_erasure_v2.py
python scripts/verify_ghostgraph_v2.py
python scripts/verify_ghostgraph_live_v2.py
python -m external_ghostgraph_challenge.verify_v2
scripts/reproduce_release.sh core
```

The measured service experiment additionally requires pinned PostgreSQL, Redis, Qdrant, and container dependencies. Reproduction verifies the published computation; it does not create independent authorship. No personal biometric data generated by the multi-service experiment are released because that experiment uses deterministic synthetic identities; the external face inputs remain governed by their original dataset terms.

## 13. Conclusion

EraSeMap demonstrates a practical and mathematically explicit way to audit biometric erasure across heterogeneous artifacts, future registered operations, and a bounded set of plausible topology shifts. A deletion request becomes a typed residual-path and temporal-reachability problem, completion becomes a conjunction of path closure, positive mandatory evidence, and stable registered transitions, and correction becomes a minimum-cost action problem whose result must survive replay. TRE further requires one action set to survive every declared topology scenario. The abstract guarantees are machine-checked; the optimizers conform to exhaustive oracles; real local services show substantial savings; and model influence is handled through a bounded quantitative gate with exact fallback.

The evidence supports reproducibility, internal correctness, and feasibility. It does not yet establish independent superiority or production-wide deletion. The strongest next result is an independently authored, frozen hidden challenge followed by an authorized organizational pilot. Preserving this boundary is not a weakness of the project; it is what makes its current claim scientifically defensible.

## References

[1] Y. Cao and J. Yang, “Towards Making Systems Forget with Machine Unlearning,” 2015 IEEE Symposium on Security and Privacy, pp. 463–480, 2015. DOI: 10.1109/SP.2015.35.

[2] L. Bourtoule et al., “Machine Unlearning,” 2021 IEEE Symposium on Security and Privacy, 2021. arXiv:1912.03817.

[3] D. M. Sommer, L. Song, S. Wagh, and P. Mittal, “Towards Probabilistic Verification of Machine Unlearning,” arXiv:2003.04247, 2020.

[4] J. Weng, S. Yao, Y. Du, J. Huang, J. Weng, and C. Wang, “Proof of Unlearning: Definitions and Instantiation,” arXiv:2210.11334, 2022.

[5] T. Eisenhofer, D. Riepel, V. Chandrasekaran, E. Ghosh, O. Ohrimenko, and N. Papernot, “Verifiable and Provably Secure Machine Unlearning,” IEEE Conference on Secure and Trustworthy Machine Learning (SaTML), 2025; arXiv:2210.09126v3.

[6] R. Chourasia and N. Shah, “Forget Unlearning: Towards True Data-Deletion in Machine Learning,” Proceedings of the 40th International Conference on Machine Learning, PMLR 202:6028–6073, 2023.

[7] B. Zhang, Z. Chen, C. Shen, and J. Li, “Verification of Machine Unlearning is Fragile,” Proceedings of the 41st International Conference on Machine Learning, PMLR 235:58717–58738, 2024.

[8] A. Koloskova, Y. Allouah, A. Jha, R. Guerraoui, and S. Koyejo, “Certified Unlearning for Neural Networks,” Proceedings of the 42nd International Conference on Machine Learning, PMLR 267:31275–31298, 2025.

[9] T. Lebo, S. Sahoo, and D. McGuinness, editors, “PROV-O: The PROV Ontology,” W3C Recommendation, 30 April 2013.

[10] U.S. Patent Application US20220414070A1, “Tracking Data Lineage and Applying Data Removal to Enforce Data Removal Policies,” 2022.

[11] U.S. Patent US11120156B2, “Privacy Preserving Data Deletion,” 2021.

[12] U.S. Patent US12456052B2, “Systems and Methods for Facilitating Verifiability of Machine Learning Model Unlearning,” 2025.

[13] D. Temoshok et al., “Digital Identity Guidelines: Identity Proofing and Enrollment,” NIST SP 800-63A-4, July 2025. DOI: 10.6028/NIST.SP.800-63a-4.

[14] EraSeMap, public repository and evidence archive, version 0.5.0, 2026: https://github.com/nazkari86-lab/erasemap.

[15] European Data Protection Board, “EDPB identifies challenges hindering the full implementation of the right to erasure,” 18 February 2026.

[16] UK Patent Application GB2562767A, “Right to erasure compliant back-up,” 2018.

[17] D. Degel and P. Lutter, “A Robust Formulation of the Uncertain Set Covering Problem,” Optimization Online, 2013.

[18] U.S. Patent Application US20210406398A1, “Data Processing Systems for Data Testing to Confirm Data Deletion and Related Methods,” 2021.

[19] N. Galesi and F. Ranjbar, “Counting and Localizing Defective Nodes by Boolean Network Tomography,” arXiv:2101.04403, 2021.

[20] A. D'yachkov, A. Macula, and V. Rykov, “Error-Correcting Nonadaptive Group Testing with Disjunct Matrices,” Discrete Applied Mathematics 80:217–222, 1997. DOI: 10.1016/S0166-218X(97)80002-9.

[21] V. Chakraborty et al., “Meaningful Data Erasure in the Presence of Dependencies,” Proceedings of the VLDB Endowment 18(10):3435–3448, 2025. DOI: 10.14778/3748191.3748206.

## Appendix A. Notation

| Symbol | Meaning |
|---|---|
| G = (V,E,τ,s) | Registered typed erasure graph |
| u | Subject of one erasure request |
| Rᵤ(G) | Active residual paths for subject u |
| Cᵤ | Mandatory verifier channels |
| q(c) | PASS, FAIL, or UNKNOWN result for channel c |
| A | Finite catalog of candidate remediation actions |
| c(a) | Non-negative action cost |
| B | Selected action subset, B ⊆ A |
| Apply(G,B) | Deterministic post-action graph and evidence |
| F | Frozen three-valued evaluator |
| Feasible(B) | All selected actions are permitted and replay returns COMPLETE |
| FCR | False-complete rate |
| Reach(q₀,δ) | States reachable after deletion under registered transitions |
| MSC | Minimum-cost Stabilization Cut blocking every registered regeneration witness |
| TRE | Topology-Robust Erasure: one exact plan for every topology in a declared uncertainty envelope |
| ET | Erasure Tomography: bounded coded deletion probes for recurrence-mechanism localization |
| GhostGraph | Active finite version-space discovery of deletion-regeneration topology |

## Appendix B. Claim–Evidence Map

| Claim | Evidence | Boundary |
|---|---|---|
| Replayed COMPLETE is conditionally sound | Lean theorem with explicit assumptions | Does not prove topology discovery or driver correctness |
| Exact CDC is minimum-cost over listed candidates | Lean finite optimality theorem | Only for the registered finite candidate set |
| Exact MSC is safe and minimum-cost under registered temporal semantics | Lean conditional theorem; 16,384/16,384 Python/oracle configurations | Depends on transition coverage and feasibility soundness |
| Exact TRE is safe and minimum-cost across a declared envelope | Lean conditional theorem; 4,096/4,096 Python/oracle configurations | Depends on all-scenario feasibility soundness and envelope membership |
| Python exact CDC implements the finite contract | 3,072/3,072 oracle matches | Bounded systematic conformance, not Python formal semantics |
| Mandatory channels prevent a typed-node blind spot | 0/75 versus 75/75 mechanism stress | Project-authored development evidence |
| PCUG transfers to official external structures | 0/100 false complete; 25/25 complete | Strongest typed baseline tied; mappings are internal |
| Targeted remediation can be cheaper than rebuild-all | 17.64× speedup; 94.62% fewer bytes; 20/20 complete | One local machine and synthetic identities |
| Adaptive face candidate meets frozen bounded gates | −0.00653 AUC difference; 1.593×; privacy upper CI 0.04091 | Post-exposure adaptive result; exact fallback remains required |
| Sequential deletion candidate meets six frozen gates | 25 transitions; worst retained accuracy −0.00952; privacy upper CI 0.00624 | First-run preregistered, but project-authored and no-shadow-model |
| RSE distinguishes future risk from guarded latent carriers | 30/30 risks; 10/10 safe; 10/10 coverage faults; 0/30 post-MSC recurrences | Prospective but project-authored local multi-path lab |
| TRE survives the frozen topology shifts | Nominal 35/35 recurrences; TRE 0/35; cost 7 versus blanket 60 | Prospective but finite, visible, project-authored envelope |
| ET localizes bounded recurrence mechanisms | 8/8 supports; 4/4 negative fail-closed; 3,584/3,584 oracle; Redis 4/4 | `k=1`, `e=0`, project-authored catalogue/workflows; no arbitrary discovery |
| GhostGraph actively reduces topology uncertainty | 7 probes; 3 exact + 2 path-class; OUT and UNVERIFIED detected; live 5/5 cases with zero false confidence | Finite project-authored catalogue; greedy tied; external blind run is `NOT_COLLECTED` |
