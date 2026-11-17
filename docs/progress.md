# Implementation progress

Design: Bus_Config_AI_Detailed_Design_EN_v3.md
Plan: Bus_Config_AI_Implementation_Plan_EN_v1.md
Current milestone: M0
Current subtask: T01.2
Status: verified
Verified date: 2026-11-17 (Asia/Shanghai)

## Last verified unit — T01.2

- Local commit: the commit containing this entry, titled
  `feat: enforce T01.2 selection and value contracts`.
  Resolve it with `git log -1 --format=%H -- docs/progress.md`.
- Branch: `codex/t01-2-selection-contracts`, based on `b75febb`.
- Initial inspection: clean `main`; T01.1 had been merged as PR #1 since the
  preceding session. No domain package or selection test file existed. No
  unrelated changes needed preservation or prerequisite repair.
- Files changed: `src/busconfig/domain/{__init__,contracts,invariants}.py`,
  `tests/unit/test_selection_contracts.py`, `README.md`, `docs/decisions.md`,
  `docs/progress.md`. Python version, package/dependency configuration, doctor,
  supplied design and implementation plan remain unchanged.
- Result: one scalar configuration revision per function in a validated selection
  map; duplicate rows fail before map construction; instance scopes add no slots;
  explicit value states preserve false, zero and missing/blank distinctions.

## T01.2 verification evidence

All `uv` commands below used `UV_CACHE_DIR=/tmp/busconfig-uv-cache` in the sandbox.
All inputs were synthetic. Tests required no database, model or external service.

| Command/check | Actual result |
| --- | --- |
| `git status --short --untracked-files=all`; `git log -2 --oneline`; `git branch --show-current` | Clean main at `b75febb`; T01.1 implementation commit `3143aaa` followed by merge. |
| `uv run pytest -q` before changes | 24 passed; existing settings/doctor baseline. |
| `uv run pytest tests/unit/test_selection_contracts.py -q` after writing tests | Collection error: domain package absent. Recorded as a setup dependency, not proof of duplicate behavior. |
| `uv run pytest tests/unit/test_selection_contracts.py -q --tb=short` with contract shell and explicit unimplemented validator | RED: 9 failed, 15 passed. Duplicate-row, instance-scope, empty-draft and boundary tests reached `NotImplementedError` instead of their expected results. |
| `uv run pytest tests/unit/test_selection_contracts.py -q` after row validation | GREEN: 24 passed, including identical rows, distinct configs, distinct revisions, separate instances, scalar IDs and explicit clear requests. |
| `uv run pytest tests/unit/test_selection_contracts.py -k 'false_zero_missing or known_requires' -q --tb=short` | RED: 2 failed, 42 deselected; value-state type not yet defined. |
| `uv run pytest tests/unit/test_selection_contracts.py -q --tb=short` with value types but no state consistency validator | RED: 13 failed, 31 passed; invalid state/value pairs did not raise. |
| `uv run ruff check --fix src/busconfig/domain tests/unit/test_selection_contracts.py` | Fixed one import-order finding; reported one long test line, subsequently resolved by formatter. |
| `uv run ruff format src/busconfig/domain tests/unit/test_selection_contracts.py`; `uv run ruff check .` | Two files formatted; lint passed. |
| `uv run pytest tests/unit/test_selection_contracts.py tests/unit/test_settings.py -q` | GREEN: 68 passed (44 domain cases, 24 existing settings cases). |
| `uv run pytest tests/unit -q` | GREEN: 68 passed. |
| `uv run pytest -q` | GREEN: 68 passed. |
| Isolated mutation check via `uv run python -` and a temporary copy of `busconfig/domain`; removed only the pre-map duplicate guard; ran `pytest ... -k duplicate_function_rows_are_rejected -q --tb=short` in that copy | All 3 duplicate cases failed with `DID NOT RAISE SelectionInvariantError`, proving dictionary overwriting cannot silently satisfy the tests. Repository implementation was not modified by this check; temporary copy removed. |
| `uv run ruff format --check src/busconfig/domain tests/unit/test_selection_contracts.py`; `uv run ruff check .` | Four files already formatted; all lint checks passed. |
| `git diff --cached --check`; `git diff --cached --stat`; scoped staged source/test diff | Passed whitespace checks; inspected all seven staged files and confirmed only T01.2 scope. |

Additional assertions cover non-null persisted selections, explicit null clear
requests, omitted request-field rejection, array/comma-string/type rejection,
unmapped instances, rejecting pre-collapsed dictionaries, revalidating untrusted
constructed rows, independent decision revision scopes, contradictory value states,
finite numbers, structured bindings, raw source text, source block IDs, and
current/historical/planned scope through JSON round trips.

## T01.2 review and rulings

- Used the available executing-plans, test-driven-development and
  verification-before-completion skills. Executed locally, without delegation.
- Final review: scoped self-review of contracts, validator, tests and docs. Checked
  list-before-map validation, duplicate-before-construction ordering, absence of
  instance slots, explicit null semantics, no truthiness coercion, and runtime
  independence from planner/model/evaluation code. No outstanding findings.
- Ruling: define only the source assertion fields needed for T01.2 value semantics,
  using design §8.1 and its four states — do not create a replacement matching
  schema or prematurely build decision/report objects. Cost: source versions,
  locators, collision detection and immutable payload serialization remain T01.3.
- Ruling: represent observed blank/absent text through retained `raw_text`, while
  an unresolved fact remains `MISSING` — no fifth value state is invented. Cost:
  T03 must preserve that raw evidence and implement the standalone-slash rule;
  these contracts do not infer missingness by inspecting arbitrary text.
- Ruling: work on a local feature branch with this file as the ledger, retaining
  the existing Python baseline — the user requested one scoped subtask and local
  commit, with no delegation. Cost: review is by the author, not an independent
  reviewer; no interpreter compatibility claim beyond the tested environment.
- Blockers: none. No prerequisite repair, deployment, push, merge or messaging.

## Next action — T01.3

Freeze identity and canonical serialization. Begin with
`test_revision_hash_is_order_independent`, `test_source_id_collision_is_rejected`
and `test_report_does_not_mutate_payload_hash`. Complete stable source identity,
locators/version scope, issues and typed result contracts; keep validation reports
outside the immutable decision payload; deliver `docs/contracts.md` examples and
schema version. No services required; use synthetic inputs only.

Limits: T01.2 validates input representation and selection cardinality for one
revision. It does not prove configuration ownership/existence in pinned knowledge,
candidate suitability, source identity integrity, approval eligibility, deep
decision immutability or persistence. The typed map is an ordinary Python mapping;
later consumers still need independent whole-order validation. Integration tests
do not exist yet and were not claimed as run. M0 remains incomplete until its
remaining tasks/gates pass.

# Historical record — T01.1

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
