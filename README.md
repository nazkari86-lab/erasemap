# EraseMap

EraseMap is a research prototype for auditing registered biometric-data lineage. It finds
residual paths from a subject to active processing sinks and refuses to call missing evidence
successful erasure.

EraseMap only covers artifacts recorded by trusted instrumentation. It does not prove that no
unknown copy exists, provide legal advice, or claim validation on eGov or another production
identity system.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src/erasemap
```

The `erasemap` CLI will be documented when its commands are implemented.
