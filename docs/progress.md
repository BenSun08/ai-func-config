# Implementation progress

Design: Bus_Config_AI_Detailed_Design_EN_v3.md
Plan: Bus_Config_AI_Implementation_Plan_EN_v1.md
Current milestone: M0
Current subtask: T01.1
Status: verified
Verified date: 2026-11-17 (Asia/Shanghai)

## Last verified unit

- Subtask: T01.1 — reproducible shell, `busconfig` package and local doctor.
- Commit: the local commit containing this record, titled
  `feat: establish T01.1 package and local doctor`; resolve its ID with
  `git log -1 --format=%H -- docs/progress.md`.
- Branch: `codex/t01-1-package-doctor`, based on `107c8c9`.
- Changed files: `.env.example`, `.gitignore`, `.python-version`, `pyproject.toml`,
  `uv.lock`, `README.md`, `src/busconfig/{__init__,cli,settings}.py`,
  `tests/unit/test_settings.py`, `docs/{environment,decisions,progress}.md`.
- Existing task-required files adopted unchanged into version control:
  `AGENTS.md`, `docs/Bus_Config_AI_Detailed_Design_EN_v3.md`, and
  `docs/Bus_Config_AI_Implementation_Plan_EN_v1.md`.
- Artifacts: `docs/environment.md`; locked environment; package sources/tests;
  source distribution and wheel in `/tmp/busconfig-t011-dist/` (temporary,
  rebuildable, not committed); ignored `runtime/data/` created by doctor.

## Verification evidence

For sandbox commands below, the actual prefix was
`UV_CACHE_DIR=/tmp/busconfig-uv-cache` unless explicitly stated otherwise.
Tests use invented values and local temporary directories only.

| Command/check | Actual result |
| --- | --- |
| `git status --short`, `git ls-files`, `git log -3 --oneline` before edits | Existing dirty main; only two `.DS_Store` files and old architecture document tracked. Scaffold, current design/plan, tests and progress untracked; progress and all settings/domain/test stubs empty. |
| `.venv/bin/python -m pytest tests/unit/test_settings.py::test_doctor_redacts_credentials -q` (initial Python 3.15 environment, no cache prefix) | RED: 1 failed; command could not find `busconfig`. Test collected normally and asserted the subprocess result. |
| `.venv/bin/python -m pytest tests/unit/test_settings.py -q --tb=no` (initial environment) | 19 failed because the command module did not exist. |
| `uv sync` (first with sandbox cache prefix) | Failed DNS fetching PyYAML under sandbox; no dependency incompatibility established. |
| `uv sync` (approved outside sandbox, default cache) | Success: Python 3.12.1, 26 packages resolved, 25 installed; lockfile updated. |
| `uv run pytest tests/unit/test_settings.py::test_doctor_redacts_credentials -q` (package shell only) | RED: empty doctor output. Refined the assertion to explicitly require a diagnostic report. |
| `uv run pytest tests/unit/test_settings.py -q --tb=short` (package shell only) | RED: 19 failed; named test specifically failed `doctor must emit its diagnostic report`; validation cases returned 0 instead of 2/3. |
| `uv run pytest tests/unit/test_settings.py -q` (first implementation) | GREEN: 19 passed. |
| `uv run ruff check .` (first pass) | Three import-order findings; fixed only the task's three Python files. |
| `uv run pytest tests/unit/test_settings.py -q --tb=short` (diagnostic-path regression) | RED: 1 failed, 22 passed; quoted synthetic credential leaked through the data path. Fixed by redacting before JSON serialization. |
| `uv run pytest tests/unit/test_settings.py -k http_settings -q --tb=short` (whitespace placeholder regression) | RED: 1 failed, 3 passed, 20 deselected; padded `replace-with-...` model name accepted. Fixed placeholder detection without changing the configured value. |
| `uv run pytest tests/unit/test_selection_contracts.py tests/unit/test_settings.py -q` (final named parent command) | GREEN: 24 passed. The pre-existing selection test file is empty and contributed no tests; this does not verify T01.2. |
| `uv run pytest tests/unit -q` (final affected regression) | GREEN: 24 passed. |
| `uv run pytest -q` (final full existing suite) | GREEN: 24 passed. |
| `uv run ruff format src/busconfig tests/unit/test_settings.py`; `uv run ruff check .` | Formatting applied to task files; final lint passed. Project-local Ruff settings prevent reliance on parent-directory configuration. |
| `uv run busconfig doctor` | Exit 0; Python 3.12.1/application and library versions, `development`, `disabled`, `runtime/data`, `writable: true`. |
| `uv run python -c 'import busconfig; print(busconfig.__file__)'` | Exit 0; imports `src/busconfig/__init__.py`. |
| `uv sync --locked` | Exit 0; resolved 26 packages, checked 25; no lockfile drift. |
| `uv build --out-dir /tmp/busconfig-t011-dist` (approved outside sandbox, repeated after final code/docs changes) | Source distribution and `ai_func_config-0.1.0-py3-none-any.whl` built successfully. |
| Wheel ZIP inspection using `uv run python -` | Verified three `busconfig` modules and console entry point; old `ai_func_config/` package absent. |
| Wheel smoke using the project interpreter from `/tmp`, `PYTHONPATH=/tmp/busconfig-t011-dist/ai_func_config-0.1.0-py3-none-any.whl`, `BUSCONFIG_DATA_DIR=/tmp/busconfig-t011-wheel-data` | Asserted module imported from the wheel, inspected entry point, ran `main(['doctor'])`: exit 0 and writable true; dependencies reused from the verified venv, not a clean-machine install. |
| `uv run pytest tests/integration -q` | Not run: this directory/suite does not exist yet. Plan §1 says unavailable future commands are not business-test failures. |
| `git diff --cached --check` | Reported only three pre-existing Markdown hard-break lines in the supplied design (lines 3–5). Kept that input unchanged. The same check excluding that supplied file passed. |
| `git diff --cached --stat`, scoped source/test/config diff, `git status --short`, `git check-ignore`, Python TOML/document smoke | Inspected staged scope and code; verified secret/runtime/weight/trace ignores and matching Python baseline/lock/document basenames. |

