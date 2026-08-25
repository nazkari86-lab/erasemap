# Qwen–TOFU v2 Kaggle runner

This private offline GPU kernel runs the frozen adaptive v2 protocol. It reuses the pinned wheels
and TOFU snapshot from the v1 assets dataset and attaches a separately versioned source snapshot
whose revision marker must match a clean Git commit.

```bash
scripts/kaggle_qwen_tofu_v2.sh submit
scripts/kaggle_qwen_tofu_v2.sh status
scripts/kaggle_qwen_tofu_v2.sh collect
```

`submit` refuses a dirty worktree, publishes the exact committed source as a private Kaggle dataset,
waits for Kaggle to report that source as ready, and only then submits the GPU kernel. `collect`
refuses to overwrite an existing result and runs the offline verifier after downloading every
paginated output file.
