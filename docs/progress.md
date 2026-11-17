# Implementation progress

Design: Bus_Config_AI_Detailed_Design_EN_v3.md
Plan: Bus_Config_AI_Implementation_Plan_EN_v1.md
Current milestone: M0
Current subtask: T01.3
Status: verified
Verified date: 2026-11-17 (Asia/Shanghai)

## Last verified unit — T01.3

- Local commit: the commit containing this entry, titled
  `feat: freeze T01.3 identity and serialization contracts`.
  Resolve it with `git log -1 --format=%H -- docs/progress.md`.
- Branch: `codex/t01-3-identity-contracts`, based on `9ef891d`.
- Initial inspection: clean working tree on `codex/t01-2-selection-contracts`.
  The existing 68 tests passed. No unrelated changes were present.
- Changed files: `src/busconfig/domain/{contracts,invariants,immutable,serialization}.py`,
  `tests/unit/{test_identity_contracts,test_selection_contracts}.py`,
  `docs/{contracts,decisions,progress}.md`, `README.md`.
- Result: schema 1.0 source identities/locators, issues and typed result records;
  immutable nested decision content; canonical payload/report hashes; source reuse
  and stale report rejection. Selection cardinality and evidence-only instances
  remain intact. Supplied design/plan, Python baseline and dependencies unchanged.

## T01.3 verification evidence

All `uv` commands used `UV_CACHE_DIR=/tmp/busconfig-uv-cache`. Tests and examples
use synthetic values only. No database, model endpoint or network was needed.

| Actual command/check | Observed result |
| --- | --- |
| `git status --short --untracked-files=all`; `git branch --show-current`; `git log -3 --oneline` | Clean T01.2 branch at `9ef891d`; created local T01.3 branch from it. |
| `uv run pytest -q` before edits | 68 passed. |
| `uv run pytest tests/unit/test_identity_contracts.py -q --tb=short` after writing tests | RED: 10 failed. Nested fact mutation did not raise; remaining new identity/hash types/functions were missing. |
| Same identity command after initial implementation | 7 failed, 3 passed. Pydantic treated generic dataclass `FrozenMap` as a dataclass instead of using its validator. Replaced that helper with an immutable Mapping class. |
| Same identity command after mapping repair | 9 passed, 1 failed: the test's new report copied a stale supplied hash. Fixed the fixture to omit the old hash when constructing a new report, retaining rejection of mismatched supplied hashes. |
| Same identity command with boundary regressions | RED: 5 failed, 11 passed. Duplicate JSON keys were overwritten before hash validation, public copy updates bypassed validation, and ParseResult/report-binding/advisory types were not yet implemented. |
| Same identity command after boundary implementation | GREEN: all 16 identity cases passed (with the 44 selection cases: 60 passed). |
| Same identity command with reference/proposal tests | RED: 2 failed, 20 passed; assertion-reference order changed the hash and extraction proposals accepted human-confirmed assertions. Both corrected. |
| `uv run pytest tests/unit/test_identity_contracts.py -k 'report_check_reference or model_response' -q --tb=short` | RED: 2 failed, 22 deselected; report-check reference order affected hashing and ModelResponse was missing. Both corrected. |
| `uv run pytest tests/unit/test_identity_contracts.py -k 'reused_as_block or itself_as_parent' -q --tb=short` | RED: 2 failed, 24 deselected; cross-type source-ID aliasing and self-parent revisions were accepted. Both corrected. |
| `uv run pytest tests/unit/test_identity_contracts.py -k configuration_attributes -q --tb=short` | RED: 1 failed, 26 deselected; configuration attributes accepted a bare boolean without a value state. Introduced explicit AttributeValue and updated the new test caller. |
| `uv run pytest tests/unit/test_identity_contracts.py -q` after attribute tightening | 26 passed, 1 failed: a custom mapping before-validator lost JSON-mode tuple conversion. Compared direct AttributeValue, dict and FrozenMap validation; isolated JSON/Python schema paths to retain strict validation and JSON-array support. |
| `uv run pytest tests/unit/test_identity_contracts.py -q` final | GREEN: 27 passed. |
| `uv run pytest tests/unit/test_selection_contracts.py tests/unit/test_settings.py -q` | GREEN: 68 passed; named T01 parent verification. |
| `uv run pytest tests/unit -q` | GREEN: 95 passed. |
| `uv run pytest -q` | GREEN: 95 passed. |
| `uv run ruff format ...`; `uv run ruff check --fix ...`; `uv run ruff check .` | Formatting/import findings corrected in task files; lint passed. |
| `uv run ruff format --check src/busconfig/domain tests/unit/test_identity_contracts.py tests/unit/test_selection_contracts.py` | Initial final-check found one wrapping change in immutable.py; formatted that file, then all 7 checked files passed. |
| `uv run python -` documentation/schema smoke | All 4 JSON examples in docs/contracts.md validated; decision/report hashes and source references matched; JSON Schema generated for all 57 contract models. |
| `git diff --check` and scoped source/doc review | No whitespace errors; reviewed canonicalization, immutable boundaries, source registries, typed result fields and compatibility changes. |
| `git diff --cached --check`; `git diff --cached --stat`; scoped staged diff; `git diff --name-only` | All staged checks passed; 10 scoped files, no unstaged edits. |

