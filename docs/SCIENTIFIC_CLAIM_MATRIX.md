# EraSeMap scientific claim matrix

Snapshot: 2026-08-30. EraSeMap is one public algorithm with FIND, ERASE, and PROVE stages. The table
separates formal, measured, prospective, failed, and pending evidence.

| Claim | Scope and assumptions | Strongest evidence | Status |
|---|---|---|---|
| Unified EraSeMap certifies only after FIND evidence, the physical/model ERASE plan, and temporal PROVE replay pass | Registered graph/actions, valid bounded discovery evidence, sound local verifiers and registered transitions | `run_erasemap` fail-closed tests | Implemented conditional composition; not open-world completeness |
| Replayed completion excludes represented residual paths | Registered topology complete; local verifiers sound; mandatory channels included | Lean `replayed_complete_sound` plus checked boundary counterexamples | Conditional theorem |
| ERASE selects a minimum-cost registered action plan | Finite permitted catalogue, integer costs, sound feasibility replay | Lean exact-selector theorem; 3,072/3,072 Python/oracle ordering matches | Conditional theorem plus bounded conformance |
| PROVE lifts snapshot absence to registered temporal safety | Every real transition covered; registered transitions preserve absence | Lean temporal composition theorem and missing-coverage counterexample | Conditional theorem |
| PROVE selects a safe minimum-cost temporal control set | Finite registered controls; replay feasibility implies temporal safety | Lean exact temporal selector; 16,384/16,384 Python/oracle matches | Conditional theorem plus bounded conformance |
| FIND identifies a bounded recovery graph or full observable path class | Closed six-graph catalogue, sound complete isolated traces, truth listed except OUT | Frozen v2: 3 exact, 2 path-class, OUT and UNVERIFIED; 0 false confidence; 7 vs 13 vs 49 probes; Lean filtering/minimax contracts | Prospective project-authored bounded result |
| FIND transfers to live stock services | Digest-pinned Redis, Keycloak, MLflow, Qdrant; isolated synthetic commitments | 5 cases, 5 probes, exact/path, OUT and safe cases detected; zero false confidence/recurrence/retained loss | Project-authored live stock-service transfer |
| Targeted ERASE is cheaper than rebuild-all | Synthetic identities, pinned local PostgreSQL/Redis/Qdrant, declared byte accounting | 20 paired trials; 17.64× geometric-mean speedup; 94.62% fewer written bytes; no retained loss | Preregistered local real-process result |
| One contract transfers across identity, ML-lineage, and biometric-vector services | Digest-pinned stock services, project-authored mappings/faults, public Olivetti vectors plus synthetic inputs | 60 cases: 0 EraSeMap false completes, native 45, typed audit 5; 15/15 coverage faults fail-closed | Preregistered project-authored transfer |
| PROVE distinguishes latent risk from guarded retention | Four project-authored carrier families and registered transitions | 30/30 risks, 10/10 safe, 10/10 coverage faults, 0/30 post-control recurrence | Prospective project-authored result |
| Fast Qwen unlearning matches exact retraining while preserving utility | Pinned Qwen2.5-1.5B, TOFU subset, frozen conjunctive gates | V1 and V2 both failed at least one mandatory gate; speed and zero reload recurrence did not override failures | **Falsified for current candidates; exact retraining remains fallback** |
| Sequential face-unlearning candidate stays inside the frozen retained-user privacy bound | Olivetti task, four no-shadow attacks, 25 transitions, fixed budget | Six-gate first-run PASS; maximum added-advantage upper bound 0.00624 | Bounded project-authored result; not certified privacy |
| EraSeMap generalizes to independently authored hidden topologies | External author controls hidden graphs/traces; sealed truth; frozen clean source and signature checks | Executable blind kit and tamper tests only | **Pending external execution: NOT_COLLECTED** |
| EraSeMap works in production FaceID/eGov/government infrastructure | Authorized instrumentation covers actual stores, transitions, and model channels | Pilot protocol and adapters only | **Not established** |

## Interpretation rules

1. A formal theorem is always reported with its assumptions.
2. Bounded exhaustive checks do not establish open-world behavior.
3. Project-authored prospective evidence is not independent replication.
4. Failed model experiments remain published and cannot be rewritten as success.
5. Engineering checks do not promote a result into a stronger evidence class.
