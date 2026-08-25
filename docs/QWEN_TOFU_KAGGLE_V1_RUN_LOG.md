# Qwen–TOFU Kaggle v1 run log

Date: 2026-08-25  
Kernel: `hijima/erasemap-qwen-tofu-v1`  
Scientific result: `FAIL` (valid first GPU result; retained unchanged)

The preregistered methods, seeds, metrics, and nine success thresholds were not changed during
these attempts. Every failure occurred before the first training step, so none is a scientific
trial or evidence about unlearning quality.

| Kernel version | Outcome | Pre-training cause | Resolution |
| --- | --- | --- | --- |
| 1 | `ERROR` | Kaggle worker could not resolve `github.com` | Retried unchanged |
| 2 | `ERROR` | Same external DNS failure | Built a network-independent asset bundle |
| 3 | `ERROR` | Kaggle automatically extracted uploaded archives | Switched to mounted directories |
| 4 | `ERROR` | Wheel archive had an additional extracted directory level | Corrected the wheel mount path |
| 5 | `ERROR` | Editable install attempted networked build isolation | Executed frozen source via `PYTHONPATH` |
| 6 | `ERROR` | Kaggle `tokenizers 0.22.2` conflicted with Transformers 4.48.3 | Added compatible frozen transitive wheels |
| 7 | `ERROR` | `torch.cuda.is_available()` was false although kernel metadata requested GPU | Requires Kaggle account GPU access or quota |
| 8 | `COMPLETE` | Valid three-seed Tesla P100 execution | Collected and independently recomputed offline; frozen decision `FAIL` |

Version 7 successfully reached the experiment's fail-closed CUDA gate. Version 8 then ran the full
three-seed protocol on a Tesla P100. The original verifier reported seven of nine gates passed. A
later semantic audit found that the perturbed-answer channel reused the ordinary answer, so the
post-audit accounting is six valid passes, two failures, and one unevaluable gate. The candidate missed the
all-seed forgetting minimum (`0.04837 < 0.05`) and exceeded the world-fact degradation maximum
(`0.45300 > 0.20`), so the conjunctive decision is `FAIL`. Exact adapter retraining passed its
forgetting gate, and reload recurrence was zero. See
[`QWEN_TOFU_KAGGLE_V1_REPORT.md`](QWEN_TOFU_KAGGLE_V1_REPORT.md).

The private assets dataset is `hijima/erasemap-qwen-tofu-v1-assets`. It contains source revision
`50305b8931ef915a6de3242d5220e1b2b25d9841`, TOFU revision
`324592d84ae4f482ac7249b9285c2ecdb53e3a68`, and the offline wheels. Qwen weights come from the
official Kaggle Model source `qwen-lm/qwen2.5/transformers/1.5b/1`.
