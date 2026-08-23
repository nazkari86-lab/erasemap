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
| Problem clarity | 9.5/10 | `examples/five_branch_system.json` gives a two-node counterexample: `source -> template` | Usability test with judges or operators who can explain the result unaided |
| Practical relevance | 9.6/10 | Contracts cover source, template, cache, vector store, backup, and model influence | Authorized organization pilot on actual deletion workflow |
| Narrow scientific novelty | 9.6/10 | Fail-closed PCUG/CDC, temporal RSE/MSC, and topology-robust TRE with explicit prior-art exclusions | Untouched external topology shifts outperform frozen strong baselines |
| Experimental methodology | 9.8/10 | Frozen protocols, one-shot holdouts, paired bootstrap, retained negative MUFAC result, three prospective first-run studies, and 4,096-case TRE plus 16,384-case MSC conformance | Independently authored preregistered holdout |
| Scientific claim completion | 9.7/10 | Conditional PCUG/RSE/TRE soundness and exact CDC/MSC/TRE optimality in Lean; measured systems, sequential-release, temporal, and topology-shift results | External hidden challenge plus materially different system replication |
| Real inputs and transfer | 9.0/10 | Open face datasets, official source structures, real PostgreSQL/Redis/Qdrant processes | Authorized real records or redacted production instrumentation |
| Independence of evidence | 7.8/10 | Executable signed challenge exists, but `external_results/` has no accepted external result | One verified evaluator passes all 9.5 rubric gates |
| Formal justification | 9.8/10 | Lean PCUG/RSE/TRE soundness and exact CDC/MSC/TRE results; axiom audit; 3,072 CDC, 16,384 MSC, and 4,096 TRE production/oracle runs | Independent proof review or machine-checked implementation refinement |
| Engineering | 9.8/10 | Strict typing, tests, coverage, SHA-pinned CI actions, pinned build backend, exact runtime/test constraints, signed evidence and drift checks | Reproducible external deployment or release audit |
| Reproducibility | 9.8/10 | CI-equivalent clean-worktree release gate, committed protocols, raw hashes, deterministic showcase | Independent clean-machine reproduction |
| FaceID/eGov/KYC applicability | 9.4/10 | System-neutral typed contract and display adapters | Authorized domain-specific instrumentation and evaluation |
| Competition presentation readiness | 9.7/10 | Jury showcase, Russian defense script, Q&A, evidence-led slide deck | Timed rehearsal with an unfamiliar reviewer |
| RKNP competitiveness | 9.8/10 | Formal result plus measured multi-service result satisfy the frozen 9.8 trigger | External PASS or organization confirmation for a defensible 9.9 |
| ISEF-level readiness | 9.5/10 | Strong contribution, honest limitations, reproducible artifacts, formal and measured results | External PASS raises evidence readiness toward 9.7–9.8 |

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

## Reproduce the jury artifact

```bash
erasemap showcase --repo-root . --output outputs/jury-showcase-v1
open outputs/jury-showcase-v1/index.html
```

The command recomputes the live audit, validates frozen result invariants, includes SHA-256 hashes
of every source artifact, and fails closed if a headline result is changed.
