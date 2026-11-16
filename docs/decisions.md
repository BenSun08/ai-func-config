# Implementation decisions

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
