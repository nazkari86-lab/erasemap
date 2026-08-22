# PCUG holdout readiness gate

Status: **NOT READY / NOT COMMITTED**

The development protocol intentionally contains `"holdout":{"committed":false,"seeds":[]}` and
the implementation refuses holdout execution. A holdout may be created only after every item below
is satisfied and reviewed.

- [ ] Development failures and `UNKNOWN` cases have been reviewed without changing their labels.
- [ ] Primary endpoint, unit of analysis, effect direction, margins, denominators, and interval
  method are frozen.
- [ ] Hidden topology families come from a source independent of the current generator where
  licensing permits redistribution or controlled evaluation.
- [ ] Hidden verifier challenges are committed before candidate results are inspected.
- [ ] Dataset/identity ownership and split provenance are independently checked.
- [ ] All required baselines and ablations are named before the holdout is opened.
- [ ] Exclusion, exception, timeout, and missing-evidence rules are frozen and fail-closed.
- [ ] The exact code revision, environment manifest, protocol, action catalogue, and cost semantics
  are committed from a clean tree.
- [ ] A one-shot execution rule and result-retention location are fixed.
- [ ] It is agreed that a revealed holdout cannot be relabelled development or silently replaced.
- [ ] An external evaluator can run the independent bundle checker with a separately supplied public
  key.
- [ ] Claim language is prewritten for pass, fail, and inconclusive outcomes.

Completing this checklist authorizes protocol creation, not a production claim. Production FaceID,
eGov, bank, school, or government evaluation still requires written authorization, instrumentation,
representative populations, and operational threat modelling.

