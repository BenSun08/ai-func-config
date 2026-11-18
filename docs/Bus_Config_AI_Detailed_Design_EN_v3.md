# Bus Function Configuration AI System — Detailed Design

**Version:** 3.0  
**Date:** November 16, 2026 (Asia/Shanghai)  
**Status:** Detailed design based on the accepted architecture; not an implementation or a production qualification.  
**Audience:** The engineer building an independent system on a personal computer or server, using synthetic data.

**November 18 amendment.** [Candidate discovery](#105-row-and-function-discovery) defines three ways to find configurations. The [comparison protocol](#185-gates-and-experiments) also evaluates the original row-scoring proposal and specifies how to choose a default from measured results.

## Reading guide

The central correction is mandatory: **within one order configuration, each function may select at most one configuration.** This document supersedes any earlier suggestion that two alternatives belonging to the same function could be combined to satisfy that function. Several configurations may still be selected across different functions, subject to coverage, dependencies, and compatibility.

Read Sections 1–5 for the business rules and architecture, Sections 6–15 for engineering contracts, and Sections 16–21 for delivery, evaluation, deployment, and implementation work packages. Examples use invented identifiers and do not reproduce company configurations.

The table of contents uses standard Markdown links with GitHub heading anchors. If a heading changes, update its incoming links. References at the end use ordinary web links.

**Execution companion:** [Detailed implementation plan](Bus_Config_AI_Implementation_Plan_EN_v1.md) expands the T01–T16 work packages into 48 subtasks with Codex prompts, skills, environment setup, verification, and deployment instructions. Keep both files together in the repository `docs/` directory; this design remains the source of business rules.

## Contents

1. [Confirmed requirements and design decisions](#1-confirmed-requirements-and-design-decisions)
2. [First principles and the selection invariant](#2-first-principles-and-the-selection-invariant)
3. [System boundaries and success conditions](#3-system-boundaries-and-success-conditions)
4. [Architecture and component responsibilities](#4-architecture-and-component-responsibilities)
5. [End-to-end processing and state transitions](#5-end-to-end-processing-and-state-transitions)
6. [Source documents and ingestion contracts](#6-source-documents-and-ingestion-contracts)
7. [Knowledge preparation and authoring formats](#7-knowledge-preparation-and-authoring-formats)
8. [Domain model and evidence representation](#8-domain-model-and-evidence-representation)
9. [Cross-document linking and requirement construction](#9-cross-document-linking-and-requirement-construction)
10. [Retrieval and candidate comparison](#10-retrieval-and-candidate-comparison)
11. [Rules and engineering validation](#11-rules-and-engineering-validation)
12. [Single-choice selection and whole-order validation](#12-single-choice-selection-and-whole-order-validation)
13. [LLM contracts and bounded reasoning](#13-llm-contracts-and-bounded-reasoning)
14. [Persistence and transactional integrity](#14-persistence-and-transactional-integrity)
15. [Human review and change propagation](#15-human-review-and-change-propagation)
16. [API and user interface contracts](#16-api-and-user-interface-contracts)
17. [Output workbook and explanation design](#17-output-workbook-and-explanation-design)
18. [Synthetic data and independent evaluation](#18-synthetic-data-and-independent-evaluation)
19. [Deployment and operational behavior](#19-deployment-and-operational-behavior)
20. [Repository layout and module interfaces](#20-repository-layout-and-module-interfaces)
21. [Implementation plan and acceptance gates](#21-implementation-plan-and-acceptance-gates)
22. [Worked synthetic decision examples](#22-worked-synthetic-decision-examples)
23. [Superseded assumptions and remaining domain mappings](#23-superseded-assumptions-and-remaining-domain-mappings)
24. [References and glossary](#24-references-and-glossary)

## 1. Confirmed requirements and design decisions

### 1.1 Confirmed by the user

| ID | Requirement |
|---|---|
| U01 | Build an independent system on a personal computer or server; use synthetic test data because company data cannot be exported. |
| U02 | Combine the pin-definition, low-voltage control-logic, and switch-layout documents when interpreting order requirements. |
| U03 | In the pin-definition document, distinguish planned pin use, historical-order reference connections, and actual current-order connections and logic. Historical reference connections may be ignored. |
| U04 | A slash `/` in the explained source format represents a blank. |
| U05 | Useful switch information includes component name, functional logic, position count, indicator color, backlight color, rocker-switch ID, and switch type. The ID field may contain a CAN message ID or the word indicating a hardwired connection. |
| U06 | The configuration attribute table lists key properties of each configuration in the function library. |
| U07 | The experience table contains human configuration experience. |
| U08 | Output should preserve the illustrated function/configuration table and add evidence, confidence information, and understandable selection reasons. |
| U09 | The proposed catalog-led workflow with independent order-demand discovery and bidirectional checking is broadly accepted. |
| U10 | **Each function in the function library may select at most one configuration for an order.** |

### 1.2 Engineering decisions in this design

These are implementation choices, not additional statements attributed to the user:

- A configurable function is a stable library entity that owns its alternative configurations. Its identity is assigned by an explicit catalog mapping, not inferred from heading depth alone.
- The selection key is the order decision revision plus `function_id`. A physical instance is evidence scope, **not another selection slot**.
- A required, resolved function needs exactly one compatible configuration before approval. An unnecessary function has zero. Unknown and unmatched functions remain unresolved with zero selected configurations.
- Preserve human-friendly authoring sheets, normalize them into typed internal records, and retain source links.
- Use a modular Python application with a separate model endpoint. Begin with deterministic logic; add model assistance without making the model the source of engineering truth.
- Treat the source photographs as structural references. The independent project will ingest generated native XLSX and DOCX files; photo OCR is an optional future adapter, not a prerequisite.
- Use one selected configuration revision per function. Version alternatives are alternatives too: selecting two revisions of one configuration is forbidden.
- Confidence is initially an evidence grade, not a claimed probability of correctness.

## 2. First principles and the selection invariant

### 2.1 What the system decides

The system must establish what an order requires, determine which existing configurations can implement those requirements, and construct a justified order configuration. Text similarity helps locate information; it does not establish compatibility.

Five conditions govern a successful result:

1. Relevant order requirements have been captured with their source context.
2. Selected configurations satisfy the applicable interface and behavior requirements.
3. Selection cardinality is valid for every function.
4. Dependencies and interactions are consistent across the order.
5. Uncertainty, evidence, and human decisions remain traceable to immutable versions.

### 2.2 The non-negotiable cardinality rule

Let `C(f)` be the configurations owned by function `f` in the pinned library snapshot. Let `x(o,f,c)` be 1 when configuration `c` is selected for function `f` in the active decision for order `o`.

\[
\sum_{c\in C(f)} x(o,f,c) \leq 1
\]

When the function is confirmed required and the order is being approved:

\[
\sum_{c\in C(f)} x(o,f,c) = 1
\]

That second condition is an approval requirement, not permission to force a poor match. If no acceptable candidate exists, keep the draft unresolved.

| Situation | Selected configurations | Business outcome |
|---|---:|---|
| Confirmed not needed, with supporting evidence | 0 | Resolved exclusion |
| Required and one compatible choice identified | 1 | Proposed, then reviewable after global checks |
| Required but several alternatives remain indistinguishable | 0 | Choice requires review |
| Requirement or material evidence is unknown | 0 | Clarification required |
| Required but no acceptable candidate was found | 0 | Search or library-gap investigation |
| Two alternatives cover complementary parts of the same function | 0 | Existing alternatives do not jointly become a valid selection |

The model may return several ranked candidates, and the reviewer may inspect them side by side. **Candidate lists are not selected configuration lists.**

### 2.3 Instances do not bypass cardinality

If one function concerns both a front and a rear device, the application still has one selection slot for that function. A selected configuration's declared scope must support all applicable instances. If one instance requires configuration A and another requires B under the same function, report a conflict or library gap. Do not create new function IDs or separate selection slots automatically. Initial selection uses fixed configuration revisions; parameterized binding changes are outside the first release. A configuration requiring unresolved parameters cannot be silently instantiated.

Separate selections are valid only when the maintained library explicitly defines separate configurable functions. Human catalog maintenance may correct an identity mapping, but runtime matching cannot invent a split to make an infeasible order appear feasible.

### 2.4 Coverage can remain many-to-many

A configuration may cover multiple requirements. A requirement may depend on configurations from multiple **different** functions. For example, a signal-detection function and an indicator-control function may participate in the same behavior.

Coverage links therefore remain many-to-many, while selection is zero-or-one per function. A coverage claim must also account for the actual connection and composition of those different functions. Combining statements from their descriptions is not sufficient proof of combined behavior. Cross-function coverage is allowed only through a reviewed composition template that allocates obligations and defines the connection and verification contract (Section 12.6).

## 3. System boundaries and success conditions

### 3.1 In scope

- Ingest native synthetic order spreadsheets and a synthetic DOCX function library.
- Import and validate attribute definitions, configuration attributes, and experience rules.
- Build order facts and requirements independently of the candidate library.
- Link evidence across source documents and identify ambiguous or conflicting links.
- Review every catalog function for applicability without assuming every function is required.
- Retrieve candidates, compare critical differences, and propose at most one per function.
- Validate order coverage, dependencies, exclusions, resource use, and selection cardinality.
- Support human clarification, selection replacement, approval, and reproducible export.
- Evaluate against independent synthetic reference answers and manually reviewed anchor cases.

### 3.2 Out of scope for the initial implementation

Automatic ECU software generation, vehicle flashing, company-system integration, unattended production release, arbitrary hardware redesign, unrestricted natural-language theorem proving, and automatic publication of newly inferred experience rules are excluded.

A library-gap report may propose what is missing. It does not fabricate an existing configuration ID or activate a new implementation. A new configuration can enter selection only after it has been authored, reviewed, assigned a version, and included in a new knowledge snapshot.

### 3.3 Acceptance is not a single accuracy score

An order is review-ready only when required functions have one proposed choice, critical checks pass, and blocking evidence or coverage issues are absent. Approval additionally requires a recorded human decision over that exact revision. A successful processing run can instead produce an unresolved report; successful execution is not successful configuration.

The personal project can demonstrate behavior on its synthetic domain. It cannot establish company accuracy, actual company labor savings, or production vehicle safety.

## 4. Architecture and component responsibilities

Use a modular monolith: one business application, one durable worker process when background execution is needed, one PostgreSQL database, and a separate model-serving endpoint. Modules communicate through typed contracts rather than prompt strings passed between autonomous agents.

```mermaid
flowchart TD
    K["Library, attributes and rules"] --> KP["Knowledge preparation and review"]
    KP --> KS["Versioned knowledge snapshot"]
    O["Order documents and context"] --> IP["Parsing and source snapshots"]
    IP --> OF["Facts, requirements and links"]
    OF --> FT["Function-level assessment tasks"]
    KS --> FT
    FT --> EC["Evidence and candidate comparison"]
    KS --> EC
    EC --> SC["Single-choice order selection"]
    SC --> GV["Whole-order validation"]
    GV --> HR["Human review"]
    HR -->|New evidence or replacement| FT
    HR -->|Approved revision| EX["Workbook and audit export"]
```

| Component | Responsibility | Does not do |
|---|---|---|
| Source store | Original bytes, hashes, document metadata, source locations | Decide which document wins a conflict |
| Parsers | Recover structure, text, tables, revisions, and unresolved parsing issues | Infer omitted engineering requirements |
| Knowledge compiler | Catalog mapping, configuration revisions, attributes, approved rules | Turn unreviewed model output into approved knowledge |
| Order interpreter | Extract facts, requirements, source scope, and instance relationships | Adapt order facts to suit a candidate |
| Evidence resolver | Collect supporting and contradicting evidence and explain missing fields | Treat failed search as proof of absence |
| Candidate retriever | Produce a broad, traceable candidate set | Select a final configuration |
| Candidate validator | Check supported attributes, bindings, behavior, and applicability | Offset a failure with a similarity score |
| Selection planner | Choose zero or one candidate per function under cross-function constraints | Combine alternatives of the same function |
| Order validator | Validate coverage, dependencies, cardinality, side effects, and unresolved issues | Assume individual candidate checks prove global validity |
| Review service | Capture clarifications and revision-bound human decisions | Silently override failed constraints |
| Exporter | Render a particular draft or approved revision consistently | Recompute selection or interpret symbols ad hoc |
| Evaluation runner | Compare outputs with independent reference outcomes | Expose gold answers to the application |

## 5. End-to-end processing and state transitions

### 5.1 Knowledge preparation

1. Snapshot original function-library, attribute, and rule files.
2. Parse hierarchy, configuration boundaries, source versions, and relevant text.
3. Map each configuration to exactly one configurable function.
4. Extract proposed attributes and behavior representations; retain the original text.
5. Detect attribute/body disagreements, ambiguous revisions, and malformed rules.
6. Review additions and changes, then publish an immutable `KnowledgeSnapshot`.

Every order run pins one snapshot. An unfinished knowledge update cannot change an in-progress run's candidates.

### 5.2 Order processing

1. Create an `OrderSnapshot` with context and document hashes.
2. Parse all order sources and record parsing completeness.
3. Extract source assertions and behavioral requirements before candidate selection.
4. Resolve cross-table entities and preserve competing links when ambiguous.
5. Evaluate approved applicability and mandatory rules using three-valued facts.
6. Form the assessment inventory: all catalog functions plus unmapped demands.
7. Resolve function-level evidence, then retrieve and check candidate revisions.
8. Assemble a constrained proposal with at most one selected revision per function.
9. Validate the entire proposal independently of the planner.
10. Present proposed choices, exclusions, unresolved functions, and residual demands.
11. Accept human corrections as new inputs or decision revisions; rerun affected checks.
12. Approve an exact eligible revision and generate an export from that revision.

The function-led path is the initial operating default. An optional row search can supply leads for uncertain function mappings, ambiguous links and residual demands at steps 6–7. A lead may identify documents or configurations worth checking. Confirming an entity link still requires the order-side evidence from §9.

### 5.3 Separate execution from business state

| State dimension | Values |
|---|---|
| Run execution | `QUEUED`, `RUNNING`, `WAITING_REVIEW`, `SUCCEEDED`, `FAILED`, `CANCELLED` |
| Function demand | `REQUIRED`, `NOT_REQUIRED`, `UNDETERMINED` |
| Candidate check | `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE` |
| Function resolution | `PROPOSED`, `EXCLUDED`, `NEEDS_EVIDENCE`, `AMBIGUOUS_CHOICE`, `CONFLICT`, `NO_MATCH_FOUND`, `LIBRARY_GAP_CONFIRMED` |
| Decision revision | `DRAFT`, `REVIEW_READY`, `APPROVED`, `SUPERSEDED` |

`NOT_APPLICABLE` is allowed only when an explicit applicability predicate is false. A missing value produces `UNKNOWN`, not `NOT_APPLICABLE`.

An `UNDETERMINED` function remains unresolved with no selected configuration. A `NOT_REQUIRED` function needs a reason, such as explicit exclusion or a confirmed false applicability condition. Absence of a keyword alone is insufficient.

### 5.4 Approval and blocking issues

Approval requires a complete assessment inventory; one selected configuration for each required function; zero for excluded functions; no unresolved demands; no critical unknown or failed check; and a validation report whose hash matches the exact decision payload.

Benign metadata issues can remain informational. Each issue type has a fixed severity policy. Neither the model nor an individual UI action may downgrade a blocking issue silently. A reviewer resolves the evidence or proposes a reviewed rule/configuration correction, then validation runs again.

## 6. Source documents and ingestion contracts

### 6.1 Native formats first

Support XLSX and DOCX for the first implementation. Generate representative synthetic files with merged cells, multiline logic, nonuniform header rows, and revision annotations. A later image/PDF adapter must expose uncertain OCR fields and image-region provenance; it must not pretend to have native cell references.

Every imported file has a declared document role, business revision, content hash, parser version, and layout profile. Do not identify a role from its filename alone. Wrong or ambiguous headers produce an import issue and a mapping preview.

### 6.2 Pin-definition source

| Source field group | Internal interpretation |
|---|---|
| Controller and pin identity | Controller instance, hardware revision if supplied, connector and pin |
| Planned or expected use | `PLANNED_USE`; a design intention, not proof of current wiring |
| Historical order connections | `HISTORICAL_REFERENCE`; stored for provenance, excluded from current-order fact resolution by default |
| Current order port definition and connected product | `CURRENT_ORDER`; current wiring and endpoint assertions |
| Current order connector/pin details | Endpoint binding assertions, with explicit controller/side/role |
| Logic description | Current-order behavioral clauses requiring linkage to the corresponding function and endpoint |

A row can describe several endpoint connections or several behaviors. Preserve the row as a source unit and produce separately linked assertions where needed. Never select a configuration because one pin token matches while the actual connected product is unrelated.

### 6.3 Low-voltage control logic

Preserve function item, full logical description, change indicator, and any explicit baseline reference. Split logical clauses only after preserving their enclosing conditions and scope. A parent condition such as “when powered on” applies to its nested actions; sentence splitting must not detach it.

“No change” is metadata, not automatically missing content. If the row contains a complete current description, use that description with its provenance. If it explicitly relies on a baseline instead, resolve a named baseline revision; otherwise raise `BASELINE_MISSING`. Do not infer a baseline merely from similar order identifiers.

### 6.4 Switch-layout source

Preserve component name, functional logic, physical position count, indicator color, backlight color, connection field, and switch type. Other observed columns can be stored as extra source metadata without inventing decision relevance.

Normalize the connection field into `connection_mode = HARDWIRED | CAN | UNKNOWN` and a separate communication identifier when supplied. Preserve the raw original field. A CAN message ID alone is not a full signal definition: bus/network, frame format, signal field, and decoding may be needed for a particular check. Missing details remain missing.

Keep `physical_position_count`, `mechanical_behavior` (momentary/latching), and `controlled_state_sequence` separate. A momentary switch with two physical positions can control a sequence with more than two functional states.

### 6.5 XLSX handling rules

- Detect header bands through the declared layout profile; preview uncertain mappings.
- Expand merged headers for interpretation while keeping original merged ranges as provenance.
- Carry a function label down only within a validated merged/grouped region. Do not forward-fill arbitrary blanks.
- Preserve multiline cells and deliberate whitespace in the raw representation.
- Preserve hidden rows and their hidden status; do not silently discard them. The import profile determines whether they are current, reference, or unresolved.
- Retain both formulas and available cached values. A cache is not evidence of recalculation. Relevant absent or stale caches require supplied values or review.
- Preserve rich-text deletion marks and other relevant formatting when the source profile uses them; unsupported semantics produce an issue.
- Parse only the entire standalone token `/` as the specified blank marker. Strings such as `0/1/2/3` remain actual values.
- Normalize units with an explicit conversion registry; keep the original value and unit.
- Export untrusted source strings as text to prevent spreadsheet formula interpretation.

The `openpyxl` documentation distinguishes formula text from stored cached values and exposes rich-text preservation as an option [R03]. These are parser implementation concerns, not permissions to accept cached or styled content without source semantics.

### 6.6 DOCX function-library handling

Read headings, paragraphs, tables, nested content where supported, notes, and revision metadata in document order. Configuration ownership comes from the catalog mapping. A table continued across pages must remain part of its configuration; page boundaries are presentation boundaries.

Each source profile declares how effective content is determined. For documents with tracked changes, preserve accepted/current versus deleted/superseded content explicitly. If the effective revision cannot be established, do not publish that configuration into approved knowledge. Color alone does not establish revision status.

Use heading path, paragraph/block index, table/cell coordinates, text span, and document hash for native provenance. Rendered page numbers may be attached as a convenience, but must not be the sole identifier because pagination depends on rendering. Ordinary `python-docx` paragraph/table lists omit some content inside revision marks; the adapter must inspect relevant OOXML or reject unsupported revision constructs visibly [R04].

### 6.7 Parse completion contract

`ParseResult` contains `source_blocks`, `assertions`, `issues`, and a `completeness` record. Completeness records supported/unsupported regions, mapped/unmapped columns, and whether mandatory sections were found. A parser that merely returned some rows has not necessarily completed the import.

## 7. Knowledge preparation and authoring formats

### 7.1 Keep practical authoring views

Engineers may continue to use per-function wide tables. A normalized representation is the exchange and storage contract, not a demand that engineers manually write database records. A template importer maps each function's named columns to a versioned attribute dictionary.

Generic columns such as “Attribute 1” require a local header mapping. Their meaning must never carry over from the preceding function by accident.

Recommended authoring workbook sheets:

| Sheet | Key fields |
|---|---|
| `Functions` | Function ID, name, category path, configurable flag, aliases, scope |
| `Configurations` | Configuration ID, owning function ID, revision, lifecycle, source reference |
| `AttributeDefinitions` | Attribute code, type, unit, domain, applicability, comparison operator, decision role |
| `ConfigAttributes` | Configuration revision ID, attribute code, typed value, value state, evidence, review status |
| `EvidenceHints` | Function/attribute, preferred source roles, field aliases, required scope |
| `Rules` | Rule ID, revision, type, scope, predicate, effect, exceptions, basis, review status |
| `Compositions` | Template ID/revision, requirement pattern, participating functions, obligation allocation, connections, verification basis |

### 7.2 Configuration ownership and versions

Each configuration belongs to exactly one configurable function. Category headings are not selectable. A configurable function can appear at different depths in different documents; identifiers such as `1.1` and `4.1` are display references, not inherently permanent identities.

`ConfigRevision` is immutable and contains an effective lifecycle, compatibility scope, full relevant behavior, attribute facts, bindings, and dependencies. A knowledge release explicitly lists its eligible revisions. Older applicable revisions may be included deliberately; “latest date” is not a universal compatibility rule.

Attribute extraction produces a draft revision. Knowledge review checks its correspondence to the source. A change to source behavior invalidates derived attributes until they are revalidated. There is one authoritative representation per released fact, with traceable alternatives during conflict resolution.

### 7.3 Attribute definition contract

| Field | Meaning |
|---|---|
| `attribute_code` | Stable identifier such as `switch.mechanical_behavior` |
| `value_type` | Boolean, integer, decimal, enum, string identifier, ordered sequence, set, binding list, or behavior reference |
| `unit` | Explicit unit for numeric values, or null |
| `applicability_predicate` | Approved predicate defining when the attribute matters |
| `comparison_operator` | `EQ`, `SET_CONTAINS`, `SET_EQUALS`, `RANGE_WITHIN`, `SEQUENCE_EQUALS`, or supported behavior check |
| `decision_role` | `REQUIRED_CONDITION`, `PREFERENCE`, or `DISPLAY_ONLY` |
| `order_evidence_hints` | Where to look for the order's required value |
| `definition_evidence` | Why the candidate's own value is believed correct |
| `missing_policy` | Required comparison with missing evidence returns unknown |

Do not treat all attributes as equal-weight scoring features. A confirmed required-condition failure rejects eligibility regardless of preferences. Colors may be display-only for one function and decision-relevant for another.

Binding sets must retain signal roles and associations. For example, two sensors wired to two pins must not become two independent unordered lists that lose which sensor uses which pin.

### 7.4 Experience-rule contract

Every rule has `rule_id`, `revision`, `rule_type`, `scope`, `condition`, `effect`, `exceptions`, `basis`, `owner`, `review_state`, and `effective_range`.

| Rule type | Effect |
|---|---|
| `REQUIRE_FUNCTION` | Create a derived demand for a function when the condition is true |
| `FORBID_CONFIG` | Mark a candidate incompatible when the condition is true |
| `REQUIRE_DEPENDENCY` | Require a different function and, optionally, an allowed set of its configurations |
| `EXCLUDE_PAIR` | Prohibit a pair of choices across functions |
| `PREFER_CONFIG` | Rank already eligible choices; cannot bypass failures or unknowns |
| `EVIDENCE_HINT` | Guide source lookup; provides no engineering proof |
| `INFORMATIONAL` | Preserve experience that is not executable |

A requirement for a function is different from a requirement for a particular configuration. A same-function dependency on a second alternative is invalid knowledge; flag `RULE_CARDINALITY_CONFLICT` during compilation.

Rule conditions use a restricted typed expression tree: `all`, `any`, `not`, `eq`, `in`, and approved numeric comparisons over registered fact paths. Effects are enumerated actions, not Python or SQL strings. No execution of free-form text is permitted.

An illustrative rule might say: if an invented order option `boarding_assist` is explicitly true, require function `DEMO-F-STOP-REQUEST`. Its basis must identify the reviewed synthetic policy. Unknown option values produce an unresolved applicability question; they do not silently evaluate as false.

Rules with contradictory hard effects do not resolve through arbitrary priority or last-write-wins. An explicit, reviewed exception relationship may resolve them; otherwise emit a conflict. Soft preferences run only after hard conditions pass. Repeated dependency expansion uses a visited set; a cycle is checked for consistency rather than allowed to loop forever.

### 7.5 Knowledge release gate

Publication checks ownership, IDs, source versions, approved rule status, supported operators, attribute types, invalid same-function dependencies, missing critical definitions, and known contradictory statements. A release may contain configurations with explicit unsupported behaviors, but those candidates cannot pass checks requiring unsupported verification automatically.

## 8. Domain model and evidence representation

### 8.1 Principal objects

| Object | Essential fields and relationships |
|---|---|
| `SourceDocument` | ID, role, business revision, byte hash, original path, layout profile |
| `SourceBlock` | Document ID, structural location, raw text, formatting/effective-status metadata |
| `SourceAssertion` | Subject, property, typed value, value state, source block IDs, statement scope |
| `ResolvedFact` | Subject/property, resolved value or conflict, contributing assertions, resolution method and review |
| `Requirement` | Order snapshot, enclosing scope, condition/action/timing, source assertions, extraction status |
| `Function` | Stable ID, category, aliases, configurable flag |
| `FunctionInstance` | Device/functional scope used for evidence; references its catalog function when mapped |
| `SignalBinding` | Signal role, source/target identity, controller/network, interface, polarity, source evidence |
| `ConfigRevision` | Configuration ID, owning function ID, revision, behavior, attributes, applicability |
| `RuleRevision` | Reviewed predicate/effect, scope, exceptions, evidence and version |
| `CompositionTemplate` | Reviewed requirement pattern, obligation allocation, different participating function IDs, connections and verification procedure |
| `KnowledgeSnapshot` | Exact catalog, config, attribute, rule and composition-template revision membership |
| `FunctionAssessment` | Function, demand state, candidate IDs, unresolved questions, preferred candidate or null |
| `CandidateCheck` | Candidate, requirement/attribute, outcome, comparator, evidence, counterexample |
| `Selection` | Decision revision, function ID, one configuration revision ID |
| `CoverageLink` | Requirement/clause, selected config revision, covered behavior, verification method and result |
| `DecisionRevision` | Immutable payload: order/knowledge snapshots, input generation, selections, assessments, issues and parent revision; separate payload hash |
| `ValidationReport` | Append-only report referencing a decision payload hash, validator version and verification evidence; separate report hash |
| `ReviewEvent` | Reviewer, action, reason, evidence changes, base and resulting revision |
| `Approval` | Decision revision, payload hash, validation hash, reviewer, timestamp |
| `Run` / `Attempt` | Execution status, pinned inputs, stage, attempt identity, model settings and errors |

### 8.2 Value state is explicit

Use `KNOWN`, `MISSING`, `NOT_APPLICABLE`, and `CONFLICT` for facts. `KNOWN(false)` and `KNOWN(0)` are real values. A default, inherited fact, extracted assertion, and human-confirmed assertion are distinguished through origin and review metadata rather than overloaded into null values.

An example evidence envelope:

```json
{
  "evidence_id": "EV-DEMO-001",
  "document_id": "DOC-DEMO-PINS-R1",
  "document_hash": "sha256:example-only",
  "location": {"sheet": "Pins", "cells": ["G12", "H12", "K12"]},
  "statement_scope": "CURRENT_ORDER",
  "subject_id": "DEVICE-DEMO-REAR-LAMP",
  "property": "output_binding",
  "value_state": "KNOWN",
  "value": {"controller": "CTRL-S1", "connector": "A", "pin": "7"},
  "raw_text": "Synthetic rear lamp connection",
  "origin": "NATIVE_DOCUMENT",
  "review_state": "UNREVIEWED"
}
```

This is a shape example, not a valid released record: the placeholder hash must be replaced with a computed hash in a real run.

### 8.3 Evidence roles and independence

Each comparison references evidence as `SUPPORTS`, `CONTRADICTS`, or `CONTEXT`. Missing information is represented by a question or completeness issue, not a fabricated evidence record.

Three documents repeating a copied sentence are not automatically three independent confirmations. Group duplicate/derived assertions by provenance lineage and do not increase confidence merely by counting repetitions.

### 8.4 Identity and version boundaries

Pin identity includes controller instance, connector, pin, and hardware revision when material. Communication identity includes bus/network, frame identity and format, plus signal definition when required. Device names are aliases, not unique identifiers.

Order facts are scoped to an `OrderSnapshot`. A row number is a source location, not a permanent function identity. Store both stable business IDs and source locations. Every decision pins a knowledge snapshot and order snapshot so it can be reproduced without reading later edits.

## 9. Cross-document linking and requirement construction

### 9.1 Link entities before combining behavior

Try exact supplied identifiers first, then reviewed aliases scoped by function and device, then structural matches using current-order endpoints and signal roles. Model-assisted linking proposes candidates only when deterministic links are insufficient.

A link record contains both entities, relationship type, evidence IDs, method, and review state. Multiple plausible links produce `AMBIGUOUS_JOIN`. Do not take the first name match or assume that equal pin strings on different controllers identify the same signal.

Current-order actual endpoints have a different semantic role from planned-use labels. An apparent disagreement is not resolved by averaging them: it may be a real planning-versus-wiring difference requiring review.

### 9.2 Source conflict handling

There is no global “pin table always wins” or “longest description wins” rule. Apply only reviewed field-specific authority or explicit supersession relationships. Record the selected interpretation and rejected/superseded assertion when such a relationship exists. Otherwise retain `CONFLICT` and block affected decisions.

Keep orders and their baselines separate. Inheritance requires a linked baseline revision and an explicit change/inheritance policy. A historical reference column is not automatically an inherited baseline.

### 9.3 Independent requirement discovery

Scan all relevant current-order logic cells and descriptions before consulting candidate behavior. Classify each source clause as a requirement, factual assertion, reference, explicit exclusion, or unresolved content. Track a ledger from each relevant source block to its extracted clauses or justified exclusion.

The deterministic M1 interpreter supports a registered, versioned set of controlled English/Chinese templates used by the synthetic renderer. The initial patterns cover explicit function required/absent declarations, typed property assignments, baseline-reference statements, Boolean trigger/action clauses, and delay/reset clauses. One canonical form is `WHEN <predicate> THEN SET <output> = <value> [AFTER <number> <unit>] [RESET WHEN <predicate>]`. Predicates allow `ALL`, `ANY`, `NOT`, registered signal names and explicit values, with parentheses defining nesting. Equivalent Chinese surface forms are registered templates, not assumed translations. The registry owns the exact accepted forms and their test fixtures; it contains no answer IDs or selected-configuration hints.

Unrecognized prose stays in the ledger as `UNPARSED_REQUIREMENT`; it cannot be discarded or guessed by the deterministic baseline. M2 adds model-proposed extraction and link alternatives through separate interfaces. Those proposals retain source spans and need the corroboration/review required in Section 11 before they support critical passes. Extraction receives order sources and context, not candidate descriptions, preserving independent demand discovery.

The ledger is a completeness aid, not proof that the extraction is correct. Independent anchor tests must include clauses deliberately missed by the primary extractor.

Requirements can remain unmapped to a catalog function. They appear in the residual-demand queue and prevent a falsely complete order. Do not suppress a requirement just because its vocabulary is absent from the library.

### 9.4 Function assessment inventory

Create one assessment per configurable function in the pinned catalog. Evaluate applicability using order facts and approved rules; expensive model calls are not needed for every clearly excluded function. Append residual demands that do not map to any catalog function.

For relevant functions, group all applicable physical instances under the same assessment. Construct one order evidence context with instance-scoped facts and requirements. A configuration must satisfy all obligations allocated to that function across the assessment's complete instance scope, not merely its easiest instance. Shared requirements use the reviewed allocation in Section 12.6; an individual candidate is not required to implement another function's allocated obligations.

Before selection search, expand a **potential dependency frontier** from every retained candidate's declared dependencies and applicable composition templates. For each newly reachable function, collect evidence and assess its eligible configurations; repeat to a fixed point over the finite pinned catalog. This is preparation, not a declaration that all reachable functions are required. A configurable per-run preparation limit defaults to 500 functions; exhaustion creates `PREPARATION_LIMIT_REACHED` and blocks a completeness claim. Actual required functions and derived obligations are recomputed from root demands within each tentative selection branch. Only the branch's active dependencies justify final selections. If a critical candidate condition can only be evaluated after choices are known, preserve it as a branch-checkable guard; evidence-missing conditions remain unknown.

### 9.5 Clarifications have engineering targets

Ask a concrete question linked to the blocked decision: for example, “Is the switch momentary or latching?” Include conflicting source excerpts when applicable. Human answers become reviewed assertions with their own IDs and timestamp; they do not overwrite original evidence. New answers invalidate affected facts, candidate checks, selection, and approval eligibility.

## 10. Retrieval and candidate comparison

### 10.1 Two retrieval tasks

**Evidence retrieval** searches order documents for the facts needed to assess a function. It uses function/device identities, reviewed aliases, current endpoints, signal roles, and source hints. It must return contrary evidence and missing-field notices as well as supportive excerpts.

**Candidate retrieval** searches the pinned configuration knowledge. Its unit is a complete configuration revision. If an index retrieves a paragraph, fetch the owning configuration's applicable conditions, exceptions, timing, and revision context before comparison.

Use distinct result types, indexes, and metrics for these tasks. A candidate-recall improvement does not establish that evidence retrieval is complete.

### 10.2 Retrieval sequence

1. Resolve candidate function identity with exact IDs or scoped aliases where possible.
2. For a known function, enumerate all eligible published revisions in that function's snapshot membership. Avoid arbitrary Top-K truncation within a small function family.
3. Apply only established hard incompatibilities, preserving rejected candidates and reasons.
4. Retain candidates affected by missing or provisional facts as unresolved candidates.
5. When function mapping is uncertain, use lexical search across function names, aliases, attributes, and full descriptions. Retain competing function mappings rather than declaring one solely from rank.
6. Add hybrid semantic retrieval only if controlled evaluation demonstrates recall gains.
7. When no match is found, broaden the search once within the defined scope and produce a search report.

Set initial cross-function exploratory retrieval to 20 candidate configuration revisions, with a second pass of up to 100 if the first pass yields no valid mapping. These are engineering resource defaults, not proofs of exhaustiveness. If the snapshot is larger and neither pass is exhaustive, the outcome remains `NO_MATCH_FOUND`, not a confirmed gap. Once the function is resolved, inspect the complete family.

### 10.3 Evidence context and finalized packet contracts

Use three sequential data stages to avoid a circular dependency:

1. `OrderEvidenceContext`: pinned order and knowledge IDs, function/instance scope, allocated requirements, facts, links, raw source excerpts and unanswered questions; no candidate comparison is required to construct it.
2. `CandidateSet` plus `CandidateAssessment` records: retrieval consumes that context and returns complete candidate definitions with search metadata; deterministic checking consumes the same context and each candidate.
3. `EvidencePacket`: the context enriched with retrieved definitions, deterministic checks, relevant rules and composition obligations. This finalized packet is supplied to the model comparison stage and reviewer.

An `EvidencePacket` includes order/knowledge snapshot IDs; function and instance scope; original requirements and reviewed normalization; resolved facts and unresolved alternatives; current-order bindings; full relevant candidate behavior; applicable rule revisions; deterministic checks; source references; and a list of questions still unanswered.

Keep a packet focused on one function assessment and its relevant dependencies. Do not place the entire function library or unrelated order documents into every model request. Do not clip away exceptions to fit a context budget. If the full relevant packet is too large, perform clause-level extraction with explicit linkage, or mark the comparison incomplete.

### 10.4 Difference matrix

Produce a matrix of candidates versus required attributes and behavior clauses. Each cell records outcome, compared values, source evidence, and comparator version. The matrix supports both deterministic selection and human review.

Ranking is lexicographic: eligibility and evidence sufficiency first; approved preferences second; lexical/semantic relevance only as a presentation aid. There is no weighted score that lets enough matches compensate for a failed necessary condition.

If multiple candidates pass locally, retain all of them for global planning. Dependencies, resource constraints, and cross-function behavior may resolve that local ambiguity. Only after global feasibility and approved preferences have been considered does an unresolved tie become final `AMBIGUOUS_CHOICE`, with no choice for the ambiguous function in a review draft. A stable display order is allowed, but it must not be mistaken for a justified winner. Partial consensus choices must be revalidated as a draft; they are not assumed to form a complete feasible plan.

### 10.5 Row and function discovery

~~~mermaid
flowchart LR
    O["Order blocks with source scope"] --> R["Row queries"]
    O --> F["Function assessments"]
    F --> H["Extra row queries for unresolved cases"]
    R --> L["Candidate leads with provenance"]
    F --> L
    H --> L
    L --> C["Resolve mapping and complete known families"]
    C --> V["Check candidates and validate the whole order"]
    R -. "Replay saved hits offline" .-> S["Signed scores and deduplicated shortlist"]
~~~

Treat a spreadsheet row as a search unit. A pin row can contain both historical and current connections, and a logic row can contain several clauses under one parent condition. Carry the table role, header, instance, enclosing condition, source cells/spans and statement scope into each query. Preserve a disposition for every substantive row, including rows without hits. Several rows can support one requirement, and a single row can support several. Keep competing device identities visible throughout retrieval.

| Discovery policy | Where candidates come from | What to inspect |
|---|---|---|
| `function` (initial default) | Use the §9 inventory and §10.2 sequence. Collect order evidence per function, enumerate known families and search lexically when the mapping is uncertain. | A family member can qualify through several conditions together even if it ranks poorly for each separate row. |
| `row` (order-led comparison) | Query the pinned library for each substantive current-order row or scoped clause. Use the same indexed configuration definitions, aliases and attribute dictionary. Group hits by owning function and configuration revision. | Record retrieved revisions before family expansion, ties, zero-hit rows and limits. A top-K cutoff can omit the only acceptable candidate. |
| `hybrid` (optional) | Run the function path. Add row queries only for unresolved mappings, competing links or residual demands. Union their leads and apply the same evidence checks. | Record the trigger, newly discovered revisions or mappings, and additional work. A retrieval hit alone cannot resolve an ambiguous join. |

All three policies can feed the same operational checks. Once a function mapping is established, complete its eligible family, prepare reachable dependencies, run the candidate checks, plan and independently validate the order. Keep the full inventory and residual demands visible for all policies. Measure both the **raw discovery** and the **post-expansion** candidate sets. Two policies can reach the same final choice while differing in evidence recovered, number of candidates examined or cost. Keep a truncated or unverified mapping unresolved.

**Row hit records.** T07 records the order and knowledge snapshot IDs, source block and span, statement and instance scope, candidate owner and revision, matched attribute or clause, retrieval method/version, rank and signed score contributions. Keep links to copied-source lineage and the scoring policy version. Load a candidate definition once per pinned revision. Retain all distinct hit-to-source links, including contrary observations. Duplicate copies from one lineage contribute once per distinct attribute observation. A query with no hit still appears in the search trace. Row order and repeated execution must give the same ranked output under a fixed policy and budget.

**Scoring baseline.** For the first offline comparison, count an exact, typed match on a comparable decision attribute as +1 and a confirmed mismatch as −1. Missing, conflicting, inapplicable and display-only fields contribute zero with their reason recorded. Preserve known false and zero as comparable values. Sum deduplicated contributions per configuration revision, then group by function. A deterministic revision ID tie-break only orders the display. Freeze the retrieval limit, comparator, weights, tie handling and minimum proposal score before evaluation. Operational candidate checks continue to distinguish hard conditions from approved preferences as specified in §10.4.

For example, one synthetic option matches the switch type, binding and color preference but fails a mandatory reset. Its score is +2. Include an order where this is the unique highest score and every option fails a necessary condition. The score-only replay must expose the tempting choice, and the checked path must return an unresolved function with the failed condition. This case distinguishes the two decision policies even when candidate recall is identical.

## 11. Rules and engineering validation

### 11.1 Evidence and logic readiness

A fact extracted by a model is not automatically verified. Exact native fields may be accepted under a tested parser contract. Model-derived identity, Boolean structure, or timing that materially affects a decision needs deterministic corroboration or explicit review before it can support a passing critical check.

Each check records its method: `EXACT_FIELD`, `APPROVED_RULE`, `TRUTH_TABLE`, `EVENT_TRACE`, `MANUAL_REVIEW`, or `MODEL_COMPARISON`. The last method alone cannot establish a critical engineering pass. This boundary makes automation coverage measurable rather than hidden.

### 11.2 Check categories

| Category | Examples |
|---|---|
| Knowledge integrity | Candidate belongs to function and pinned snapshot; revision is eligible |
| Applicability | Platform/hardware/option conditions supported by current facts |
| Interface identity | Correct controller, endpoint product, signal role, direction and binding |
| Electrical/interface behavior | Polarity, input mode, communication versus hardwire |
| Switch behavior | Momentary/latching, physical positions, controlled sequence |
| Functional behavior | Trigger, condition, action, inhibition, reset, extra behavior |
| Temporal behavior | Delay, tolerance, timeout, edge/level semantics, latching |
| Order composition | Dependencies, exclusions, resource ownership, coverage |
| Selection integrity | At most one configuration per function; required functions exactly one at approval |

Missing conditions produce unknown. A verified hard contradiction produces fail. A passing check applies only to its declared scope, not to all behavior of the configuration.

### 11.3 Restricted behavior representation

Represent supported behavior as typed conditions and transitions. The initial domain supports Boolean predicates, enumerated mode values, comparisons to explicit thresholds, output assignment, edge triggers, simple timers, resets, and declared valid-input constraints.

Keep the source clause and its formalization together. Unsupported arithmetic, complex protocols, unspecified timing, or ambiguous priority produce a review requirement rather than a guessed AST.

For Boolean combinational cases, enumerate valid input combinations and compare required/forbidden outputs. Default domain limit: 12 Boolean inputs per local check, or 4,096 combinations before domain restrictions. Larger cases require an explicit alternative checker or manual verification; do not label a truncated enumeration exhaustive.

For stateful cases, use timestamped event traces: input changes, timer expiry, output changes, and reset events. Test boundaries immediately before, at, and after a specified threshold, with tolerance represented explicitly. A trace suite demonstrates behavior on those traces; it is not an exhaustive proof of an arbitrary state machine.

### 11.4 Required versus unspecified behavior

Each formal requirement has a comparison mode:

- `EXACT_WITHIN_DOMAIN`: match all defined outputs under the declared valid domain.
- `SATISFY_SPECIFIED_CONDITIONS`: enforce specified required and prohibited behaviors; unspecified behavior remains explicitly unassessed.

Do not assume every extra behavior is acceptable, and do not reject every unspecified behavior automatically. Material extra behavior affecting shared outputs or safety-related interactions is surfaced for review. A function is fully resolved only when the required verification scope has been met.

### 11.5 Three-valued rule evaluation

Evaluate conditions over true, false, and unknown. For `all`, a known false is false; otherwise an unknown operand makes the result unknown. For `any`, a known true is true; otherwise an unknown operand makes it unknown. `not unknown` is unknown.

Conflicting facts contribute an unknown value to expression evaluation and also produce a separate conflict issue. A false sibling must not erase that issue. Scope rules determine whether the conflict blocks the particular decision.

Dependency expansion is conditional on the proposed selection. Replacing or removing the parent configuration removes its derived demands unless another active rule or explicit requirement still supports them. Recompute from root requirements rather than accumulating stale derived requirements.

## 12. Single-choice selection and whole-order validation

### 12.1 Candidate assessment is not selection

Store all candidate checks separately. A `FunctionAssessment` may expose many candidates but only one `preferred_config_revision_id` or null. An authoritative `Selection` row exists only for a chosen configuration, never for every candidate with a good score.

When unresolved evidence or final global choice ambiguity blocks a function, the review proposal selects none for it and reports the reason. Local ambiguity does not remove candidates from global search. Draft exports may show the partial order explicitly as incomplete. They cannot be approved or mislabeled as complete.

### 12.2 Feasibility before preference

The planner must find a set satisfying all hard constraints; it must not greedily choose each function's top-ranked candidate and assume the union works. A preference can be sacrificed to make the order feasible; a hard condition cannot.

For the initial implementation, use deterministic backtracking with pruning over required functions and eligible candidate sets. Explore functions with the fewest eligible candidates first. After each tentative choice, expand dependencies and prune known exclusions/resource conflicts. Keep optional candidates unselected unless an explicit/derived demand justifies selection.

Initial resource defaults are 10,000 explored search nodes or 30 seconds, whichever comes first. Record the explored scope. On exhaustion, emit `SEARCH_LIMIT_REACHED`; do not report a proven infeasible order or a confirmed library gap. Keep any feasible proposal found, but label preference optimality unproven if optimization was incomplete. If exhaustive search finds several equally justified plans, require a human choice rather than claiming a unique engineering answer.

The planner consumes the precomputed potential-dependency closure, including branch-checkable guards and obligation allocations. It never makes model calls during search. An unprepared reachable function or missing assessment context is a preparation issue, not an absent dependency. A branch evaluates guards and its active requirements, then checks that its single selected alternative for each function covers all currently allocated obligations. Assessments may be cached by obligation/context hash, never solely by configuration ID.

### 12.3 Planner output

`SelectionPlan` contains selections keyed by function ID, function assessments, coverage claims, active derived requirements, dependency edges, issues, and search-completeness metadata. It contains a scalar configuration revision per function, not a list.

The independent validator must reconstruct the checks from the proposed selections. It must not trust the planner's “valid” flag or copied coverage booleans.

### 12.4 Whole-order validation

Validate in this order:

1. IDs, configuration ownership, snapshot membership, and duplicate function selections.
2. Demand resolution and required/excluded cardinality.
3. Candidate eligibility for every selected configuration.
4. Conditional dependency closure and cross-function exclusions.
5. Exclusive resources, declared arbitration, and shared-input permissions.
6. Required behavior coverage and interaction assumptions.
7. Justification for every selected configuration and material extra behavior.
8. Residual unmapped requirements, unresolved source conflicts, and unsupported checks.

An input shared by several functions is not automatically a conflict. Two outputs using a common physical resource require a declared compatible ownership/arbitration policy; a shared pin token alone cannot establish compatibility.

### 12.5 Why no candidate is different from a library gap

`NO_MATCH_FOUND` is a search outcome. `LIBRARY_GAP_CONFIRMED` requires resolved material requirements, a validated function mapping or reviewed new-function conclusion, completed search of the relevant pinned library scope, and human confirmation that no current configuration satisfies the requirement. Incomplete materials, parsing failures, and search limits cannot establish a gap.

If the only apparent solution uses two alternatives of one function, report `SAME_FUNCTION_COMPOSITION_FORBIDDEN`. The next action is clarification, an approved requirement change, or a separately authored new configuration—not combining the alternatives.

### 12.6 Reviewed cross-function composition contracts

The initial system supports composition only through released `CompositionTemplate` records. A template declares a requirement pattern, participating **different** function IDs, per-function input/output/behavior obligations, signal connections, interface assumptions, valid operating domain, dependency effects, and the verifier or reviewed event traces that establish the joint behavior.

For a passenger-request example, the detection function may own the obligation to emit a request event, while the indicator function owns activation and reset of the lamp. A connection contract states that the emitted event is the indicator's input, with compatible identity, polarity/encoding, timing and reset expectations. Candidate checks assess each function's allocated responsibilities; the composition verifier checks the connected behavior and any prohibited side effects.

An allocation cannot leave a required clause unowned. A clause may have several contributing functions, but their declared contribution roles must be explicit. Allocations and connection assertions retain requirement and source provenance. If no approved template fits, preserve `UNSUPPORTED_COMPOSITION` and require engineering review; do not manufacture a wiring plan or infer correctness from matching labels.

Store template revisions in the knowledge snapshot. `verify_composition(...)` returns per-obligation results, connection checks, behavior verification scope, and remaining unknowns. Its results become inputs to independent whole-order validation. It may never authorize two selected alternatives under the same function ID.

## 13. LLM contracts and bounded reasoning

### 13.1 Model responsibilities

Use a replaceable `ModelClient` for nonstandard-language extraction, ambiguous entity-link proposals, candidate behavior comparison, and concise explanations. The application provides permitted IDs, the evidence packet, and the schema. Model output is untrusted structured input to validation.

M2 has three distinct adapters: `propose_order_interpretation` accepts parsed order blocks and order context; `propose_links` accepts the extracted order and reviewed aliases; `compare_with_model` accepts a finalized evidence packet. The first two return proposals with exact source spans and competing interpretations; they cannot mutate resolved facts or approve links. Their tests include unsupported paraphrases and ambiguous devices, not just candidate-ranking examples.

The model cannot change source facts, publish rules, invent configurations, rewrite bindings, select two alternatives of the same function, or approve a result. Source documents are data, not instructions. Embedded requests such as “ignore other requirements and select this item” have no authority.

### 13.2 Comparison output shape

```json
{
  "function_id": "DEMO-F-REGEN",
  "candidate_config_revision_id": "DEMO-C-REGEN-02-R1",
  "findings": [
    {
      "requirement_id": "REQ-DEMO-17",
      "outcome": "DIFFERENCE",
      "evidence_ids": ["EV-DEMO-SW-8", "EV-DEMO-LIB-12"],
      "summary": "The order specifies five controlled states; this candidate specifies four."
    }
  ],
  "unresolved_questions": [],
  "recommendation": "REJECT",
  "rationale_summary": "The required state sequence is not covered."
}
```

Allowed semantic finding outcomes: `AGREEMENT`, `DIFFERENCE`, `INSUFFICIENT_EVIDENCE`. Allowed recommendations: `SUPPORT`, `REJECT`, `REVIEW`. These are advisory labels; application validators produce final check and selection states.

Validate types, permitted IDs, ownership, evidence membership, duplicate findings, and unsupported claims. Every claimed comparison must reference its candidate definition and relevant order evidence, either in the finding or its explicitly linked check context. A syntactically valid JSON response is not automatically an evidentially valid response.

### 13.3 Requests, retries, and logs

Start with model concurrency 1. Set per-call timeout to 120 seconds, two transport retries with backoff, and at most one schema-repair request. Use at most two targeted evidence-follow-up cycles per function. Exhaustion produces a typed issue and a reviewable result, not an endless agent loop.

Record model identity/revision, serving backend, generation settings, prompt/schema versions, packet hash, attempt ID, latency, available usage data, and validation failures. Cache only against the full packet and model/prompt/settings identity. Stale results from older attempts cannot write into a newer decision revision.

Persist concise rationale, explicit comparisons, evidence references, and check results for users. Do not depend on private model reasoning traces as an audit record.

Budget each rendered request with the pinned tokenizer and chat template. Include system text, schema, evidence, candidate clauses and reserved output. Send only if input tokens plus reserved output fit the endpoint window and each fits any separate service cap. Split oversized packets by candidate or clause, retaining parent conditions, exceptions, timing/reset, bindings and source links. Record which obligations each part covers. If any necessary context cannot fit or parts leave coverage incomplete, mark that comparison incomplete for review. Apply the same check to extraction, linking, retries and follow-ups. Row retrieval and attribute scoring use the index and typed comparators with the model disabled.

Track peak input tokens per request separately from total input/output tokens and call count per order. Include retries, cache hits, splits, unsent oversize packets and elapsed time. Report locally counted input separately from provider-reported usage and mark unavailable usage explicitly. Record zero calls for disabled mode. Freeze model, tokenizer, window, output reserve, per-order token/call caps and cache policy for paired comparisons. Reaching a cap preserves unfinished work as unresolved.

### 13.4 Confidence and automation eligibility

Initial evidence grades:

| Grade | Meaning |
|---|---|
| `COMPLETE_SUPPORTED` | Required evidence is resolved; critical checks are supported and passed; no material ambiguity |
| `REVIEW_REQUIRED` | A semantic interpretation, unsupported behavior check, or unresolved alternative requires review |
| `INSUFFICIENT_OR_CONFLICTING` | Necessary evidence is missing or contradictory |

These grades are not probabilities. Model self-reported scores, if retained for experiments, are labeled uncalibrated and excluded from approval logic.

Later probability calibration must use a held-out labeled set for a clearly defined target such as “the selected configuration is acceptable for this function.” Store the calibration version and report reliability by function/scenario, together with error rates and abstention. Do not calibrate on the final test set or combine uncalibrated stage scores by averaging them.

## 14. Persistence and transactional integrity

### 14.1 Immutable snapshots, explicit current pointers

Store original files in a private local content-addressed directory and business records in PostgreSQL. JSON-only repositories may be used for the earliest deterministic prototype, but approval, concurrent editing, and durable worker acceptance require PostgreSQL integration tests.

Each `DecisionRevision` has an immutable decision payload once created. A review edit creates a child revision. Lifecycle transitions and validation reports are append-only records outside that payload. The order has one `working_decision_revision_id` and, separately, one `approved_decision_revision_id`; views and exports always declare which they show. Historical revisions do not count as simultaneous current selections.

Define `payload_hash` as SHA-256 over a versioned canonical UTF-8 JSON encoding of the decision content: pinned snapshots, input-generation token, assessments, ordered selection map, issue/evidence references and parent revision. Sort object keys and ID-indexed collections; preserve semantic sequences. Normalize decimals/units through typed contracts; exclude mutable lifecycle fields, validation reports, export timestamps and the hash itself. Each append-only validation report references `payload_hash` and has its own `report_hash` over its canonical findings, validator versions and verification evidence. Approval binds both hashes. There is no circular decision-hash/validation-hash definition.

The order also holds `input_generation`, incremented atomically for a new current document upload, accepted clarification, or active context change. A run and decision pin that generation. Upload does not have to wait for a new run to finish before making an older decision stale for current-order approval. Approval requires the pinned generation to equal the order's current generation. A document upload and approval both lock the same order row: whichever commits first establishes the sequence. An approval preceding a later upload remains historical, while the new generation immediately requires a new decision before current-order approval/export.

### 14.2 Database-enforced selection ownership

The database uses a primary key on `(decision_revision_id, function_id)`. That is the storage enforcement of the user's rule. There is no instance ID in this uniqueness key.

The following is a DDL design fragment. Referenced parent tables and their matching unique keys must be created by the implementation migration; this fragment is not a standalone migration.

```sql
CREATE TABLE selection (
    decision_revision_id uuid NOT NULL,
    knowledge_snapshot_id uuid NOT NULL,
    function_id uuid NOT NULL,
    config_revision_id uuid NOT NULL,
    PRIMARY KEY (decision_revision_id, function_id),
    FOREIGN KEY (decision_revision_id, knowledge_snapshot_id)
        REFERENCES decision_revision (id, knowledge_snapshot_id),
    FOREIGN KEY (knowledge_snapshot_id, function_id, config_revision_id)
        REFERENCES snapshot_config (knowledge_snapshot_id, function_id, config_revision_id)
);
```

Required parent invariants:

- `decision_revision` has unique `(id, knowledge_snapshot_id)` and `(id, order_id)`.
- `config_revision` has unique `(id, function_id)` and an immutable owner.
- `snapshot_config` has primary key `(knowledge_snapshot_id, function_id, config_revision_id)` and a foreign key `(config_revision_id, function_id)` to `config_revision(id, function_id)`.
- Each order current pointer has a composite foreign key pairing the revision ID with the order ID, preventing a pointer to another order's revision.
- Approval references the exact decision and validated content hashes. One approval record per revision is sufficient for the single-reviewer initial scope.

PostgreSQL unique and foreign-key constraints provide the primitive guarantees used here [R01]. Approval eligibility is a cross-record business condition, checked transactionally; do not attempt to encode it as a simple row-level CHECK over other tables.

### 14.3 Revision replacement transaction

For a human or worker update:

1. Validate the request's actor, order, idempotency key, and expected working revision.
2. Lock the order root row in a short transaction and compare the expected revision and pinned/current input generation.
3. Reject stale edits with HTTP 409; do not silently merge competing selections.
4. Insert a new immutable decision revision and its complete selection map.
5. Enforce ownership/snapshot foreign keys and zero-or-one cardinality.
6. Write the change event and update the working pointer atomically.
7. Enqueue affected validation work with a durable job record.

Expensive model calls and long validation runs happen outside that short transaction. Their results carry the input revision hash; attaching a report requires the hash to match, without changing the immutable payload. A stale-generation result may be archived for its original run but cannot advance the current working/approval pointers. Approval locks the order, checks the expected current revision and input generation, verifies a passing current report, and writes approval/pointer/event in one transaction. PostgreSQL row locking supports this coordination [R02].

Updating a required function from configuration A to B is a replacement in a new revision, not an append. A failed replacement leaves the previous revision intact. An approval cannot survive a changed decision payload.

### 14.4 Idempotency and crash recovery

API mutation keys are scoped by order and action. Repeating the same key and payload returns the recorded result; reusing the key with a different payload returns a conflict. Workers use stage keys built from snapshot/revision, stage, and implementation versions.

A worker claims a durable job with a lease and attempt token. Lease recovery may repeat computation, but only the current attempt may attach results through a compare-and-swap check. Atomic revision writes and idempotent export records prevent duplicate business effects. Do not claim that model calls themselves execute exactly once.

Write export bytes to a temporary path, verify their content, then atomically publish the file and manifest. A failed export does not undo an already valid approval; it produces a retryable export failure for that same approved revision.

## 15. Human review and change propagation

### 15.1 Review actions

| Action | Required input | Effect |
|---|---|---|
| Confirm or correct an extracted fact | Fact ID, typed value, source/engineering basis, expected revision | New reviewed assertion and affected recomputation |
| Resolve a source conflict | Chosen interpretation, justification, scope | Preserved competing assertions plus an explicit resolution |
| Confirm function demand | Required/not required, supporting evidence | New demand decision; selection and coverage rechecked |
| Replace a configuration | Function ID, one revision ID, reason, expected decision revision | New decision revision with zero-or-one selection preserved |
| Clear a selection | Function ID and reason | Zero selected; required function becomes unresolved |
| Supply manual verification | Named check, tested/reviewed scope, evidence and conclusion | A traceable verification result, not a generic override |
| Confirm a library gap | Completed search report and resolved requirements | Gap confirmed; function remains unconfigured |
| Approve | Exact decision revision and validation hash | Approval only if all gates pass |

A reviewer cannot click through a known hard failure to produce an approved order. They can correct a fact, provide appropriate missing verification, or initiate a reviewed knowledge change. That change then receives a new version and revalidation.

### 15.2 Dependency-aware invalidation

Maintain dependency edges from source blocks to facts, requirements, links, candidate checks, derived demands, selections, and global checks. Reuse unaffected results only when all relevant dependency/version hashes match.

| Change | Minimum invalidation |
|---|---|
| Current-order endpoint or polarity | Related binding/link, candidate checks, resource checks, coverage |
| Functional condition or timing | Requirement formalization, behavior checks, selection, coverage |
| Switch type | Relevant attribute checks and dependent behavior checks |
| Configuration revision | Its attributes/behavior, candidate checks, dependent selections |
| Rule revision | Rule effects, derived demands, candidate eligibility/preferences, global checks |
| Selected alternative | Conditional dependencies, resources, coverage, order validation |
| Unclassified source change | Conservatively rerun the complete order interpretation and validation |

Any material change makes the changed working revision unapproved. The previous approved revision remains historically valid for its original snapshots, clearly labeled as not representing the new working inputs.

### 15.3 Avoiding excessive clarification

Group questions by the missing fact and the functions it affects. One answer should resolve all legitimately linked checks. Prefer a precise field correction over asking the user to restate a long document.

A reviewed source-completeness policy may support absence claims, such as a complete equipment inventory explicitly excluding a device. Without that contract, “not mentioned” remains unknown. This lets the catalog sweep exclude irrelevant functions efficiently without converting every missing string into a false assertion.

## 16. API and user interface contracts

### 16.1 User-facing workflow

The review application has five primary surfaces: order upload/mapping, knowledge release review, run overview, function comparison, and output/approval history. The interface leads with the order's readiness and unresolved decisions, then lets the engineer inspect evidence.

The function comparison view contains original source excerpts, normalized requirements, candidate difference columns, failed/unknown checks, and one radio-button selection group. Clearing the choice is supported. Multiple-selection checkboxes are inappropriate for alternatives of one function.

A separate instance panel shows front/rear or other physical scopes. It never introduces independent selection controls for the same function. A change preview explains which dependent functions will be rechecked.

### 16.2 Initial HTTP endpoints

| Method and route | Contract |
|---|---|
| `POST /orders` | Create order with user-supplied context and schema version |
| `POST /orders/{order_id}/documents` | Upload role-tagged document; create immutable source snapshot |
| `GET /orders/{order_id}/imports/{import_id}` | Mapping preview, parsing issues, source completeness |
| `POST /knowledge/imports` | Import draft library/attributes/rules |
| `POST /knowledge/releases` | Publish reviewed, validated knowledge snapshot |
| `POST /orders/{order_id}/runs` | Pin order and knowledge snapshots; enqueue run; return HTTP 202 |
| `GET /runs/{run_id}` | Execution state, stage summaries, typed errors, result revision |
| `GET /decisions/{revision_id}` | Immutable assessment/selection summary |
| `GET /decisions/{revision_id}/functions/{function_id}` | Evidence packet, differences, checks and candidate list |
| `POST /orders/{order_id}/clarifications` | Reviewed assertion referencing the expected base revision |
| `PUT /orders/{order_id}/functions/{function_id}/selection` | Replace or clear one selection, then revalidate |
| `POST /decisions/{revision_id}/approvals` | Approve exact current revision with matching validation hash |
| `POST /decisions/{revision_id}/exports` | Generate explicitly draft or approved export |
| `GET /exports/{export_id}` | Status and authorized download for the pinned export |

Mutation endpoints require `Idempotency-Key` and an expected base revision where applicable. Responses include the resulting revision and affected-function IDs. Use 422 for malformed types/IDs, 409 for stale revisions or semantic selection conflicts, and a typed asynchronous failure in run status for processing errors.

Selection request shape:

```json
{
  "expected_decision_revision_id": "REV-DEMO-10",
  "config_revision_id": "DEMO-C-REGEN-02-R1",
  "reason": "Confirmed the required five-state sequence from reviewed evidence."
}
```

`config_revision_id` may be null to clear the selection. Arrays are rejected. Schema validation must not coerce an array or comma-separated string into a scalar ID. The function is identified by the route; the server verifies ownership against the pinned knowledge snapshot. Strict validation reduces unintended coercion, but domain checks still need explicit implementation [R05].

### 16.3 Error vocabulary

Initial stable error codes include `PARSE_INCOMPLETE`, `UNPARSED_REQUIREMENT`, `BASELINE_MISSING`, `AMBIGUOUS_JOIN`, `SOURCE_CONFLICT`, `ATTRIBUTE_BODY_CONFLICT`, `UNKNOWN_REQUIRED_FIELD`, `UNSUPPORTED_BEHAVIOR_CHECK`, `UNSUPPORTED_COMPOSITION`, `MULTIPLE_CONFIGS_FOR_FUNCTION`, `CONFIG_FUNCTION_MISMATCH`, `CONFIG_NOT_IN_SNAPSHOT`, `RULE_CARDINALITY_CONFLICT`, `SAME_FUNCTION_COMPOSITION_FORBIDDEN`, `DEPENDENCY_CONFLICT`, `RESOURCE_CONFLICT`, `UNCOVERED_REQUIREMENT`, `UNJUSTIFIED_SELECTION`, `PREPARATION_LIMIT_REACHED`, `SEARCH_LIMIT_REACHED`, `MODEL_TIMEOUT`, `MODEL_SCHEMA_INVALID`, `MODEL_EVIDENCE_INVALID`, `STALE_INPUT_GENERATION`, and `STALE_REVISION`.

Every issue includes scope, severity, evidence IDs, and a concrete resolution target. Users see plain-language explanations; codes remain available for troubleshooting and evaluation.

## 17. Output workbook and explanation design

### 17.1 Five-sheet workbook

Retain the illustrated hierarchical result view while separating verbose evidence. The four business sheets are supplemented by a small reproducibility manifest.

| Sheet | Row unit | Main fields |
|---|---|---|
| `Configuration Results` | One catalog configuration revision | Category/function/configuration, demand state, candidate status, selected flag, decision summary, evidence grade, issue IDs, review state |
| `Match Evidence` | One candidate/requirement or attribute comparison | Order value, candidate value, outcome, comparator, source locations, concise reason |
| `Open Issues` | One actionable issue | Function/requirement, severity, missing/conflicting facts, affected choices, requested resolution |
| `Coverage` | One requirement with linked coverage details | Original requirement, mapped function(s), selected configuration(s), verified/partial/unknown coverage, evidence |
| `Run Manifest` | One metadata entry | Order/knowledge/decision revisions, hashes, parser/model/rule versions, timestamp, draft/approved status |

Use stable IDs even when display numbering matches the familiar function library hierarchy. The first sheet can list several alternatives under a function, but its selected count is always zero or one. Excluded alternatives distinguish `FAILED_CHECK`, `NOT_CHOSEN`, `NOT_ASSESSED`, and `OUT_OF_SCOPE`; a single generic cross must not hide these meanings.

### 17.2 Symbols and approval labels

The photographs do not establish a complete approved symbol legend. Proposed default: `●` means selected, `×` means not selected, and `?` means unresolved. The authoritative columns are textual `selection_state` and `candidate_status`; symbols are optional presentation. A legend explains that an unresolved function has no selected alternative.

Every sheet identifies `DRAFT — UNRESOLVED` or `APPROVED`, with the decision revision. A draft may be exported for review even with zero choices on required functions. Approved export uses only the approved selection snapshot, never a newer draft.

### 17.3 Explanation contract

Each selected row answers:

1. Why is this function required for the order?
2. Which order facts and behavior clauses determine the choice?
3. Which candidate definition supports those comparisons?
4. Which checks passed, and by what verification method?
5. Why were close alternatives not selected?
6. What human review, if any, resolved ambiguity?

For an unresolved row, explain what prevents a choice and what would resolve it. Do not invent a positive matching story simply to populate an explanation column.

### 17.4 Export integrity checks

Before publication, reload the generated workbook and verify selected counts by function, exact revision IDs, counts of required/unresolved functions, issue links, and agreement with the decision payload. Check duplicate rows cannot accidentally create two selected alternatives. Verify Unicode, wrapped descriptions, frozen headers, filters, and source references.

Native source links use document ID plus structural location, with optional links to the application's evidence viewer. Do not rely on absolute paths from the developer's machine. The workbook remains understandable offline through source excerpts and location text.

## 18. Synthetic data and independent evaluation

### 18.1 Generate a coherent fictional domain

Define a synthetic engineering world with functions, mutually exclusive alternatives per function, hardware interfaces, switch behavior, dependencies, and order requirements. Produce DOCX/XLSX views from this world, then add controlled formatting and semantic perturbations.

Start with three families: lighting, stop requests, and a simplified multistate switch function. Add a simplified interlock family once Boolean and temporal checks work. All identifiers, product names, network IDs, bindings, and values are invented; the uploaded photographs guide structure rather than become the personal project's dataset.

### 18.2 Independent reference answers

Maintain hand-authored anchor cases in addition to generated cases. A reference answer may be one acceptable selection, several acceptable complete plans, or an expected unresolved/conflict outcome. Do not force one arbitrary gold ID when several choices are valid.

The reference checker is separate from runtime rule and selection implementations. Gold files are not mounted into the application process or model context. Evaluate the generator too: inspect anchor renderings and inject mutations whose expected consequences are specified independently.

Split by order/scenario family, not by spreadsheet row. Keep paraphrases and near-duplicate variants together. Use development, validation, and untouched test partitions; calibration uses a validation subset, never the final test partition.

### 18.3 Mandatory scenario matrix

| ID | Scenario | Expected result |
|---|---|---|
| E01 | Required function with one fully compatible alternative | Exactly one proposed choice |
| E02 | Function explicitly absent under a reviewed completeness policy | Zero, with exclusion basis |
| E03 | Function necessity unknown | Zero and clarification |
| E04 | Two same-function alternatives cover complementary clauses | No combined selection; report gap/conflict |
| E05 | Different instances appear to need different alternatives of one function | No instance-based bypass |
| E06 | Two selected revisions of one configuration | Cardinality rejection |
| E07 | Two globally acceptable alternatives without a decisive preference | Zero for the ambiguous function, choice requires review |
| E08 | Different functions jointly cover a requirement with compatible composition | Allowed, one per function |
| E09 | Dependency requires a conflicting alternative of an already chosen function | Backtrack or report conflict |
| E10 | Replacing a parent choice removes its conditional dependency | No stale derived demand |
| E11 | Historical pin matches, current endpoint is unrelated | Historical evidence cannot justify selection |
| E12 | Same pin token on different controllers | No false identity merge |
| E13 | `/`, explicit false, 0, and not-applicable | Distinct internal states |
| E14 | `0/1/2/3` switch sequence | Preserved as a value, not blank |
| E15 | Two physical positions controlling five states | Position count distinct from state count |
| E16 | OR changed to AND, or polarity reversed | Counterexample/failure |
| E17 | Delay differs by a factor of ten | Timing mismatch |
| E18 | Reset or timeout behavior missing | Unknown/unsupported check, not automatic pass |
| E19 | Source tables disagree | Conflict preserved and surfaced |
| E20 | Baseline inheritance referenced but baseline absent | `BASELINE_MISSING` |
| E21 | Deleted/obsolete DOCX content resembles a match | Not treated as current without revision resolution |
| E22 | Attribute index disagrees with configuration body | Knowledge conflict, no silent pass |
| E23 | Requirement outside the catalog | Residual demand prevents complete approval |
| E24 | Duplicate copied evidence in three sources | No unjustified confidence increase |
| E25 | Parser misses a merged header or nested clause | Completeness/anchor test detects the issue |
| E26 | Blank or stale formula cache | No invented numeric value |
| E27 | Model invents an evidence/configuration ID | Output rejected |
| E28 | Prompt instruction embedded in source text | No authority over workflow |
| E29 | Timeout, invalid JSON, repeated request | Bounded failure, durable recovery |
| E30 | Two reviewers replace the same selection concurrently | One current revision; stale request rejected |
| E31 | Database insert attempts two selections for one function | Constraint rejects duplicate |
| E32 | Export includes duplicate selected rows | Export integrity check fails |
| E33 | Order evidence changes after approval | New revision needs revalidation; stale approval not reused |
| E34 | Search resource limit reached | Incomplete search outcome, not a proven gap |
| E35 | Wrong-function configuration or wrong-snapshot revision | Referential/application rejection |
| E36 | Selected configuration adds an unwanted shared-output action | Interaction issue surfaced |
| E37 | Two locally eligible candidates, only one globally feasible | Global planner selects the feasible alternative |
| E38 | New source uploaded before approval while no new run is complete | Old input-generation approval rejected |
| E39 | Validation report added after immutable decision creation | Payload hash unchanged; report hash separate |
| E40 | Shared requirement has partial per-function obligations | Only reviewed complete composition can pass |
| E41 | Deterministic parser encounters unregistered prose | Unparsed clause retained; M2 proposal requires validation |
| E42 | Candidate requires a previously inactive function | Potential closure prepares candidates; only active branch creates demand |

### 18.4 Metrics

| Metric | Definition |
|---|---|
| Evidence recall | Required gold evidence relationships recovered / required gold evidence relationships |
| Join precision | Correct accepted entity links / accepted entity links |
| Candidate recall | Resolvable assessments with at least one acceptable candidate retrieved / resolvable assessments |
| Single-choice violation count | Decision/export functions with more than one selected alternative |
| Selected-choice precision | Acceptable proposed choices / proposed choices, scored against independent references |
| Demand recall | Required functions/demands correctly identified / required functions/demands |
| False exclusion rate | Required functions incorrectly declared not required / required functions |
| Correct unresolved rate | Cases requiring abstention correctly left unresolved / cases requiring abstention |
| Wrong acceptance rate | Cases with disqualifying conditions incorrectly marked review-ready / such cases |
| Complete-order correctness | Orders matching an acceptable full plan or correct unresolved outcome / evaluated orders |
| Review effort | Measured active review time and correction count, reported separately from model latency |

Report denominators, scenario breakdowns, and sample counts. A model that abstains on everything can have no wrong selections but no useful automation; report completion and error metrics together.

### 18.5 Gates and experiments

All mandatory invariant and fault tests must pass; duplicate selections must be zero at application, database, and export layers. No case with known critical conflict may be marked approval-ready in the frozen anchor set. These are test gates, not claims of zero real-world risk.

Run two paired experiments on the same synthetic orders. The first changes discovery only. The second holds the row hits constant and tests whether scoring and deduplication alone would produce acceptable decisions.

| Experiment | Runs on each order | Recorded outputs |
|---|---|---|
| Discovery | `row`, `function`, `hybrid` (§10.5), each with the same family completion, candidate checks, planner and order validator | Raw hits and zero-hit queries, unique candidates before/after expansion, accepted links and residual demands, checks, final selections or abstentions, reasons, resources used |
| Decision policy | Replay the identical row-hit artifact. One branch uses signed scores and deduplication only. The other uses the same unique candidate IDs and applicable obligations with hard checks, planning and independent validation. Freeze the candidate pool in both branches and record missing family members/dependencies as incomplete. | Preserve the original raw shortlist including multiple alternatives. For comparable top choices, report the unique highest positive score per function, abstaining on ties or no positive score. Compare both branch outputs against independent acceptable plans/issues. Record raw duplicate-function proposals, wrong choices and missed abstentions before any correction. |

The score-only replay lives in the evaluation runner. It produces hypothetical choices and a diagnostic of which constraints they would violate. Only the checked application path produces a decision revision eligible for review. Keep the fixed-pool replay distinct from end-to-end row discovery, where family completion is required. Test normalization, rule use and other ablations independently after these comparisons.

Pin a manifest per paired case with the input and knowledge hashes, split and case family, parser/index/comparator/planner versions, policy/weights/K, model settings, resource limits, cache state, and artifact hashes. Hold these fixed except for the named experimental factor. Use independent hand-authored expected links, eligible alternatives, acceptable plans or required unresolved outcomes. Include simple exact matches, a valid candidate below every row cutoff, complementary partial matches with no valid single choice, copied rows, ambiguous front/rear or historical pins, cross-function conflicts and a long packet with a decisive trailing exception. Keep variants of a family in the same split. Run deterministic comparisons first, then pair model-enabled runs separately.

Report per-case gains and losses plus §18.4 counts and denominators. Measure candidate recall before and after family completion, wrong accepted links, whole-order correctness, wrong acceptance, correct abstention, and review time/corrections. Report per-order row queries, unique definitions fetched, candidate checks, model calls, total tokens, peak request size, latency, splits, incomplete comparisons and cost when known. A missing or failed run stays in the case ledger. Predeclare quality and resource limits on development data and freeze them before validation. A proposed operational default must pass all invariant gates, introduce zero new critically wrong acceptances on the paired mandatory cases and meet the frozen resource limits. Apply the same adoption test to checked row-led and hybrid discovery. Require a gain in complete-order correctness or reduced measured review effort without regression in the other metric or in correct abstention. If both qualify, prefer higher complete-order correctness, then lower review effort, then lower per-order cost under the same deployment assumptions. Retain the function default for a tie with baseline, inconclusive evidence or missing required measurements. Evaluate the chosen configuration once on untouched families and report failures separately.

Use pytest and custom deterministic metrics first. Add a prompt/model comparison runner when real model calls are introduced; a framework can organize experiments, but domain scoring remains project-owned. LLM grading may assess explanation clarity after human validation, not critical cardinality, polarity, or behavior correctness.

## 19. Deployment and operational behavior

### 19.1 Runtime arrangement

| Process/storage | Responsibility |
|---|---|
| FastAPI application | Authenticated review/API and source/evidence views |
| Durable worker | Parsing, extraction, candidate checks, planning, validation, exports |
| PostgreSQL | Business snapshots, runs, jobs, review events, approvals, workflow checkpoints |
| Private file directory | Original documents, derived evidence artifacts, exports, manifests |
| Qwen model endpoint | Replaceable inference service, local or on a server controlled by the user |

Use ordinary Python functions for domain logic. LangGraph may orchestrate stage transitions and review/resume once those functions work. Its checkpointer stores workflow state, not the entire business audit model. Resume may re-enter node code, so persistent side effects must be idempotent [R06].

Keep model inference dependencies separate from the application. Select and pin actual package/model versions during environment setup after compatibility checks. This design does not assume available GPU hardware or claim a particular model size will fit the user's computer.

### 19.2 Access and data handling

For local development, bind to loopback. For a shared server, require authentication, TLS, and role checks for knowledge publication, manual review, and approval. The initial personal deployment can use one reviewer role; a multi-person separation-of-duties policy is a later requirement, not assumed here.

Uploads are parsed as data; do not execute macros, external links, arbitrary formulas, or expression strings. Validate archive/file sizes and types. Keep model endpoint credentials out of documents, prompts, exports, and repository history. Use only synthetic content for this independent project.

### 19.3 Operations and observability

Trace stages by run ID, snapshot IDs, function ID, candidate ID, attempt ID, and implementation version. Record typed outcomes rather than only log prose. Expose counts of unresolved functions, model failures, search limits, stale responses, and export failures.

Back up database and source-file storage together with a manifest that identifies the consistent revision boundary. Demonstrate a restore on a separate test location. The restored system must reproduce an approved export without querying changing external knowledge.

Cancellation stops new stages and prevents stale attempts from committing, but does not promise an already-started external inference call has physically stopped. Large inputs use bounded queues and stage limits rather than unbounded concurrency.

## 20. Repository layout and module interfaces

### 20.1 Responsibility map

| Path | Responsibility |
|---|---|
| `src/busconfig/domain/contracts.py` | Shared typed IDs, states, evidence, requirement, selection and result contracts |
| `src/busconfig/domain/invariants.py` | Pure identity and cardinality checks |
| `src/busconfig/ingest/xlsx_parser.py` | Spreadsheet profiles and structural source extraction |
| `src/busconfig/ingest/docx_parser.py` | Function-library structure and effective-content handling |
| `src/busconfig/knowledge/compiler.py` | Configuration ownership, attributes, rule validation and snapshot compilation |
| `src/busconfig/knowledge/rules.py` | Restricted predicate evaluation and derived-demand provenance |
| `src/busconfig/orders/interpreter.py` | Order assertions, requirements and source-clause ledger |
| `src/busconfig/orders/linker.py` | Scoped entity/link resolution and conflict preservation |
| `src/busconfig/retrieval/evidence.py` | Function evidence collection and missing-evidence questions |
| `src/busconfig/retrieval/candidates.py` | Candidate enumeration and bounded broader search |
| `src/busconfig/validation/candidate.py` | Attribute/interface comparison and check aggregation |
| `src/busconfig/validation/behavior.py` | Supported Boolean and event-trace verification |
| `src/busconfig/validation/composition.py` | Released obligation allocations, connection checks and joint-behavior verification |
| `src/busconfig/selection/planner.py` | Constrained single-choice search and search-completeness report |
| `src/busconfig/validation/order.py` | Independent order validation and approval eligibility |
| `src/busconfig/models/client.py` | Model adapter, timeout/retry, response envelope |
| `src/busconfig/models/compare.py` | Packet/schema construction and semantic response validation |
| `src/busconfig/models/extract.py` | Independent order extraction and entity-link proposals with source spans |
| `src/busconfig/persistence/repository.py` | Transactional snapshots, revisions, selections and approvals |
| `src/busconfig/workflow/runner.py` | Durable stages, leases, versioned reuse and cancellation |
| `src/busconfig/review/service.py` | Clarifications, replacements, invalidation and approval commands |
| `src/busconfig/export/workbook.py` | Workbook rendering and reload integrity checks |
| `src/busconfig/api/app.py` | HTTP routes and authentication boundaries |
| `src/busconfig/ui/` | Review templates and client interactions |
| `tests/unit/`, `tests/integration/`, `tests/acceptance/` | Domain, persistence, parser and full-workflow checks |
| `evals/gold/`, `evals/runners/`, `evals/reports/` | Isolated reference outcomes, evaluation runner and reports |
| `synthetic/worlds/`, `synthetic/renderers/` | Invented domain definitions and source-file generation |
| `src/busconfig/orders/templates.py` | Versioned deterministic source-language patterns and their formal mappings |
| `migrations/`, `deploy/`, `docs/` | Schema migrations, deployment configuration and project documentation |

The paths are proposed files for the new repository, not claims that they already exist.

### 20.2 Interface contracts

All types below are defined in `domain/contracts.py` before dependent implementation. `ModelResponse` and `SemanticComparison` are distinct from validated `CandidateCheck` records.

```python
parse_xlsx(source: SourceDocument, profile: LayoutProfile) -> ParseResult
parse_docx(source: SourceDocument, profile: LayoutProfile) -> ParseResult
compile_knowledge(inputs: KnowledgeInputs) -> KnowledgeCompilation
evaluate_rules(facts: FactSet, rules: RuleSet, selections: SelectionMap) -> RuleEvaluation
interpret_order(parsed: list[ParseResult], context: OrderContext) -> OrderInterpretation
resolve_links(order: OrderInterpretation, aliases: AliasRegistry) -> LinkedOrder
build_order_evidence(order: LinkedOrder, function: Function, knowledge: KnowledgeSnapshot) -> OrderEvidenceContext
retrieve_candidates(context: OrderEvidenceContext, knowledge: KnowledgeSnapshot) -> CandidateSet
check_candidate(context: OrderEvidenceContext, candidate: ConfigRevision) -> CandidateAssessment
build_comparison_packet(context: OrderEvidenceContext, candidates: CandidateSet, checks: list[CandidateAssessment]) -> EvidencePacket
verify_behavior(requirement: BehaviorSpec, candidate: BehaviorSpec, domain: InputDomain) -> BehaviorCheck
verify_composition(template: CompositionTemplate, selections: SelectionMap, order: LinkedOrder, knowledge: KnowledgeSnapshot) -> CompositionCheck
propose_order_interpretation(parsed: list[ParseResult], context: OrderContext, client: ModelClient) -> OrderExtractionProposal
propose_links(order: OrderInterpretation, aliases: AliasRegistry, client: ModelClient) -> LinkProposalSet
compare_with_model(packet: EvidencePacket, client: ModelClient) -> SemanticComparison
plan_selection(order: LinkedOrder, preparation: AssessmentPreparation, knowledge: KnowledgeSnapshot, budget: SearchBudget) -> SelectionPlan
validate_order(order: LinkedOrder, plan: SelectionPlan, knowledge: KnowledgeSnapshot) -> ValidationReport
replace_selection(command: ReplaceSelectionCommand, repo: Repository) -> DecisionRevision
approve_decision(command: ApproveDecisionCommand, repo: Repository) -> Approval
render_workbook(decision: DecisionRevision, report: ValidationReport, destination: Path) -> ExportManifest
```

`SelectionMap` maps `FunctionId` to one `ConfigRevisionId`; absence means no selection. External bulk data is validated as a list before conversion to this map so duplicate function entries cannot disappear through dictionary overwriting. `KnowledgeCompilation` returns a draft snapshot plus blocking/nonblocking issues; it cannot be published while blockers remain.

`SelectionInput` contains a function ID and configuration revision ID for one externally supplied selected row. `CandidateSet` contains complete retrieved `ConfigRevision` records and search metadata; `OrderEvidenceContext` contains no candidate checks. `OrderExtractionProposal` and `LinkProposalSet` preserve unapproved assertions, exact source spans, alternatives and issues. `CompositionCheck` contains allocated-obligation, connection and joint-behavior results. `ModelClient` exposes `complete(request: ModelRequest) -> ModelResponse`, with request identity, allowed schema, payload and execution settings; both fake and HTTP clients implement that boundary.

`KnowledgeInputs` includes parsed library content, reviewed attribute/rule drafts, catalog mapping and composition templates. `prepare_assessments(order: LinkedOrder, knowledge: KnowledgeSnapshot, limit: int = 500) -> AssessmentPreparation` in `retrieval/evidence.py` expands the potential dependency frontier and calls evidence/candidate/check modules. `AssessmentPreparation` contains assessments keyed by context hash, branch-checkable guards, obligation allocations, completeness and issues. The workflow passes the entire `AssessmentPreparation` to the planner, never only the assessment list. The planner verifies required contexts exist before search and propagates incomplete preparation and its issues into the selection plan, blocking completeness and approval claims. Preparation and selection budgets are separate.

`OrderInterpretation` and `LinkedOrder` retain facts, requirements, instance scopes, and unresolved items. `CandidateAssessment` carries check outcomes and evidence sufficiency; it never changes the selected map. `SelectionPlan` records budget exhaustion and unresolved functions, while `ValidationReport` independently determines approval eligibility.

Before building a function evidence context, T07's discovery step consumes the pinned parsed blocks, linked order, knowledge snapshot and policy. It returns tentative leads plus the §10.5 trace. At T09 the run coordinator supplies these to assessment preparation through an optional discovery input, preserving the function-led call above as the default. Resolve leads against the linked order before family expansion. Keep ranked hits in the trace and pass the unique full revisions through the existing `CandidateSet` boundary.

## 21. Implementation plan and acceptance gates

### Bus Function Configuration AI Implementation Plan

> **For agentic workers:** Use task-by-task execution with explicit tests and review. If the user chooses the installed Superpowers execution workflow, use `superpowers:executing-plans`; delegate only when separately authorized. Do not treat this design deliverable as authorization to implement or deploy.

**Goal:** Build a synthetic-data application that produces evidence-backed order configurations with at most one configuration per function.

**Architecture:** Separate source interpretation, knowledge compilation, evidence retrieval, candidate checking, single-choice planning, and order validation. Preserve immutable snapshots and human review; model assistance operates through bounded, validated interfaces.

**Tech Stack:** Python, uv, openpyxl, python-docx with explicit OOXML handling where required, Pydantic, PostgreSQL, FastAPI, pytest, a replaceable Qwen endpoint, and LangGraph for durable review workflows when introduced.

**Spec:** Sections 1–20 and 22–23 of this document. Copy this file into the repository as `docs/Bus_Config_AI_Detailed_Design_EN_v3.md` and its companion as `docs/Bus_Config_AI_Implementation_Plan_EN_v1.md` before implementation. Preserve these basenames so the Obsidian cross-document links continue to work.

### Global constraints

- Each function in the function library may select at most one configuration for an order.
- The selection key is decision revision plus function ID; instances do not create extra slots.
- Unknown is not false, zero, or not-applicable; `/` as a standalone token means blank.
- Source photographs provide structure; project datasets use invented engineering values.
- No same-function composition, invented configuration IDs, silent rebindings, or automatic rule publication.
- Current-order evidence, historical reference, and planned use remain distinct.
- Required unresolved functions block approval but permit a clearly labeled draft report.
- Every persisted and exported decision pins source, knowledge, and decision versions.

### Review focus

Five easily missed input classes are assigned explicit checks below: duplicate external rows overwritten by maps (T01), revision-marked DOCX content outside ordinary paragraph lists (T04), dependency removal after replacement (T09/T12), stale concurrent reviews or input uploads (T11/T12), and draft exports accidentally displaying approved status (T14).

### Work package order

| Milestone | Tasks | Usable outcome |
|---|---|---|
| M0 | T01–T02 | Domain contracts, cardinality checks, independent synthetic anchors |
| M1 | T03–T09 | Deterministic native-file-to-draft workflow with single-choice validation |
| M2 | T10 | Model-assisted comparisons measured against M1 |
| M3 | T11–T14 | Durable review, API/UI, approved and draft workbooks |
| M4 | T15–T16 | Evaluation report, reproducible deployment and restore demonstration |

Start each task with its named behavior test, observe the intended failure, implement the minimum behavior, run the relevant suite, and commit the tested unit. Do not run nonexistent commands as evidence that this document has been implemented. Commands below are commands for the future repository.

### T01 — Contracts and single-choice invariants

**Execution steps:** [T01 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t01-contracts-and-single-choice-invariants).

**Files:** Create `pyproject.toml`, `src/busconfig/domain/contracts.py`, `src/busconfig/domain/invariants.py`, and `tests/unit/test_selection_contracts.py`.

**Consumes:** Sections 2, 5, 8, and 20. **Produces:** All shared contracts; `validate_selection_rows(rows: list[SelectionInput]) -> SelectionMap`, which rejects duplicates before map construction.

- [ ] Write `test_duplicate_function_rows_are_rejected`: two different configuration IDs for the same function raise `MULTIPLE_CONFIGS_FOR_FUNCTION`; two identical repeated rows are also rejected rather than silently collapsed.
- [ ] Add `test_instances_do_not_change_selection_key`, `test_null_selection_is_allowed_in_draft`, and `test_false_zero_missing_are_distinct`; assert the precise behaviors in Sections 2 and 8.
- [ ] Run `uv run pytest tests/unit/test_selection_contracts.py -q` and observe the intended missing/incorrect-contract failure; implement contracts, explicit validation and the environment lockfile.
- [ ] Rerun that file; expect all tests to pass. Reject arrays supplied to a scalar selected ID and accept a null clear-selection request.
- [ ] Commit the contracts and tests together. Gate: there is no list-valued authoritative selected configuration field.

### T02 — Synthetic anchors and isolated reference outcomes

**Execution steps:** [T02 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t02-synthetic-anchors-and-independent-reference-outcomes).

**Files:** Create `synthetic/worlds/core.yaml`, `synthetic/renderers/fixtures.py`, `evals/types.py`, `evals/gold/anchors.json`, `tests/acceptance/test_anchor_integrity.py`.

**Consumes:** T01 IDs and states. **Produces:** `build_anchor_suite() -> AnchorSuite`; define `AnchorSuite` in `evals/types.py` with cases containing fixture paths, split/scenario IDs, acceptable selection maps or expected unresolved state, expected issue codes and independent verification notes. Application runtime code never imports evaluation types or reference outcomes.

- [ ] Hand-author E01–E10, including E04's two complementary same-function alternatives with an expected unresolved result, not a combined gold selection.
- [ ] Write `test_anchor_selection_cardinality` and `test_gold_is_not_application_input`; assert every gold plan respects cardinality and application fixture bundles contain no answer directory or answer-revealing metadata.
- [ ] Run `uv run pytest tests/acceptance/test_anchor_integrity.py -q`; observe failure before implementing fixture validation and rendering support.
- [ ] Implement and rerun; inspect at least one hand-authored order and its reference comparison without using the production planner.
- [ ] Commit the fictional world, reference outcomes and tests. Gate: anchors specify both acceptable selections and correct abstentions.

### T03 — Spreadsheet ingestion with provenance

**Execution steps:** [T03 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t03-spreadsheet-ingestion-with-provenance).

**Files:** Create `src/busconfig/ingest/xlsx_parser.py`, `tests/integration/test_xlsx_parser.py`, and XLSX fixtures under `tests/fixtures/xlsx/`.

**Consumes:** `SourceDocument`, `LayoutProfile`, T02 fixtures. **Produces:** `parse_xlsx(...) -> ParseResult` as specified in Section 20.

- [ ] Write fixture tests for merged headers, multiline cells, historical/current columns, standalone `/`, `0/1/2/3`, and empty formula caches. Assert retained source cells and correct value/scope states.
- [ ] Run `uv run pytest tests/integration/test_xlsx_parser.py -q`; confirm the missing parser causes the expected failures.
- [ ] Implement layout-profile mapping and completeness reporting; preserve raw text and formatting metadata needed by the profile.
- [ ] Rerun tests; assert a missing mandatory column emits `PARSE_INCOMPLETE` rather than returning a deceptively complete result.
- [ ] Commit the parser and fixtures. Gate: parsing preserves scope and location, and never fills arbitrary blanks.

### T04 — DOCX library structure and effective content

**Execution steps:** [T04 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t04-docx-library-structure-and-effective-content).

**Files:** Create `src/busconfig/ingest/docx_parser.py`, `tests/integration/test_docx_parser.py`, and DOCX fixtures under `tests/fixtures/docx/`.

**Consumes:** Shared source contracts and explicit effective-content profiles. **Produces:** `parse_docx(...) -> ParseResult`.

- [ ] Write tests with configuration headings, body tables, continued content, a deleted clause, and an inserted paragraph inside revision XML. Assert every effective clause belongs to the correct configuration.
- [ ] Run `uv run pytest tests/integration/test_docx_parser.py -q`; confirm expected failures before implementation.
- [ ] Implement document-order traversal and explicit revision handling; mark unsupported or ambiguous effective-content structures as blocking parse issues.
- [ ] Rerun; assert obsolete deleted logic cannot become a passing candidate fact and relevant inserted content cannot vanish silently.
- [ ] Commit. Gate: ordinary paragraph extraction alone is not accepted as complete library parsing.

### T05 — Knowledge compiler and authoring templates

**Execution steps:** [T05 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t05-knowledge-compiler-and-authoring-templates).

**Files:** Create `src/busconfig/knowledge/compiler.py`, `src/busconfig/knowledge/rules.py`, `tests/unit/test_knowledge_compiler.py`, and `docs/data-contracts.md`.

**Consumes:** T03/T04 parsed knowledge and T01 contracts. **Produces:** `compile_knowledge(...) -> KnowledgeCompilation`, `evaluate_rules(...) -> RuleEvaluation`, and the Section 7 workbook templates.

- [ ] Write tests for wrong-owner configuration, attribute/body disagreement, unsupported rule operators, unknown rule conditions, a dependency demanding two alternatives of the same function, and composition templates with missing obligation owners or same-function alternative participants.
- [ ] Run `uv run pytest tests/unit/test_knowledge_compiler.py -q`; expect the new contracts/behavior to fail initially.
- [ ] Implement ownership, typed attributes, source references, rule predicates and release gates. Keep informational experience non-executable.
- [ ] Rerun; assert `RULE_CARDINALITY_CONFLICT` blocks publication and unknown conditions do not create false exclusions.
- [ ] Commit. Gate: a compiled release has stable owners, explicit versions, and approved executable rules.

### T06 — Independent order interpretation and linking

**Execution steps:** [T06 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t06-independent-order-interpretation-and-linking).

**Files:** Create `src/busconfig/orders/interpreter.py`, `src/busconfig/orders/linker.py`, `src/busconfig/orders/templates.py`, `tests/unit/test_order_interpretation.py`; align synthetic renderers with the declared template registry without embedding reference answers.

**Consumes:** Parsed order sources, context, and approved aliases. **Produces:** `interpret_order(...) -> OrderInterpretation` and `resolve_links(...) -> LinkedOrder`.

- [ ] Write tests for same pin token/different controller, current-versus-historical disagreement, an absent referenced baseline, conflicting descriptions, an out-of-catalog demand, supported template clauses and unregistered prose preserved as `UNPARSED_REQUIREMENT`.
- [ ] Run `uv run pytest tests/unit/test_order_interpretation.py -q`; inspect expected failures.
- [ ] Implement scoped assertions, source-clause ledger, baseline resolution and link alternatives. Keep requirements before candidate comparison.
- [ ] Rerun; assert ambiguous joins remain ambiguous and the out-of-catalog demand stays visible.
- [ ] Commit. Gate: order facts are not rewritten to fit a candidate and every extracted clause retains its enclosing scope.

### T07 — Evidence and candidate retrieval

**Execution steps:** [T07 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t07-evidence-retrieval-and-candidate-enumeration).

**Files:** Create `src/busconfig/retrieval/evidence.py`, `src/busconfig/retrieval/candidates.py`, `tests/unit/test_retrieval.py`.

**Consumes:** `LinkedOrder`, knowledge snapshot and function assessments. **Produces:** `build_order_evidence(...) -> OrderEvidenceContext`, `retrieve_candidates(...) -> CandidateSet`, and `build_comparison_packet(...) -> EvidencePacket`.

- [ ] Write tests that a known function retrieves its complete eligible family, contrary evidence is retained, unknown attributes do not hard-filter candidates, and truncated broad search does not confirm a gap.
- [ ] Run `uv run pytest tests/unit/test_retrieval.py -q`; observe failures.
- [ ] Implement exact IDs, scoped aliases, structural filters and lexical fallback with recorded completeness. Keep evidence retrieval separate from candidate retrieval.
- [ ] Rerun; assert packet references cannot cross order snapshots and parent configuration context is restored after paragraph matches.
- [ ] Commit. Gate: candidate IDs and rejected/unknown reasons are inspectable without a model.

### T08 — Attribute and behavior validation

**Execution steps:** [T08 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t08-attribute-and-behavior-validation).

**Files:** Create `src/busconfig/validation/candidate.py`, `src/busconfig/validation/behavior.py`, `src/busconfig/validation/composition.py`, `tests/unit/test_candidate_validation.py`.

**Consumes:** Order evidence contexts, config revisions, supported behavior specs and released composition templates. **Produces:** `check_candidate(...) -> CandidateAssessment`, `verify_behavior(...) -> BehaviorCheck`, `verify_composition(...) -> CompositionCheck`.

- [ ] Write tests for OR/AND, polarity, tenfold delay differences, missing reset, physical position count versus controlled-state count, unsupported behavior, complete cross-function obligation allocation, and an unverified composition that must remain unresolved.
- [ ] Run `uv run pytest tests/unit/test_candidate_validation.py -q`; observe failures for the intended cases.
- [ ] Implement explicit comparators, truth-table counterexamples and event-trace checks with verification-scope metadata. Never execute expression strings.
- [ ] Rerun; assert a failed required condition cannot be outweighed by matching attributes and unsupported critical behavior stays unknown.
- [ ] Commit. Gate: every candidate outcome names its method, values, source evidence, and unresolved scope.

### T09 — Single-choice planning and independent order validation

**Execution steps:** [T09 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t09-single-choice-planning-and-independent-order-validation).

**Files:** Create `src/busconfig/selection/planner.py`, `src/busconfig/validation/order.py`, `tests/unit/test_selection_planner.py`, `tests/acceptance/test_deterministic_order.py`; extend `src/busconfig/retrieval/evidence.py` with dependency-frontier preparation using the T08 validators.

**Consumes:** Linked order, complete `AssessmentPreparation` including guards/allocations/completeness/issues, knowledge rules/composition templates and search budget. **Produces:** `prepare_assessments(...) -> AssessmentPreparation`, `plan_selection(...) -> SelectionPlan`, `validate_order(...) -> ValidationReport`.

- [ ] Write E04/E05/E08/E09/E10/E34/E37/E42 tests. Assert same-function composition is rejected, cross-function composition is checked, dependency conflicts backtrack, removed parents remove derived demands, locally tied candidates survive for global disambiguation, previously inactive dependency functions are prepared, and exhausted search is not proven infeasibility.
- [ ] Run `uv run pytest tests/unit/test_selection_planner.py tests/acceptance/test_deterministic_order.py -q`; observe failures.
- [ ] Implement potential-dependency closure, bounded backtracking and independent validation, including branch-scoped obligations, reverse justification and material extra behavior. Reject duplicate selection rows before mapping; pass the whole preparation result to search and assert preparation limits propagate to the plan/report as blocking incomplete outcomes.
- [ ] Rerun; add a case where the locally preferred choice causes a cross-function conflict and a less-preferred eligible alternative makes the order feasible.
- [ ] Commit. Gate: M1 produces a correct draft or correct unresolved report from native files without model calls.

### T10 — Model adapter and semantic comparison

**Execution steps:** [T10 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t10-model-adapter-and-bounded-semantic-assistance).

**Files:** Create `src/busconfig/models/client.py`, `src/busconfig/models/compare.py`, `src/busconfig/models/extract.py`, `tests/unit/test_model_contract.py`, `evals/runners/compare_models.py`.

**Consumes:** Parsed order sources/context for extraction, order interpretation/aliases for linking, and finalized evidence packets for comparison. **Produces:** `propose_order_interpretation(...) -> OrderExtractionProposal`, `propose_links(...) -> LinkProposalSet`, `compare_with_model(...) -> SemanticComparison`; HTTP adapter implementing `ModelClient`.

- [ ] Write tests for timeout, malformed JSON, invented IDs, missing evidence, source-embedded instructions, a response attempting to overrule a hard failure, paraphrased order clauses with exact span references, and ambiguous-device link alternatives that cannot become approved automatically.
- [ ] Run `uv run pytest tests/unit/test_model_contract.py -q`; observe intended failures using controlled fake responses.
- [ ] Implement bounded retries and schema/evidence validation for all three adapters. Extraction must not receive candidate definitions; preserve unknown proposals until corroboration/review. Add one real-model integration path behind explicit endpoint configuration.
- [ ] Rerun contract tests, then execute a frozen anchor comparison with the actual configured model. Record real and fake runs separately.
- [ ] Commit. Gate: model assistance improves or explains designated semantic cases without weakening deterministic constraints; no fabricated benchmark numbers.

### T11 — PostgreSQL schema and atomic decision revisions

**Execution steps:** [T11 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t11-postgresql-schema-and-atomic-decision-revisions).

**Files:** Create `src/busconfig/persistence/repository.py`, `migrations/001_core.sql`, `tests/integration/test_revision_repository.py`.

**Consumes:** Shared domain contracts and Section 14 constraints. **Produces:** `Repository` operations for snapshots, revisions, selected maps, jobs, review events, reports and approval.

- [ ] Write real-PostgreSQL tests for duplicate function selections, wrong configuration owner, wrong snapshot membership, cross-order pointer, idempotent repeated mutation, concurrent replacements, unchanged decision payload hashes after report insertion, and atomic input-generation increments.
- [ ] Run `uv run pytest tests/integration/test_revision_repository.py -q` against a disposable configured PostgreSQL instance; observe expected missing-schema/behavior failures.
- [ ] Implement complete migrations, composite foreign keys, short root-row transactions, optimistic revision checks, and atomic event/pointer writes.
- [ ] Rerun; assert one concurrent update succeeds and the stale one returns `STALE_REVISION`, with no partially written new selection.
- [ ] Commit. Gate: database tests independently enforce cardinality; in-memory tests are insufficient evidence for this milestone.

### T12 — Review, invalidation, and approval

**Execution steps:** [T12 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t12-human-review-invalidation-and-approval).

**Files:** Create `src/busconfig/review/service.py`, `tests/integration/test_review_service.py`.

**Consumes:** Repository, order/candidate validators, dependency records. **Produces:** `replace_selection(...) -> DecisionRevision`, `approve_decision(...) -> Approval`, and clarification commands.

- [ ] Write tests for clearing a required function, replacing A with B, stale validation hashes, manual evidence resolution, dependent-demand removal, edits after approval, and a document-upload/approval race before a replacement run completes; the new input generation must block approval of the old current decision.
- [ ] Run `uv run pytest tests/integration/test_review_service.py -q`; observe failures.
- [ ] Implement immutable child revisions, impact propagation, explicit manual verification and transactional approval gates.
- [ ] Rerun; assert clearing blocks approval, replacement never leaves both choices selected, and old approvals cannot validate changed working inputs.
- [ ] Commit. Gate: human review changes facts or choices transparently without bypassing hard conditions.

### T13 — Durable workflow, API, and review UI

**Execution steps:** [T13 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t13-durable-workflow-api-and-review-ui).

**Files:** Create `src/busconfig/workflow/runner.py`, `src/busconfig/api/app.py`, `src/busconfig/ui/`, `tests/integration/test_workflow_api.py`.

**Consumes:** Repository, review service and all processing stage contracts. **Produces:** Section 16 routes, durable job stages, and single-choice review screens.

- [ ] Write tests for crash after stage completion, lease recovery, stale attempt responses, cancel-before-commit, selection array rejection, unauthorized approval, and HTTP 409 on stale edits.
- [ ] Run `uv run pytest tests/integration/test_workflow_api.py -q`; observe failures.
- [ ] Implement durable stage identities, status projections, bounded worker concurrency, review/resume, and radio-button alternatives with a clear action.
- [ ] Rerun; manually inspect an unresolved and a resolved function, source excerpts, and the replacement impact preview.
- [ ] Commit. Gate: a restarted worker resumes without duplicate business effects and no UI path creates two selected alternatives.

### T14 — Workbook generation and export checks

**Execution steps:** [T14 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t14-workbook-generation-and-export-integrity).

**Files:** Create `src/busconfig/export/workbook.py`, `tests/integration/test_workbook_export.py`.

**Consumes:** Exact decision revision, validation report and approval state. **Produces:** `render_workbook(...) -> ExportManifest` and five-sheet exports.

- [ ] Write tests for selected-count round trips, duplicate selected rows, wrong revision IDs, unresolved draft labeling, approved-versus-new-draft separation, and formula-like source text.
- [ ] Run `uv run pytest tests/integration/test_workbook_export.py -q`; observe failures.
- [ ] Implement workbook layout, stable IDs, evidence/issue links, manifest, text-safe cells and reload validation.
- [ ] Rerun; visually inspect long Chinese descriptions, wrapped cells, filters, symbols and legend in a spreadsheet viewer.
- [ ] Commit. Gate: exported choices exactly match the pinned revision and an unresolved draft can never be presented as approved.

### T15 — Full evaluation and retrieval ablations

**Execution steps:** [T15 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t15-full-evaluation-and-retrieval-experiments).

**Files:** Create `evals/runners/run_suite.py`, `evals/runners/ablate_retrieval.py`, `tests/acceptance/test_release_gates.py`, and experiment report templates.

**Consumes:** Frozen cases E01–E42, independent gold outcomes, full application adapters. **Produces:** case-level results, aggregate metrics with denominators, and reproducible experiment manifests.

- [ ] Add all remaining matrix cases and write tests that deliberately corrupt a decision, duplicate a function selection, or hide a residual demand; the independent evaluator must detect each corruption.
- [ ] Run `uv run pytest tests/acceptance/test_release_gates.py -q`; confirm the evaluator's negative controls fail when detection is removed.
- [ ] Implement the paired discovery and fixed-pool decision comparisons in §18.5, including raw row scores, per-order context usage, abstentions and the default-selection gate.
- [ ] Run `uv run python -m evals.runners.run_suite --split test`; record outcomes without tuning on the test set. Run ablations on development/validation partitions first.
- [ ] Commit the evaluator, manifests and reproducible reports. Gate: demonstrate useful completion and correct abstention together, not only fewer errors.

### T16 — Deployment, restore, and learning handoff

**Execution steps:** [T16 detailed steps, prompts, and verification](Bus_Config_AI_Implementation_Plan_EN_v1.md#t16-deployment-restore-and-learning-handoff).

**Files:** Create `deploy/compose.yaml`, `docs/runbook.md`, `docs/environment.md`, `docs/demo.md`, and `tests/acceptance/test_restore.py`.

**Consumes:** Tested application, pinned dependencies, synthetic demo dataset. **Produces:** local/server deployment procedure and a restored reproducible example.

- [ ] Write `test_restore_preserves_approved_revision` to compare decision hashes, selections, approval and export manifest before and after a restore.
- [ ] Record actual machine resources and model access; configure isolated application/model environments and authenticated server access where needed.
- [ ] Implement backup/restore instructions and the disposable restore harness. Run `uv run pytest tests/acceptance/test_restore.py -q` against a clean destination.
- [ ] Demonstrate one correct selection, one same-function composition rejection, one evidence conflict, and one reviewed replacement with fresh validation.
- [ ] Commit the deployment/runbook materials. Gate: another engineer can reproduce the demonstration using synthetic data and understand every unresolved limitation.

### Learning checkpoints

After M0, explain why single-choice selection and many-to-many coverage are compatible. After M1, trace one wrong candidate from source fact to failing check without a model. After M2, demonstrate a measured improvement attributable to model assistance. After M3, reproduce a stale-edit rejection and an invalidated approval. After M4, explain what synthetic evaluation does and does not establish.

Do not set a calendar deadline from this document alone. Estimate task effort after M0 and the native parsing spike reveal actual document variability and available development time. The previous learning roadmap remains useful for concepts, but its task order and cardinality assumptions must be read through this revision.

## 22. Worked synthetic decision examples

### 22.1 One compatible choice

An invented order requires function `DEMO-F-REGEN`: a momentary two-position switch controls the sequence `0 → 1 → 2 → 3 → 4 → 0`, using binding `CTRL-M/J14`. The three sources agree on that scope and the required behavior has been verified.

| Candidate | Switch | Binding | Controlled sequence | Result |
|---|---|---|---|---|
| `DEMO-C-R1` | Momentary | CTRL-M/J14 | 0 → 1 → 2 → 3 → 0 | Fails sequence |
| `DEMO-C-R2` | Momentary | CTRL-M/J14 | 0 → 1 → 2 → 3 → 4 → 0 | Passes the stated example requirements |
| `DEMO-C-R3` | Latching | CTRL-M/J14 | 0 → 1 → 2 → 3 → 4 → 0 | Fails switch behavior |

Assuming all other applicable checks and dependencies pass, the proposal selects only `DEMO-C-R2` for `DEMO-F-REGEN`. R1 and R3 remain visible as rejected candidates with evidence-backed differences.

Example explanation: “The current-order switch entry specifies momentary operation and the five-state cycle. The current pin definition binds this switch to CTRL-M/J14. R2 matches these reviewed conditions. R1 has a four-state cycle; R3 requires a latching switch.” This is a decision summary, not a substitute for the underlying check records.

### 22.2 Complementary alternatives cannot be combined

An invented function `DEMO-F-INTERLOCK` must react to both conditions A and B. Configuration I1 responds to A only; I2 responds to B only. There is no configuration implementing both in the pinned library.

The forbidden output is `{I1, I2}` for `DEMO-F-INTERLOCK`. Even if their descriptions appear to cover both conditions together, the user's single-choice rule prohibits that selection.

The valid draft has no selection for that function and an issue explaining the uncovered behavior. If the requirements and exhaustive family search are confirmed, a reviewer may confirm a library gap. A newly engineered I3 could later be authored and released; the matching system does not pretend I3 already exists.

### 22.3 Different functions may participate in one behavior

Suppose `DEMO-F-REQUEST-DETECT` has a selected configuration D1, and `DEMO-F-STOP-INDICATOR` has a selected configuration L1. They are different maintained functions. A passenger request behavior may rely on both, provided their signal connection, timing, reset and output behavior are compatible.

There is one selected configuration for each function. A coverage link can reference both, but the composition check must verify the signal flow and shared assumptions. This does not relax the one-choice invariant.

### 22.4 Physical instances conflict under one function

A front device requires the momentary alternative and a rear device requires the latching alternative of the same function. No single configuration supports both, and the library does not define separate front and rear functions.

The system reports `CONFLICT` or a potential library gap. It does not create `function_front` and `function_rear` IDs automatically. The next action is to confirm the order interpretation or request a maintained catalog/configuration change.

### 22.5 Replacement and stale approval

Revision R10 selects A for function F and is approved. New evidence requires B. The working update creates R11 with B only; R10 remains a historical approved snapshot. R11 is unapproved until affected checks and human review complete.

If a second reviewer submits a change based on R10 after the working pointer has moved to R11, the service returns a stale-revision conflict. It cannot append a second selection or silently overwrite R11.

## 23. Superseded assumptions and remaining domain mappings

### 23.1 Explicit corrections to earlier proposals

| Earlier wording or possible interpretation | Corrected design |
|---|---|
| Several configurations might jointly cover one function | Alternatives of the same function may never be selected together |
| Per-function selection quantity can vary freely | Every configurable function has maximum one selection in an order decision |
| Physical instances might have separate configuration choices | Instances preserve evidence scope; they do not multiply selection slots |
| Many-to-many coverage implies unrestricted selection | Coverage remains many-to-many; cardinality stays zero-or-one per function |
| A high-ranked candidate should always be selected | Unknown, ambiguous, incompatible and unmatched cases may have zero selections |
| A checkbox-style output can represent any combination | Output may list every alternative, but selection count is enforced per function |
| A model explanation establishes why a choice is valid | Evidence, explicit checks and versioned review establish the basis; model prose summarizes it |

The earlier plan's general approach to synthetic data, deterministic baselines, model assistance, human review, and evaluation remains useful. Its same-function composition examples and any unrestricted per-function cardinality assumptions are superseded by this document.

### 23.2 Domain mappings to establish during knowledge onboarding

These do not block the architecture. They are required mappings for any concrete function family before that family's results can be approved:

- Which library nodes own mutually exclusive configurations, independent of heading depth.
- Which source formats and revision marks identify current effective text.
- Which fields have approved authority or inheritance relationships.
- Which source inventories are complete enough to support explicit absence.
- Which configuration definitions contain unresolved parameters; the first release supports fixed revisions and flags parameter-dependent candidates as unsupported until a later explicit instantiation design.
- Which behavior clauses can be verified automatically and which need manual engineering evidence.
- Which cross-function dependencies and resource-sharing arrangements are valid.
- The exact business export symbol legend, if compatibility with the existing workbook requires one.

Use explicit synthetic definitions for the personal project. Do not infer company-wide policies from one photographed example. Unmapped source conditions remain issues rather than hidden defaults.

### 23.3 Decisions intentionally deferred to implementation

Select exact package versions, model size, inference backend and machine sizing after the environment check. Choose a simple UI implementation consistent with the contracts; extensive visual design is not required to validate the decision workflow. Add vector retrieval, a specialized solver, or a dedicated evaluation service only after a measured bottleneck justifies it.

No additional business approval is needed to obey the user's corrected single-choice rule. If a future requirement genuinely needs multiple alternatives of the same maintained function, that would be a business-rule change and must not be smuggled in as an implementation optimization.

## 24. References and glossary

### 24.1 Primary technical references

These references support library/database behavior, not claims about company implementation or expected system accuracy. Accessed November 16, 2026. Pin and test the concrete versions used during implementation.

- **R01:** [PostgreSQL — Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html). Unique and foreign-key constraints used for selection cardinality and ownership.
- **R02:** [PostgreSQL — Explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html). Row locks used for coordinated decision-pointer updates.
- **R03:** [openpyxl — Excel reader](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html). Formula/cache selection and rich-text loading behavior.
- **R04:** [python-docx — Document objects](https://python-docx.readthedocs.io/en/latest/api/document.html). Document traversal and revision-mark limitations.
- **R05:** [Pydantic — Strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/). Type validation without treating coercion as domain validation.
- **R06:** [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts). Human review, checkpointed resume and repeated-node side effects.

### 24.2 Terminology

| Term | Meaning in this design |
|---|---|
| Function | Maintained configurable entity owning alternative configurations |
| Function instance | Physical or logical scope such as a particular device; not an extra selection slot |
| Configuration | One alternative implementation for one function |
| Configuration revision | Immutable version of that alternative's definition |
| Order snapshot | Frozen order context and source documents |
| Knowledge snapshot | Frozen catalog, attributes, configuration revisions and approved rules |
| Evidence packet | Scoped order facts, source excerpts, candidates, checks and unanswered questions |
| Candidate | An alternative being considered; not necessarily selected |
| Selection | One chosen configuration revision in a function's single selection slot |
| Demand | Explicit or approved-rule-derived need for behavior/function |
| Coverage | Verified relationship between required behavior and the selected configurations that implement it |
| Unknown | Evidence or verification is insufficient; neither true nor false |
| Library gap | Reviewed absence of a suitable implementation within a defined, searched library snapshot |
| Decision revision | Versioned order assessment and selection result |
| Approval | Human acceptance of one exact eligible decision and validation result |

### 24.3 Design completion checklist

- [x] Apply the user-confirmed maximum-one rule to model, workflow, storage, UI and export design.
- [x] Preserve independent order-demand discovery alongside catalog-led assessment.
- [x] Specify source roles, blank handling, versioning and evidence conflicts.
- [x] Define attribute/experience authoring formats and their separate responsibilities.
- [x] Define deterministic and model responsibilities, bounded failures and review behavior.
- [x] Specify transactional replacement, stale-edit handling and approval invalidation.
- [x] Define output sheets, auditable explanations and nonprobabilistic initial confidence.
- [x] Define independent evaluation, cardinality regression cases and implementation gates.
- [ ] Implement and validate the application against these contracts in a new repository.

The checked items refer to design coverage only. No software, model benchmark, database migration or deployment is claimed complete by this document.
