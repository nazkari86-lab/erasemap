# EraSeMap competition evidence scorecard

Snapshot: 2026-08-23. This is a fixed evidence map, not an official RKNP or ISEF score and not a
probability of winning. A number may move only after the named evidence event occurs.

## Thirty-second explanation

Deleting the main biometric row does not guarantee deletion: a template, vector index, cache,
backup, model influence, or stale service can still use the person. EraSeMap registers these
derivatives in one typed graph and returns one of three verdicts:

- `COMPLETE`: every represented residual path is closed and every mandatory verifier passed;
- `INCOMPLETE`: a usable residual remains, with the shortest counterexample path;
- `UNVERIFIED`: the available evidence is insufficient, stale, or inconsistent.

It then computes the minimum-cost permitted set of actions needed to reach verified completion.

## Evidence-anchored assessment

| Dimension | Current | Observable evidence | Next score-changing event |
|---|---:|---|---|
| Problem clarity | 9.6/10 | Seven-step showcase plus 12 aligned EN/RU one-minute cards; human result remains `NOT_COLLECTED` | At least 10 unfamiliar participants pass the frozen answer-blind endpoints |
| Practical relevance | 9.7/10 | Frozen failures and remediation now execute on stock identity, ML-lineage, and biometric-vector services | Authorized organization pilot on actual deletion workflow |
| Narrow scientific novelty | 9.7/10 | One frozen fail-closed PCUG/CDC contract transfers across Keycloak, MLflow, and Qdrant while preserving explicit prior-art exclusions | Untouched external topology shifts outperform frozen strong baselines |
| Experimental methodology | 9.9/10 | Frozen one-shot 60-case stock-service run, raw process evidence, oracle controls, prior prospective studies, and finite conformance audits | Independently authored preregistered holdout |
| Scientific claim completion | 9.8/10 | Formal PCUG/RSE/TRE results plus measured optimization and frozen three-family transfer PASS | External hidden challenge plus materially different system replication |
| Real inputs and transfer | 9.4/10 | Public Olivetti vectors and real stock Keycloak/MLflow/Qdrant processes; identities/commitments and faults remain project-authored | Authorized real records or redacted production instrumentation |
| Independence of evidence | 7.8/10 | Executable signed challenge exists, but `external_results/` has no accepted external result | One verified evaluator passes all 9.5 rubric gates |
| Formal justification | 9.8/10 | Lean PCUG/RSE/TRE soundness and exact CDC/MSC/TRE results; axiom audit; 3,072 CDC, 16,384 MSC, and 4,096 TRE production/oracle runs | Independent proof review or machine-checked implementation refinement |
| Engineering | 9.9/10 | Strict typing, digest-pinned stock lifecycle, redacted ledgers, offline tamper checks, signed external handoff, and fail-safe teardown | Reproducible external deployment or release audit |
| Reproducibility | 9.9/10 | Committed protocol, first-run trials, 9.6 MiB raw evidence, public asset provenance, and standalone offline recomputation | Independent clean-machine reproduction |
| FaceID/eGov/KYC applicability | 9.5/10 | One contract now runs on stock identity and biometric-vector services, not only display adapters | Authorized domain-specific instrumentation and evaluation |
| Competition presentation readiness | 9.8/10 | Evidence-bound seven-step showcase, Russian defense/Q&A, and answer-blind bilingual handoff | Timed rehearsal with an unfamiliar reviewer |
| RKNP competitiveness | 9.8/10 | Formal result plus measured multi-service result satisfy the frozen 9.8 trigger | External PASS or organization confirmation for a defensible 9.9 |
| ISEF-level readiness | 9.6/10 | Formal contribution, first frozen cross-family stock-service result, raw reproducibility, and explicit limitations | External PASS raises evidence readiness toward 9.7–9.8 |

The independence row is deliberately not averaged away. More project-authored code cannot move it
above 7.8.

## Strongest results, without scope inflation

1. **Mechanism:** on 75 project-authored non-complete interaction cases, PCUG made 0 false-complete
   decisions while node-only typed audit made 75. This explains why channels and replay matter; it
   is not external superiority evidence.
2. **Formal:** Lean checks conditional replay soundness and finite CDC optimality. Production
   `exact_cdc` matched exhaustive selection in 3,072/3,072 preregistered runs.
3. **Measured systems:** across 20 paired local holdout seeds using real PostgreSQL, Redis, Qdrant,
   encrypted backups, and a ridge model, exact CDC maintained 100% completion and retained data,
   achieved 17.64x geometric-mean speedup with 95% CI [16.39x, 18.98x], and wrote 94.62% fewer
   declared application/filesystem bytes than rebuild-all.
4. **Model layer:** adaptive MUFAC v3.2 passed the unchanged bounded utility/privacy gates at 1.59x
   speedup, but it is a post-exposure improvement rather than fresh confirmation.
5. **Sequential privacy:** a first-run preregistered Olivetti study passed six frozen gates across
   25 release transitions; the largest paired upper 95% CI for additional membership advantage was
   0.00624 against the 0.05 limit. The attacks use no shadow models and are not a privacy guarantee.
6. **External boundary:** the independent score remains 7.8 until an identifiable evaluator authors,
   freezes, reveals, signs, and submits the challenge.
7. **Temporal deletion:** the RSE v2 protocol was public before implementation and first execution.
   RSE detected 30/30 multi-path risks, verified 10/10 guarded safe cases, failed closed on 10/10
   coverage faults, matched its exhaustive oracle, and produced 0/30 physical recurrences after
   exact MSC. Snapshot PCUG missed future replay in 30/30 risk cases, while blanket carrier audit
   rejected 10/10 safe cases. This strengthens the prospective mechanism result without changing
   the 7.8 independence score.
8. **MSC conformance:** production branch-and-bound matched a separate exhaustive subset oracle in
   16,384/16,384 configurations spanning every carrier subset and permission mask, eight cost
   catalogues, and both input orders. This closes a bounded implementation gap; it is not a new
   external experiment.
9. **Topology robustness:** the TRE protocol was committed before implementation and first run.
   Nominal exact MSC regenerated data in 35/35 frozen topology shifts; one exact all-scenario TRE
   plan regenerated data in 0/35, matched its exhaustive oracle, cost 7 versus blanket destruction
   at 60, and returned a shift-specific witness in every case. A separate 4,096-configuration
   conformance audit had zero mismatches. The envelope and execution remain project-authored, so
   independence stays 7.8.
10. **Open stock-service transfer:** a frozen 60-case first run on digest-pinned Keycloak, MLflow,
    and Qdrant passed every conjunctive gate: 0 EraSeMap false completes, 15/15 coverage faults
    failed closed, 0 retained loss, 0 post-control recurrence, and 60/60 exact/oracle matches.
    Native-success made 45 false-complete decisions and typed-node audit made 5. Public Olivetti
    vectors improve input realism, but mappings, faults, and execution are project-authored; the
    independence score therefore remains 7.8.

## Reproduce the jury artifact

```bash
erasemap showcase --repo-root . --output outputs/jury-showcase-v1
open outputs/jury-showcase-v1/index.html
```

The command recomputes the live audit, validates frozen result invariants, includes SHA-256 hashes
of every source artifact, and fails closed if a headline result is changed.
