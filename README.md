# Bus function configuration

Synthetic-data application following the [detailed design](docs/Bus_Config_AI_Detailed_Design_EN_v3.md)
and [implementation plan](docs/Bus_Config_AI_Implementation_Plan_EN_v1.md).
T01.1 establishes the Python package and local environment diagnostic. T01.2 adds
typed selection inputs, duplicate-function rejection and explicit fact value
states. Parsing, planning, persistence and model execution are subsequent tasks.

## Local setup

Use Python 3.12 and uv (verified versions and hardware are in
[environment.md](docs/environment.md)). From the repository root:

```sh
uv sync --locked
uv run python -c 'import busconfig'
uv run busconfig doctor
```

The distribution retains the repository name `ai-func-config`; the import package
is `busconfig` and the console command is `busconfig`. `uv.lock` pins resolved
dependencies. No database, Docker, GPU, model endpoint or credentials are needed
for the disabled baseline.

`doctor` prints JSON with Python/application/library versions, environment, model
mode, and the data directory's write check. It creates the configured data directory
if absent, writes and removes a temporary probe, and does not contact external
services. Exit codes: `0` local checks succeeded, `2` invalid settings/arguments,
`3` data-directory operation failed. Success does not establish model or database
connectivity, or validate a bus configuration.

## Settings

[.env.example](.env.example) documents the process-environment variables. The
application does not automatically load or execute `.env` files. For example:

```sh
BUSCONFIG_DATA_DIR=./runtime/local-data BUSCONFIG_MODEL_MODE=disabled uv run busconfig doctor
```

Supported diagnostic mode names are `disabled` (default), `fake`, and `http`.
Only `http` requires a non-placeholder model name and an HTTP(S) base URL. These
are settings checks; fake and HTTP clients arrive in T10. Timeouts, concurrency,
preparation limits and search budgets must be positive and finite; optional retry,
repair and follow-up counts may be zero. Credentials and endpoint values are
omitted from reports, and credential values embedded in diagnostic paths are
redacted. Invalid settings report field names without input values.

Keep actual credentials in an untracked environment or secret store. Only invented
engineering inputs may be used in this independent project.

## Verification

```sh
uv run pytest tests/unit/test_selection_contracts.py tests/unit/test_settings.py -q
uv run pytest tests/unit -q
uv run pytest -q
uv run ruff check .
```

Integration tests will run when their owning task creates them. See
[progress.md](docs/progress.md) for exact commands, observed results, scope
decisions, remaining limitations and the next subtask.
