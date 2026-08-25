# EraSeMap Qwen–TOFU Kaggle v1

This private Kaggle GPU kernel extracts EraSeMap commit
`50305b8931ef915a6de3242d5220e1b2b25d9841` from a frozen private Kaggle Dataset, installs pinned
wheels without network access, attaches the official Qwen2.5-1.5B Kaggle Model, and executes the
preregistered three-seed TOFU experiment. The newer source revision only adds offline input-path
support after two pre-execution Kaggle DNS failures; the frozen protocol, seeds, methods, metrics,
and success thresholds are unchanged. Only adapters and evidence artifacts become kernel output.

```bash
scripts/kaggle_qwen_tofu_v1.sh submit
scripts/kaggle_qwen_tofu_v1.sh status
scripts/kaggle_qwen_tofu_v1.sh collect
```

The helper supports either `~/.kaggle/access_token` (Bearer token) or legacy
`~/.kaggle/kaggle.json`. A username must be supplied through `KAGGLE_USERNAME` or the `username`
field in `kaggle.json`. It refuses to overwrite a previously collected result. Collection invokes
the offline EraSeMap verifier before accepting the output.
