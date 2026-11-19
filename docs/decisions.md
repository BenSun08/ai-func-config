# Implementation decisions

## T02.2 — 2026-11-19

- Store an input manifest alongside the authored world. Its digest pins the
  file bytes. A fixture consumer supplies an order ID and receives the shared
  catalog plus that order, including its own evidence and historical state.
- Assign whole families to partitions in the offline split manifest. Keep the
  twelve previously published anchors in development. Validation and test
  require new independent families before either can support a measurement.

## T02.1 — 2026-11-18

- Keep the authored catalog and versioned orders in `synthetic/worlds/core.yaml`.
  Identify an input cell by order revision, row ID and column. This gives the
  renderer stable source addresses before native artifacts and their hashes exist.
- Keep the public development answers, evidence links, rank lists and signed
  scores in `evals/gold/anchors.json`. The offline loader uses T01 scalar ID
  and JSON contracts. Each outcome has an explicit kind so an empty draft,
  resolved exclusion and invalid submission can be assessed separately.

## T01.3 — 2026-11-17

- Schema 1.0 uses strict opaque IDs, native XLSX/DOCX locators, explicit source
  business/hash/parser versions, typed issues and the §20.2 result containers.
  Result containers are data contracts, not implementations of the future
  parsers, planner, independent validator, model adapter or persistence layer.
- Decision content is a `DecisionPayload` inside a `DecisionRevision` envelope.
  Its SHA-256 hash covers versioned canonical UTF-8 JSON, sorted object keys and
  ID-indexed records/references. Semantic sequences remain ordered. Lifecycle,
  reports, export time and the hash itself are excluded from decision content.
  A report binds the decision ID/payload hash and has an independent report hash.
- Use `FrozenMap` and tuples for nested validated values. This is the minimum
  prerequisite repair to T01.2's shallow frozen models: nested dictionaries/lists
  could otherwise change after a decision was hashed. JSON representation remains
  objects/arrays; the existing test caller now expects tuple values in Python.
  Public copy updates are revalidated, and duplicate JSON object keys are rejected.
- Source block IDs derive from schema version, document identity/content hash,
  business revision and native locator. Collisions among documents, blocks and
  assertions are rejected before lookup construction, including identical repeats.
  Cross-import detection requires the caller to supply existing records; durable
  identity registration remains a persistence responsibility.
- Keep source/model text inert. Config attributes have explicit value states and
  evidence/review metadata; evidence packets retain full rules and exceptions.
  Raw model responses, advisory comparisons, unreviewed proposals and validated
  candidate checks are separate types. Proposal records cannot claim human review.
- Initial issue severity is conservative and fixed: `METADATA_NOTE` is INFO; all
  other codes are BLOCKING. Future nonblocking policy additions require deliberate
  schema/policy changes and tests; individual callers cannot downgrade blockers.
- Canonical encoding is project-specific, not RFC 8785. It preserves exact strings
  and finite JSON numeric types; no automatic Unicode, decimal or unit guessing is
  performed during hashing. Producer-specific normalization and restricted rule/
  behavior representations are completed in their owning tasks before use.
- No interpreter/dependency, doctor, database, model client or deployment changes
  were needed. Work remains on a local branch based on T01.2, with self-review as
  requested (no delegation).

## T01.2 — 2026-11-17

- Use the design's `SelectionInput`, `Selection`, `SelectionMap`,
  `FunctionInstance` and `SourceAssertion` contracts. `SelectionRequest` implements
  the body in design §16.2, with a required nullable configuration field; this
  defines request validation only, not an HTTP endpoint or revision mutation.
- `validate_selection_rows` processes one decision revision at a time. It accepts
  a list of typed inputs or external row dictionaries, validates every row, checks
  duplicate function IDs with a set, and constructs the map only after that check.
  Pre-collapsed mappings are rejected because duplicate evidence is already lost.
  Identical repeated configurations and different revisions are still duplicates.
- IDs are strict, nonempty opaque strings without whitespace or comma-separated
  lists. They are never split, trimmed or derived from instance scope. These are
  basic scalar contracts; ID generation, source collisions and pinned-library
  ownership checks are not implemented in this subtask.
- Instances carry evidence scope and an optional catalog function reference.
  Neither input nor persisted selected-row contracts accept an instance key.
  A draft with no selection is an empty map; persisted rows require a non-null ID.
- Keep the design's four value states. `KNOWN` requires a non-null typed value;
  unresolved/inapplicable states carry no resolved value. Recursive typed values
  preserve booleans, integers, strings and structured bindings, with finite numbers.
  Raw text distinguishes absent text, observed empty text and a slash marker.
  Domain contracts do not interpret raw slash text; T03 owns that parsing rule.
- `SourceAssertion` retains source block IDs and current/historical/planned scope.
  Missing-information questions are not manufactured as evidence; a `MISSING`
  assertion can represent an observed source cell without a usable value. Source
  locators, document versions and canonical identity are completed in T01.3.
  No `DecisionRevision` or `ValidationReport` payload is introduced here; their
  separation and immutable serialization remain T01.3 work.
- Keep the verified Python baseline and dependencies unchanged. Use this progress
  record as the execution ledger and self-review locally because delegation was
  explicitly prohibited. No additional service or environment repair was needed.

## T01.1 — 2026-11-17

- Keep the existing `ai-func-config` distribution name, explicitly package
  `src/busconfig`, and register `busconfig = busconfig.cli:main`. This satisfies
  design §20 without discarding the pre-existing untracked `src/ai_func_config`
  scaffold. That scaffold is excluded from the built package and this commit.
- Restore the plan's Python 3.12 baseline from the initial 3.15 scaffold. The
  existing 3.12.1 interpreter resolved the supplied dependencies successfully;
  no dependency incompatibility or baseline exception was required.
- Read process environment only; `.env.example` is documentation, not executable
  configuration. Doctor uses an output allowlist and safe field-only errors.
  It never loads credentials into its settings object or contacts an endpoint.
- Use `disabled`, `fake`, and `http` as diagnostic model-mode values; `http` is
  the enabled endpoint mode and requires explicit URL/name settings. This names
  the modes anticipated by T10, without implementing either client now. The
  environment values are `development`, `test`, and `production`.
- Check directory writability by creating the directory if needed, writing and
  removing a temporary file. Exit `3` for operational failure, `2` for invalid
  settings, and `0` for successful local checks, following plan §5.5.
- T01.2 owns selection/value types and duplicate external-row checks; T01.3 owns
  source identity, canonical hashing and validation-report separation. T01.1
  defines no replacement domain schema and makes no domain-correctness claim.
