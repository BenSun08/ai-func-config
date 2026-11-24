# Implementation progress

Design: Bus_Config_AI_Detailed_Design_EN_v3.md
Plan: Bus_Config_AI_Implementation_Plan_EN_v1.md
Current milestone: M1 (deterministic baseline)
Current subtask: T03.1, spreadsheet structure and provenance
Status: verified locally on `codex/t03-1-xlsx-structure`
Verified date: 2026-11-24 (Asia/Shanghai)
Next subtask: T03.2, spreadsheet value and formula rules

## T03.1 — Spreadsheet structure and provenance

The parser mapped 74 source cells across the 18 scope-banded native order
workbooks. In M32-r1, logic B8 retained its two lines, field heading B7 and
scope band A6:C6. Pins B6, D6 and E6 retained current DIAL-A, historical
DIAL-B and planned spare input respectively. The samples below record the
parser's complete output, including the mapping diagnostics.

| Files changed | Purpose |
| --- | --- |
| `src/busconfig/domain/contracts.py` | Add the missing `LayoutProfile` input contract and reuse the existing three statement-scope literals. |
| `config/layouts/mica-{logic,pins,switches,trim}-v1.yaml` | Declare the role, sheet, preamble and required scoped headers for the banded Mica order sources. |
| `src/busconfig/ingest/{__init__,xlsx_parser}.py` | Implement `parse_xlsx(source, profile) -> ParseResult` with the schema 1.0 block-ID, locator, issue and completeness contracts. |
| `tests/integration/test_xlsx_parser.py` | Exercise the public parser against native workbooks, including changes of column order, damaged mappings, blank cells and inert links. |
| `tests/fixtures/xlsx/{reordered,partial}/pins.xlsx` and adjacent `pins.normalized.json` | Two synthetic derivatives of the M32 pin workbook. Each JSON contains the source hash, native cell evidence, issues and completeness report. |
| `docs/{decisions,progress}.md` | Record the mapping rules, verification and handoff. |

**Parser issue report.** The [reordered sample](../tests/fixtures/xlsx/reordered/pins.normalized.json)
has five blocks and zero issues. Its planned and historical columns have exchanged
positions. The [partial sample](../tests/fixtures/xlsx/partial/pins.normalized.json)
has five blocks and seven blocking `PARSE_INCOMPLETE` issues. B5 and C5 lost
their merged scope, D5 sits under an incorrect scope, three required pairs are
therefore missing, and one worksheet has no mapping. The values in B6:D6 remain
available at their original addresses with unresolved status.

### Commands and observed results

The uv commands used `UV_CACHE_DIR=/tmp/busconfig-uv-cache`. The local task branch
starts at `556b6a9`. The pre-existing change to `.DS_Store` was excluded.

