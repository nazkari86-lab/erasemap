# EraSeMap Qwen–TOFU Kaggle v1

This private Kaggle GPU kernel clones the frozen EraSeMap commit
`e0cf331fb0bae95f8ac434297105f407d8f59428`, installs pinned training dependencies, and executes the
preregistered three-seed Qwen2.5-1.5B TOFU experiment. Model and dataset caches remain in `/tmp`;
only adapters and evidence artifacts are published as kernel output.

```bash
scripts/kaggle_qwen_tofu_v1.sh submit
scripts/kaggle_qwen_tofu_v1.sh status
scripts/kaggle_qwen_tofu_v1.sh collect
```

The helper supports either `~/.kaggle/access_token` (Bearer token) or legacy
`~/.kaggle/kaggle.json`. A username must be supplied through `KAGGLE_USERNAME` or the `username`
field in `kaggle.json`. It refuses to overwrite a previously collected result. Collection invokes
the offline EraSeMap verifier before accepting the output.