Coverage includes disabled mode without endpoint/name/key, omitted credentials and
credential-bearing URL/query values, sensitive invalid values in safe diagnostics,
quoted secrets in paths, actual temporary write/cleanup, an unusable data path,
invalid mode/budgets, finite positive timeouts, allowed zero optional counts, and
enabled endpoint/name/placeholder validation without network connections.

## Current work and scope review

- Completed: read guidance, parent T01, T01.1, design §§2/5/8/20 and environment
  guidance; checked existing code; established Python 3.12 packaging and settings;
  observed RED→GREEN behavior; ran named and affected/full tests; built and
  inspected package; recorded environment and implementation choices.
- Final review: scoped self-review; user explicitly prohibited delegation.
  Checked output/error paths for secrets, temporary-probe cleanup, exit codes,
  lock/package alignment, and absence of database/model/evaluation dependencies
  in runtime code. Reviewed whitespace-placeholder and path-secret findings with
  failing regressions and fixes. No outstanding review findings.
- Blockers: none for T01.1. Default uv-cache writes, network resolution and Git
  ref writes were sandbox restrictions, resolved with the temporary cache and
  approved local setup commands. CPU inventory restrictions remain documented.
- Unrelated state preserved: modified root/docs `.DS_Store`, pre-existing deletion
  of `docs/design/architecture-v3.md`, untracked original `src/ai_func_config/`
  scaffold and empty `tests/unit/test_selection_contracts.py`; excluded from commit.
  Final inspection found the old source scaffold absent after setup; restored its
  original 60-byte greeting and four empty stubs from the pre-edit read. These
  restored files remain untracked and outside the packaged module/commit.
- No delegation, external messaging, deployment, push or merge performed.

## Next action

T01.2 — freeze selection and value semantics. Start by writing
`test_duplicate_function_rows_are_rejected`, rejecting both `(F,C1),(F,C2)` and
repeated `(F,C1)` with `MULTIPLE_CONFIGS_FOR_FUNCTION` before map construction.
Then add instance-scope, scalar-ID and false/zero/missing cases against the design
§20.2 types. Device instances must remain evidence scope, with one function slot
per decision revision. T01.3 later defines identity/hashes and separate reports.

Required services: none. Data: synthetic only; no order/knowledge snapshots exist.
T01.2/T01.3 and the M0 gate remain unverified and incomplete.

## Rulings and limitations

- Ruling: keep execution limited to T01.1 — the generic parent prompt's domain
  obligations belong to T01.2/T01.3 in the explicit plan. Cost: no selection,
  source-identity or immutable-payload correctness claim is available yet.
- Ruling: adapt the existing checkout on a new local branch and use this file as
  the task ledger — the required inputs were untracked and the user requested
  preservation, a local commit and no delegation. No worktree or generic skill
  script changed those inputs. Cost: unrelated dirt remains visible and staging
  must stay explicit; self-review is not independent review.
- Ruling: retain distribution name, choose diagnostic mode/environment vocabulary
  and process-environment-only loading as detailed in `docs/decisions.md`.
  Cost: future T10 consumers must use or deliberately evolve these settings;
  `.env` users must supply variables through a reviewed loader/environment.
- No design or plan content was amended. Existing documents/guidance are adopted
  unchanged as T01.1 inputs/deliverables.
- Final review: minor (preserved input formatting): three existing Markdown
  hard-break lines trigger Git's trailing-whitespace check in the supplied design.
  They are intentional display formatting and were not normalized in this task.
- Verified on this macOS/Python 3.12.1 machine only; no clean-machine/Windows/Linux
  reproduction or real model/database test. Doctor validates local setup, not
  service availability or engineering behavior. Hardware details have the
  restrictions recorded in `docs/environment.md`.