| Command or check | Observed result |
| --- | --- |
| `git status --short --branch --untracked-files=all`, `git log -5 --oneline --decorate`, `git switch -c codex/t03-1-xlsx-structure` | Inspected main and created the local branch. Baseline `uv run pytest -q` passed all 171 tests. |
| `.venv/bin/python -` with openpyxl on the original Mica workbooks | Inspected native sheet names, scope merges, headers, cells and multiline text. The same logic profile has field headers on different rows across orders. |
| `uv run pytest tests/integration/test_xlsx_parser.py -q --tb=short` before parser code | Both named tests collected and failed at the missing `busconfig.ingest` import. With the rest of the initial cases, `-q --tb=line` reported eight failures. The first implementation passed all eight. |
| `uv run pytest tests/integration/test_xlsx_parser.py -q --tb=short` during review | Three failures exposed missing data-region reporting, a header-only success and a second table inheriting the first table's scopes. Another three exposed coarse region reporting and a field header merged into data that was accepted as mapped. |
| Same test file with `-k 'scope_word or hidden_rows' -q --tb=short` and later `-k second_table -q --tb=short` | Reproduced a literal scope word truncating valid data, then a separated second band with an unfamiliar field heading being accepted. The final cases preserve the literal and report the second section as unsupported. |
| Same test file with `-k link_target -q --tb=short` | The first setup omitted the blank link when saved. A native B9:B10 hyperlink range exposed the real failure: openpyxl supplied the external target as B9's cell text. The final parser retains blank B9 and the authored identical target text in B10. |
| `uv run python -` with the existing synthetic `save_native` renderer, then native reload | Wrote and reopened the two fixture variants. A separate `uv run python -` parsed all 18 banded manifest entries using their pinned revisions and SHA-256 values, checked the cells and scope anchors against the workbooks, and round-tripped the results. |
| `uv run python -` using `ParseResult.model_validate_json` and `parse_xlsx` | Reloaded both committed-format JSON examples and compared each entire report to a fresh parse of its workbook. Both matched. |
| `uv run pytest tests/integration/test_xlsx_parser.py -q` | Final named suite passed all 15 cases. |
| `uv run pytest tests/unit -q`, `uv run pytest tests/integration -q`, `uv run pytest tests/acceptance/test_anchor_integrity.py -q` | 115 unit tests, 15 integration cases and 56 anchor regressions passed. |
| `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check src synthetic evals tests` | Final full suite passed all 186 tests. Lint and formatting passed. |
| `git diff --cached --stat`, scoped `git diff --cached`, `git diff --cached --check`, `git diff --name-only` | Reviewed the 14 staged files locally. The whitespace check passed. Only `.DS_Store` had an unstaged change. The local commit containing this record is titled `feat: extract T03.1 spreadsheet structure with provenance`. |

**Handoff.** No T03.1 blockers. This parser produces structural blocks for the
four declared order layouts. Assertions are empty at this stage. Formulas
retain their expressions and require review. T03.2 owns typed values, blank
markers and cached formula values. T03.3 owns the shared archive guard, limits
and cross-import checks. The unbanded knowledge, submission and parent-decision
tables require their own mappings.

## M0 review repairs