New tests include the three named T01.3 behaviors:
`test_revision_hash_is_order_independent`, `test_source_id_collision_is_rejected`,
and `test_report_does_not_mutate_payload_hash`. They also cover changed facts and
semantic sequences, false versus zero, snapshot/generation/parent binding, immutable
nested values and detached serialization, stale/forged hashes, reused source IDs,
native locators, Unicode, issue severity, parser completeness, advisory/model
separation and preservation of complete candidate descriptions.

Integration tests still do not exist; no integration test run is claimed. The
documentation examples demonstrate contracts, not a released order dataset.

## T01.3 review, rulings and limitations

- Used executing-plans, test-driven-development, verification-before-completion
  and systematic debugging for the observed Pydantic failures. Final review is
  scoped self-review; delegation was explicitly prohibited.
- Ruling: repair T01.2 nested mutability as a prerequisite to immutable payloads.
  Cost: Python callers see tuples/FrozenMap; JSON stays arrays/objects, and public
  copy updates now validate. Updated the existing affected test caller.
- Ruling: define §20.2 result containers and supporting records as data-only
  contracts. Cost: algorithmic eligibility, restricted expression compilation,
  approval, durable identity registration and persistence are still later tasks;
  constructing a record does not prove its engineering claims.
- Ruling: use a versioned project canonical encoding with exact source strings and
  finite JSON numeric types. Cost: future normalization/encoding changes require
  explicit producer/schema changes; hashes must not be silently migrated. No
  implicit unit-equivalence or arbitrary Decimal-object support is claimed.
- Ruling: source reuse checks compare all supplied records. Cost: callers must
  include prior registrations to detect cross-import reuse until T11 persistence.
- Ruling: self-review on a new local branch with this file as the execution ledger.
  Cost: no independent reviewer; no other-platform/clean-machine qualification.
- Blockers: none. No database, model client, deployment, push, merge or messaging.
  No outstanding scoped review findings.

## Next action — T02.1

Define the invented engineering world and hand-write E01–E10 reference outcomes
before planner implementation. Start `test_anchor_selection_cardinality`, keeping
E04's complementary same-function alternatives unselected and including E07
ambiguity and E08 reviewed cross-function composition. Keep reference answers out
of runtime inputs. No services required; synthetic data only.

T01's three subtasks are now locally verified; M0 is not complete until T02 and
its independent-anchor gate pass. Hashing/schema tests are not database,
whole-order validation, model-client or deployment qualification.

# Historical record — T01.2

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
