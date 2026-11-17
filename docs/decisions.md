# Implementation decisions

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