The review reopened the [foundation gate](Bus_Config_AI_Implementation_Plan_EN_v1.md#8-stage-gates-and-verification-commands)
after the original 137 tests passed. A stale order context survived JSON reload,
and the acceptance suite admitted bad fixture variants even after their digests
were updated. The repair branch starts at clean `main` commit `2d5dfeb`.

| Files changed | Repair and observable result |
| --- | --- |
| `src/busconfig/domain/{contracts,invariants}.py`, `tests/unit/test_identity_contracts.py`, `docs/contracts.md` | Constructors and JSON reload reject facts or requirements from another order. A stable configuration has one owner across its revisions. A generated source ID must match its document revision and locator. Assertions, facts and attributes distinguish false from zero in sets, including nested values. Model assertions require a span for each cited block. Nonempty requirement and link proposals require spans. |
| `synthetic/inputs.py`, `evals/types.py` | Reject explicit answer headers and duplicate YAML keys before rendering. A second case cannot move an order into a different family by relabelling it. Mutating a yielded catalog cannot affect the next order. |
| `synthetic/renderers/fixtures.py` | Reject two orders sharing one directory, a pinned order without any native sources, and text that Excel would truncate. An existing-pack retry compares real bytes and checks for file or directory changes across the entire read. |
| `tests/acceptance/test_anchor_integrity.py`, `docs/synthetic-data.md`, `docs/progress.md` | Cross-check native order coverage against the input manifest. Read field/value tables under their DOCX owners and revisions. Check the typed E08 bench samples against the hand-reviewed pulse, count, lamp and ACK timeline. Record the fixture and gate contracts. |

### Commands and evidence

Commands below used `UV_CACHE_DIR=/tmp/busconfig-uv-cache` for uv. The authored
world, 12 evaluator references, family assignments and committed native files
have a clean diff against the base.

| Command or experiment | Observed result |
| --- | --- |
| `uv run pytest -q` before edits | 137 passed. |
| `uv run pytest tests/unit/test_identity_contracts.py -q -k 'stale_members or one_owner or still_identify or distinct_in_sets or each_cited_block' --tb=line` | All 16 new checks failed against the old contracts. Invalid records validated and false compared equal to zero. After the first repair, all 111 then-current unit tests passed. |
| `uv run pytest tests/unit/test_identity_contracts.py -k 'readable_suffix or omit_its_spans' -q --tb=line` | Four failures exposed an overbroad generated-ID check and spanless requirement/link proposals. All four passed after correction. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k 'correct_answer_header or relabelled or raw_duplicate or share_mutable or own_native or never_truncates or changed_during_comparison' -q --tb=line` | Eight input, split and renderer checks failed on the intended behaviors. The first race test used different-sized edits and stopped before the byte reads. Repeating `-k changed_during_comparison` with same-size edits reproduced the false success on a pack that was inconsistent throughout the comparison. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k raw_duplicate -q --tb=line`, then `-k correct_answer_header` | A duplicate inside a merged YAML mapping and two further explicit answer labels initially passed through. Final tests reject them and continue to accept the engineering header “Expected input voltage”. |
| In separate temporary copies, ran `python -m pytest tests/acceptance/test_anchor_integrity.py -k e08_native_trace -q --tb=short` and the same command with `-k native_revision_fields` | Changing only the 72 ms lamp sample to on failed at that sample. Changing only the DOCX writer to emit DIAL-B for LEVEL-A.1 failed against DIAL-A. Both tests passed on the authored inputs and renderer. |
| `uv run pytest tests/unit/test_selection_contracts.py tests/unit/test_settings.py tests/unit/test_identity_contracts.py -q` and `uv run pytest tests/acceptance/test_anchor_integrity.py -q` | 115 unit tests and 56 anchor acceptance tests passed. |
| `uv run pytest -q` and final `uv run pytest tests/unit tests/acceptance/test_anchor_integrity.py -q` | 171 passed in each run, with zero skips. Integration tests begin at T03. |
| `uv run python -m synthetic.renderers.fixtures --suite anchors --output runtime/anchors`, repeated with a fresh temporary destination, then `diff -qr` against `tests/fixtures/anchors` | Both the retry and fresh render matched the committed pack. An independent SHA-256 read verified all 23 manifest entries. |
| `soffice --headless --convert-to pdf` for M32-r1 pins and the function library, followed by `pdftoppm` first-page inspection | Calc showed DIAL-A under current, DIAL-B under historical and spare input under planned. Writer showed F-LEVEL → LEVEL-A.1 with DIAL-A, momentary and 0/2/5/0. Font-cache warnings did not prevent either page from rendering. |
| `uv run busconfig doctor`, `uv run python -c 'import busconfig'`, `uv build --offline --out-dir /tmp/busconfig-m0-verification.MO6RCd/dist` | Doctor reported disabled model mode and writable data. Import and both builds passed. Archive inspection found no fixture or evaluator paths in the 15 wheel members or 16 source distribution members. |
| `uv run ruff check .`, `uv run ruff format --check src synthetic evals tests`, `git diff --check` | Passed. Reviewed the scoped diff locally. |

**Handoff.** All reproduced M0 findings have regression coverage. The local M0
gate passes. Four public development families cover the authored anchors.
Independent holdout families, parser-level source lookup and database concurrency
remain later milestone work. Cumulative M0 focused hours were not recorded.
Next is **T03.1**, extracting merged headers and multiline cells with native
provenance while preserving current, historical and planned column scopes.

## T02.3 — Native anchor fixtures

The [input-only native manifest](../tests/fixtures/anchors/manifest.json) inventories
22 XLSX files and one DOCX, totalling 159,118 native-file bytes. Twelve order
revisions share one MICA-K1 catalog. The 12 independent references still specify
five selections, five required abstentions, one resolved exclusion and one
rejected submission. The public `orders/E01` directory implements the §5.5 demo
path for business revision M31-r1.

| Files changed | Purpose |
| --- | --- |
| `synthetic/{__init__,inputs}.py`, `synthetic/renderers/{__init__,fixtures}.py` | Verify the input snapshot once, render its catalog and scoped orders, and publish a complete directory with hashes, revisions, roles, layout profiles and source row locators. An intact output is reusable. |
| `synthetic/worlds/{core.yaml,manifest.json}` | Give the sleep exception in M32-r1 L32.B its own line in the same cell and repin the world. A parsed comparison with the base identified this single whitespace change. |
| `tests/fixtures/anchors/`, `tests/acceptance/test_anchor_integrity.py` | Commit the inspectable native pack. Compare two fresh renders with it, check every file digest, and read native cells, merged scope bands, revision ownership and decision history. |
| `docs/{synthetic-data,progress}.md` | Add the fixture command, navigation, visual review and verification record. |

### Commands and observed results

All `uv` commands used `UV_CACHE_DIR=/tmp/busconfig-uv-cache`.

| Command or check | Observed result |
| --- | --- |
| `git status --short --branch --untracked-files=all`, `git log -3 --oneline`, `git switch -c codex/t02-3-native-fixtures` | Clean main at `6034698`. Created the local task branch there. |
| `uv run pytest -q` before edits | 128 passed. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py::test_fixture_manifest_hashes -q --tb=short` before implementation | RED. The real CLI produced no native manifest. Its renderer module was missing. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k 'fixture_manifest_hashes or order_cells_headers or native_knowledge or render_reuses' -q --tb=short` | Initial renderer passed all four behaviors. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k 'multiline_parent or empty_order_inventory' -q --tb=short` | Both failed. L32.B was single-line and an empty inventory could publish a manifest. Added the authored line break and shared the validated loader with the suite iterator. Both passed in the six-test rerun. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k 'fixture_manifest_hashes or render_uses_native or untraceable_rows' -q --tb=short` | Four failures exposed the missing canonical pack, a scope band dependent on YAML key order, overlapping source rows, and a cell with no defined column. Generated the pack, grouped scopes by physical column and rejected untraceable cells before publication. |
| `uv run python -m synthetic.renderers.fixtures --suite anchors --output tests/fixtures/anchors`, then the same command with `--output runtime/anchors` | Both produced the input manifest and 23 native files. `diff -qr runtime/anchors tests/fixtures/anchors` passed. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py::test_fixture_manifest_hashes -q` | 1 passed. Every declared SHA-256 matched its file. Reopened workbooks and documents agreed semantically across both fresh renders and the canonical pack. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -q` | First full run flagged the existing input loader's forbidden-path literal as an evaluator dependency. Scoped that static check to the renderer and exercised the command from a fixture-only checkout. Final run: 42 passed. |
| `uv run pytest tests/unit -q`, `uv run pytest -q` | 95 unit tests passed. All 137 repository tests passed. Integration tests begin at T03. |
| `uv run ruff check .`, `uv run ruff format --check synthetic tests/acceptance`, `git diff --check` | Passed. |
| `uv run python -I -` isolation smoke | Rendered the pack with only the synthetic package and installed dependencies available. Confirmed `evals` was unavailable. The manifest matched the runtime copy. An offline scan checked ZIP CRCs and all XML parts for evaluator labels and reference notes. |
| `uv run python -` source and Markdown checks, `git diff --exit-code HEAD -- src evals` | The authored world differs only by the L32.B line break. All 11 guide links resolve. Runtime sources, answers and family assignments match the base. |

**Viewer comparison.** Opened all three M32-r1 workbooks in LibreOffice Calc
using `soffice --headless --convert-to pdf`, rasterized the pages with
`pdftoppm` and inspected the visible text. B6 showed current DIAL-A, D6
historical DIAL-B and E6 planned spare input. Logic B8 retained the awake-only
0/2/5/0 sequence and the sleep exception. Switches B5/D5 showed momentary/PETAL.
The bundled `render_docx.py --emit_pdf` opened the library in LibreOffice
Writer. Its five rendered pages showed all five function headings and thirteen
revision headings under their respective owners. macOS Quick Look also displayed
the current pin and the F-LEVEL heading with its four revisions. An additional
Numbers import displayed a blank sheet and exposed no table to the UI check.
The Calc and Writer page inspections supplied the required viewer evidence.

**Original T02.3 handoff.** The T01 contract tests, T02 anchor integrity and native
fixture gate passed locally at that revision. The subsequent M0 review and repair
record above supersedes its sign-off. Reproducibility evidence covers the pinned local tools and the native
content checked by the tests. The independent families for validation and test,
parser behavior and matching metrics belong to later work. Cumulative focused
hours for M0 were not measured. Next is **T03.1**, extraction of merged headers,
multiline cells and column scope with native provenance.

## T02.2 — Input isolation and family splits

The input manifest pins the authored world and all 12 order revisions. The
fixture loader returns the catalog and one order. The offline evaluator checks
each anchor's input pointer and family split. The 12 hand-authored outcomes
and their reasoning match the pulled baseline, including all five abstentions.

| Files changed | Purpose |
| --- | --- |
| `synthetic/worlds/manifest.json`, `synthetic/inputs.py` | Input-only inventory, digest verification, order scoping and rejection of evaluator material. |
| `evals/splits.json`, `evals/types.py`, `evals/gold/anchors.json` | Family assignments and consistency checks. Only the 12 input pointers changed in the answers. |
| `tests/acceptance/test_anchor_integrity.py` | Check actual bundles and case families, then inject contaminants and split errors into temporary copies. Check runtime Python imports and literal evaluator references. |
| `docs/synthetic-data.md`, `docs/decisions.md`, `docs/progress.md` | Loader usage, partition policy and verification record. |

### Verification

All `uv` commands used `UV_CACHE_DIR=/tmp/busconfig-uv-cache`.

| Actual command or check | Observed result |
| --- | --- |
| `git status --short --branch --untracked-files=all`, `git switch main`, `git pull --ff-only origin main`, `git switch -c codex/t02-2-fixture-isolation` | Started on clean T02.1 at `f11c2b5`. Local main fast-forwarded from `29c7fee` to `f729251`. Created the local task branch there. |
| `uv run pytest -q` before edits | 106 passed. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k 'gold_is_not_application_input or near_duplicates_share_split' -q --tb=short` before implementation | Both named tests failed on their missing manifests. With additional negative cases, the acceptance file initially had 12 failures and 15 passes. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k 'nested_gold_path or answer_header or direct_application' -q --tb=short` | Three new cases failed because nested gold paths, answer headers and an evaluator redirect were accepted. All three passed after closing those paths. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k engineering_expectation -q --tb=line` | RED on the legitimate “Expected input voltage” header. Narrowed the label check to evaluation terms. |
| Final named test command with `-q`, then `uv run pytest tests/acceptance/test_anchor_integrity.py -q` | 2 named tests passed. All 33 acceptance tests passed. |
| `uv run pytest tests/unit -q` and `uv run pytest -q` | 95 unit tests passed and 128 passed in the full suite. The integration directory does not exist yet. |
| `uv run ruff check .`, `uv run ruff format --check evals synthetic tests/acceptance`, `git diff --check` | Passed. |
| `uv build --out-dir /tmp/busconfig-t022-dist.udFCUK` and `uv run python -I -` artifact smoke | Built the source distribution and wheel. Inspected archive members. With only the wheel, fixture loader and input directory available as project inputs, loaded M34-r1 and round-tripped its scoped payload through the model request data contract. The slash cell survived and the evaluator was unavailable. |
| `python3 -` comparing gold to `git show f729251:evals/gold/anchors.json`, checking world/runtime diffs and guide links | Only the input path changed in each of the 12 cases. The authored world and runtime sources match the base. All four local guide links resolve. |

**Review and limits.** Scoped self-review against T02 and design §§18 and 22.
All four public families remain in development. Validation and test are empty.
The isolation checks cover the authored bundle, package artifacts, ordinary
runtime imports and literal references. Review is still needed for the meaning
of new free-text engineering evidence. Live inference and container image
verification belong to their owning tasks. No implementation blockers.

**Next subtask — T02.3.** Render the native XLSX and DOCX fixtures from the
scoped inputs, verify file hashes and semantic content, and compare one order
in spreadsheet and document viewers. M0 remains open.

## T02.1 — Synthetic engineering world and reference outcomes

The Mica release covers five configurable functions and thirteen fixed revisions.
Twelve independent order cases cover E01–E10 plus the two comparison variants.
Their hand-authored references specify five selections, five required abstentions,
one resolved exclusion and one rejected submission. The evidence links retain
the order revision, source cells and statement scope.

| Files changed | Purpose |
| --- | --- |
| `synthetic/worlds/core.yaml` | Invented catalog, controllers, pins, signals, switches, reviewed rules, composition trace and versioned order inputs. |
| `evals/__init__.py`, `evals/types.py`, `evals/gold/anchors.json` | Offline `build_anchor_suite()`, explicit outcome types, source relationships, required issues, reference reasoning and evaluation-only ranks/scores. |
| `tests/acceptance/test_anchor_integrity.py`, `pyproject.toml` | Acceptance checks. Pytest can import the repository-local evaluator through its console entry point. |
| `docs/synthetic-data.md`, `docs/decisions.md`, `docs/progress.md` | Case guide, fixture representation and verification record. |

### Commands and observed results

All `uv` commands below used `UV_CACHE_DIR=/tmp/busconfig-uv-cache`.

| Command or check | Result |
| --- | --- |
| `git status --short --branch`, `git log -1 --oneline`, `git worktree list` | Started on clean `main` at `29c7fee`. |
| `uv run pytest -q` before edits | 95 passed. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -q` with only the named test written | RED. One assertion failed with “missing hand-authored E01–E10 reference outcomes”. |
| Same test file with `--tb=line` | Before fixtures, one failure and six missing-evaluator setup errors. After adding the world, gold and loader, the cardinality test passed but console pytest still could not import `evals`. |
| `uv run python -m pytest tests/acceptance/test_anchor_integrity.py -q --tb=short` | 7 passed. Setting pytest's repository-root import path in `pyproject.toml` then gave 7 passed with the plan's exact console command. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -q --tb=short` after adding the E08 timing check | RED. 1 failed, 7 passed. The sender lacked `emit_delay_ms`. Added the fixed sender/receiver timing values supporting the reviewed trace. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -q` final | 10 passed, including independent cardinality/ownership checks for every acceptable map, source scopes, both comparison variants and the E08 timing budget. |
| `uv run pytest tests/unit -q` and `uv run pytest -q` final | 95 unit tests passed. The complete suite passed all 105 tests. No integration directory exists yet. |
| `uv run ruff format evals tests/acceptance`, `uv run ruff check .`, `uv run ruff format --check evals tests/acceptance` | One test file formatted. Final lint and format checks passed. |
| `uv run python -` inspecting M32 and trying malformed answers in memory | Loaded all 12 cases. M32's current DIAL-A, awake-only cycle and momentary switch jointly require LEVEL-A.1. Its rank is 2 on all three rows at cutoff 1. Duplicate function key and list-valued selection mutations were both rejected. |
| `uv build --wheel --out-dir /tmp/busconfig-t021-wheel.vHRJzL` and `python3 -` inspecting its ZIP members | The wheel contained only `busconfig/` and distribution metadata. It contains no fixtures or evaluator. |
| `git diff`, `git diff --no-index` for new files, `git diff --check`, local Markdown link smoke with `python3 -` | Reviewed the scoped diff, including untracked files. Both links in the new guide resolve. |

**Review and limitations.** Self-reviewed against design §§18 and 22 using the
executing-plans, test-driven-development and verification-before-completion skills.
The public examples use the development split. E04.positive's GLINT revision
scores +2, ahead of SHADE at 0, but misses the mandatory reset. Both remain
unselected. The ranks, scores and trace are fixture-level evidence. Runtime
retrieval, planning and model packet construction belong to later tasks.

**Initial handoff.** The first attempt to create the task branch stopped at the
automatic approval review's usage limit. The user chose to leave the changes
uncommitted on `main` at that point.

**Pre-push review.** Compared the pending files with `29c7fee` and the T02.1
business rules. In E08, raising ACK and releasing BUTTON at 60 ms violated
M40's minimum spacing between input edges. Moved the button release to 100 ms.
The input edges now occur at 20, 60 and 100 ms. The expected lamp activation
at 28 ms and reset at 72 ms still hold.

| Review command | Observed result |
| --- | --- |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -k e08_review_trace -q --tb=short` before correction | New regression failed on the simultaneous edges. |
| `uv run pytest tests/acceptance/test_anchor_integrity.py -q` after correction | 11 passed. |
| `uv run pytest tests/unit -q` and final `uv run pytest -q` | 95 unit tests passed. The full suite passed all 106 tests. |
| `uv run ruff check .`, `uv run ruff format --check evals tests/acceptance`, `git diff --check` | Passed. |
| `git switch -c codex/t02-1-synthetic-anchors` | Created the task branch from `29c7fee` after the user requested a commit and push. |

**Next subtask — T02.2.** Add the input-only manifest and family splits, with
`test_gold_is_not_application_input` and `test_near_duplicates_share_split`.
T02.3 owns the native fixture command and viewer check. M0 remains open.

# Historical record — T01.3 and matching-comparison planning

## Matching comparison design and plan — 2026-11-18

Reviewed the T01.3 contracts, selection/source invariants, settings, CLI and available tests on local `main`. Updated design §§5, 10, 13, 18, 20 and the T15 summary, and updated the plan's task contracts and M1/M4 gates. The design specifies three discovery policies and a separate same-hit, fixed-pool replay of the proposed signed-score and deduplication method. Plan §2.1 maps the additions to the existing implementation sequence and lists the schema 1.0 compatibility checks.

| Local verification | Outcome |
|---|---|
| `UV_CACHE_DIR=/tmp/busconfig-uv-cache uv run pytest tests/unit/test_identity_contracts.py tests/unit/test_selection_contracts.py -q` | 71 passed |
| `UV_CACHE_DIR=/tmp/busconfig-uv-cache uv run pytest tests/unit -q` | 95 passed |
| `UV_CACHE_DIR=/tmp/busconfig-uv-cache uv run ruff check .` | Passed |
| `python3 /tmp/check_busconfig_doc_links.py` and `git diff --check` | 111 local Markdown links in eight files, zero errors. Diff whitespace check passed. |

Verification covers the existing code and document links. The retrieval engines, score replay, token measurements and paired results are future deliverables. The repository currently contains unit tests only. Next subtask: **T02.1**, including independent E01/E04 variants for a missed single-row hit and a misleading positive score. The first runnable comparison is due at T09.3.

## Documentation follow-up — GitHub navigation (2026-11-18)

- Branch: `codex/t01-3-identity-contracts`; initial working tree was clean at
  `97722fc`. Kept the same branch.
- Changed files: `docs/Bus_Config_AI_Detailed_Design_EN_v3.md`,
  `docs/Bus_Config_AI_Implementation_Plan_EN_v1.md`, `docs/progress.md`.
- Converted 99 Obsidian wiki links (41 design, 58 plan) to standard Markdown
  relative file/heading links. Updated navigation guidance for GitHub.
  Link labels, heading text, business rules and implementation scope are preserved.
- `python3 /tmp/check_busconfig_doc_links.py` (temporary documentation smoke
  checker): before edits, exit 1 with 41 + 58 unsupported wiki links; after edits,
  exit 0 with 105 local Markdown links checked across all 8 tracked Markdown files
  and no missing files, heading anchors, or remaining wiki links. The checker
  excludes fenced code when indexing headings and handles duplicate anchors.
- `git diff --check`: passed. Reviewed the complete design/plan diff; changes
  are limited to link syntax and navigation guidance. No runtime tests were
  needed for this documentation-only change.
- Blockers: none. Verification is local against GitHub's documented section and
  relative-link rules; no live GitHub click-through or push was performed.
- Next implementation subtask remains **T02.1**; T01.3 stays verified.

## Last verified unit — T01.3

- Local commit: `97722fc`, titled
  `feat: freeze T01.3 identity and serialization contracts`.
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
