# MUFAC Safe Policy v2

Date: 2026-08-22

Decision: **SAFE_FALLBACK to exact retraining**

The original content-unseen MUFAC result remains a failure for `deletion_matched_restart` because
the conservative retained-verification AUC loss was 0.017108, above the frozen 0.01 limit. Privacy
and forgotten-distance gates passed, but the utility gate did not.

The v2 policy therefore selected exact retraining. On the already frozen external evidence this
gives retained verification AUC 0.925649, retained CKA 1.0 relative to exact retraining, and speedup
1.0x. The policy prevents an approximate model with failed utility evidence from receiving a PCUG
`COMPLETE` model-channel verdict.

This is a post-hoc fail-safe policy over immutable v3 evidence, not a new model experiment and not a
claim that the fast candidate improved. The scientific negative result remains visible; the
engineering improvement is a safe decision rule with an exact-retrain fallback.

