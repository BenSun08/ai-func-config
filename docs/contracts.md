# Shared domain contracts

Schema version: **1.0**. Implementation: `src/busconfig/domain/contracts.py`.
Design references: detailed design §§2, 5, 6, 8, 10.3, 12, 13.2, 14.1 and 20.2.
This is the T01.3 contract baseline, not a parser, planner, model client, database
or independent whole-order validator implementation.

## Validation boundary and compatibility

Use model constructors, `model_validate`, or `model_validate_json` for inputs.
JSON input rejects duplicate object keys before Pydantic can overwrite them.
Unknown fields, type coercions and nonfinite numeric values are rejected.
`model_copy(update=...)` also validates; it cannot silently bypass the hash or
field contracts. Pydantic's explicitly unsafe `model_construct`, direct access to
object internals and `object.__setattr__` are not supported input paths.

T01.2 selection inputs and `validate_selection_rows` retain their interfaces.
That function returns an ordinary typed map; `DecisionPayload` and `SelectionPlan`
take an immutable copy. External bulk selections must enter as a **row list**.
The complete list is validated and duplicate functions rejected before building
the map, including identical rows and different revisions of the same configuration.
Already serialized maps are accepted for validated record reconstruction; they
cannot recover duplicates lost by a caller before this boundary.

The necessary Python-level compatibility change is `FactValue`: validated arrays
are now tuples and objects are `FrozenMap` instances. JSON remains arrays/objects,
and serialization returns detached mutable output data. The existing test caller
was updated to expect an immutable sequence. Instances retain evidence scope and
an optional catalog function reference; they never add selection keys.

## Identity and native provenance

- `Identifier`, `FunctionId`, `ConfigRevisionId`, `DecisionRevisionId`,
  `SourceDocumentId`, `SourceBlockId`, `OrderSnapshotId` and `KnowledgeSnapshotId`
  are strict opaque strings. They reject empty, whitespace-containing and
  comma-separated values. A source location or device label is not a function ID.
- `Digest` is `sha256:` followed by 64 lowercase hex digits. A placeholder such as
  `sha256:example-only` is invalid.
- `SourceDocument` pins declared role, business revision, byte hash, original path,
  parser version and layout profile. Unicode paths are retained without guessing
  the role from the filename.
- `XlsxLocator` retains sheet and native A1 cell references. `DocxLocator` retains
  heading path, zero-based block/table/cell indexes and an OOXML path. Cell lists,
  heading paths and nested table paths retain structural order.
- `TextSpan` uses zero-based Unicode code-point offsets, with an exclusive end
  within the located native text. Negative or reversed spans are invalid. No
  rendered page number substitutes for native identity.
- `SourceBlock` retains the document ID/hash, locator, exact raw text, formatting
  data and `CURRENT | DELETED | SUPERSEDED | UNRESOLVED` effective status.
- `source_block_id(document, locator)` returns `SRC-` plus SHA-256 of the canonical
  object containing schema version, document ID, document byte hash, business
  revision and locator. Same identity inputs produce the same ID. Changed content,
  revision or location produces another ID. Original filename is not an identity
  component, so moving the same source does not manufacture different evidence.
- `validate_source_ids(documents, blocks, assertions)` rejects every reused ID
  across these inputs, even identical repeated rows, before constructing a lookup.
  It also verifies block/document hashes and assertion/block references. For a
  generated ID (`SRC-` and 64 lowercase hex digits), it recomputes the ID from
  the declared document and locator. Opaque source IDs retain the reference checks. Importers
  must include previously registered records when checking reuse across imports;
  this function is not a durable global ID registry.

## Values, issues and evidence

Facts use exactly `KNOWN`, `MISSING`, `NOT_APPLICABLE`, and `CONFLICT`. `KNOWN`
requires a non-null value. Unresolved/inapplicable states cannot carry a resolved
value. Booleans, integers, finite floats, strings and nested structures retain
their types. Assertions, resolved facts and attribute values also preserve those
types in equality and set membership, including inside nested values.

Raw source text retains the difference between absent text, an observed empty
string and `/`. These contracts do not infer a value state by inspecting arbitrary
strings. T03 owns standalone-slash normalization; `0/1/2/3` is preserved.
Numeric unit/decimal normalization belongs to the explicit typed producer contract,
not to a heuristic inside the hash encoder. Schema 1.0 accepts finite JSON numbers,
not arbitrary Python Decimal/custom objects, and never guesses unit equivalence.

`SourceAssertion` retains source block IDs, current/historical/planned scope,
origin and review status. The default origin is `UNSPECIFIED`, not an invented
native/human origin. `ResolvedFact` pins the order snapshot, contributing assertion
IDs, resolution method and review state. Configuration `AttributeValue` records
also require explicit value state, evidence IDs and review status.

An interpretation, linked order or evidence context accepts facts and requirements
only for its pinned order snapshot. Within a knowledge snapshot, all revisions
of a stable configuration ID must belong to the same catalog function.

Every block cited by a proposed assertion needs a supporting span. A proposal
that contains requirements or links (including alternative links) also needs
source spans. Checking those spans against actual source text requires the
producer's source lookup.

`Issue` contains ID, code, severity, scope, evidence IDs, resolution target and a
message. The initial conservative policy is fixed: `METADATA_NOTE` is informational;
every other code is blocking, including unknown codes. Callers cannot downgrade a
blocking code. A future policy change must be explicit, versioned and tested.

## Immutable decision and independent report hashes

`DecisionRevision` is an envelope with a revision ID, a `DecisionPayload`, and a
separate `payload_hash`. The payload contains:

- schema version, pinned order/knowledge snapshot IDs, input generation and parent;
- one scalar selected configuration revision per function;
- typed facts, function assessments, issues and evidence references.

The payload cannot contain lifecycle status, a validation report, export timestamp
or its own hash. A revision cannot parent itself. Facts must belong to its pinned
order snapshot. All nested values are immutable through supported public APIs.

Canonical encoding version 1.0 is Python JSON serialized as UTF-8, with sorted
object keys, `ensure_ascii=False`, separators `,` and `:`, and no NaN/infinity.
No Unicode normalization or whitespace trimming is performed. Numeric type is
preserved (`false`, `0`, and `0.0` differ); this is a project encoding, not a claim
of RFC 8785 conformance.

ID-indexed payload facts, assessments and issues are sorted by their IDs; duplicate
IDs are rejected. Evidence IDs, contributing assertion IDs, candidate memberships
and check reference sets are sorted. Semantic sequences (for example a controlled
state sequence, source fragments, questions or counterexample traces) retain order.
`payload_hash = sha256(canonical_json(payload))`; the revision envelope ID and its
hash field are outside that hash input. Changed facts, snapshots, generation,
parent, assessments, issues or selections change the payload hash.

`ValidationReport` is a separate immutable record with decision ID, payload hash,
validator version, typed checks, issues, verification evidence, eligibility and
its own report hash. Check/issue records and reference sets are canonicalized.
`report_hash` covers the complete report except `report_hash` itself. Constructing
a later report cannot alter the decision. Blocking issues or FAIL/UNKNOWN checks
cannot be labeled approval-eligible.

Constructors compute omitted hashes. Supplied hashes are checked and a mismatch
raises `HASH_MISMATCH`. `validate_report_binding` checks both decision ID and exact
payload hash, rejecting stale reports. Hashes detect changed content; they do not
authenticate its author, validate all engineering claims or replace T09/T11
whole-order/persistence checks. Approval binds both hashes; no approval service is
implemented here.

## Typed result inventory from design §20.2

These are data contracts. Their producer algorithms remain in the tasks named by
the implementation plan. Required completeness/search fields have no optimistic
default. Schema validation is not evidence that a result was correctly produced.

| Boundary | Result and preserved content |
| --- | --- |
| Native parsing | `ParseResult`: document, blocks, assertions, issues, `Completeness`; validates source references and ID reuse. |
| Knowledge compilation | `KnowledgeCompilation`: draft `KnowledgeSnapshot` and issues; snapshot pins exact catalog/config/attribute/rule/composition membership. No publication operation. |
| Rule evaluation | `RuleEvaluation`: three-valued rule outcomes, derived requirements, branch guards and issues. |
| Interpretation/linking | `OrderInterpretation`, `LinkedOrder`: facts, requirements, instance scopes, unresolved items, issues and explicit links. |
| Evidence gathering | `OrderEvidenceContext`: pinned order/knowledge/function, requirements, facts, links, bindings, source excerpts and questions; no candidate-check field. |
| Retrieval/checking | `CandidateSet` holds full `ConfigRevision` records and search metadata. `CandidateAssessment` holds checks and evidence sufficiency, never selections. |
| Comparison input | `EvidencePacket`: context, full candidates, assessments, full `RuleRevision` records including exceptions, and obligations. |
| Verification | `BehaviorCheck`, `CompositionCheck`: outcomes, counterexamples, verification scope, allocated obligations, connection checks and remaining unknowns. NOT_APPLICABLE requires explicit false applicability. |
| Model extraction/linking | `OrderExtractionProposal`, `LinkProposalSet`: exact source spans, alternatives, issues and unreviewed proposals. They cannot claim human confirmation. |
| Model adapter/comparison | `ModelRequest`, `ModelResponse`, `SemanticComparison` are separate. Semantic outcomes are AGREEMENT/DIFFERENCE/INSUFFICIENT_EVIDENCE; recommendations SUPPORT/REJECT/REVIEW are advisory, not candidate check outcomes. No client exists. |
| Assessment preparation | `AssessmentPreparation`: assessments keyed by context hash, guards, obligation allocations, completeness and issues. |
| Selection | `SelectionPlan`: scalar map, assessments, coverage claims, active derived requirements, dependency edges, issues and search-completeness metadata. Budget exhaustion cannot imply complete search. |
| Validation/revision | `ValidationReport`, `DecisionRevision`: independent hashed records as described above. |
| Approval/export | `Approval` binds decision/payload/validation hashes and reviewer/time; `ExportManifest` pins those hashes, destination, file hash and DRAFT/APPROVED label. No file generation or approval execution. |

`Requirement`, `SignalBinding`, `EntityLink`, `ObligationAllocation`, `BranchGuard`,
`CoverageLink`, `DependencyEdge`, `SourceSpan` and the snapshot types provide typed
supporting records. Source behavior, predicates and effects remain inert text;
future compilers/verifiers must build and validate their restricted representations
before evaluating them. Input commands, verifier ASTs and execution policies are
completed in their owning tasks before consumers are implemented, with schema and
caller updates where necessary.

Generate JSON Schema from a model with `Model.model_json_schema()`. The schema
version must change for incompatible serialization/hash changes; existing stored
hashes must not be silently recomputed under a different convention.

## Serialized synthetic examples

The following records are shape-valid illustrations, not a complete released
order/knowledge dataset. Their pinned IDs and assertion references illustrate the
boundaries. The source byte hash is computed from `b"synthetic document bytes"`,
not from a real workbook. Decision and report hashes are computed from these exact
records. The draft has a required unresolved function and no selection.

### SourceDocument

```json
{
  "schema_version": "1.0",
  "document_id": "DOC-DEMO-PINS-R1",
  "role": "PIN_DEFINITION",
  "business_revision": "R1",
  "byte_hash": "sha256:cd0ae5ea7c937481dba1c94d53e3fc764d0c052760463b7eb24a73c88e2fe050",
  "original_path": "synthetic/合成引脚.xlsx",
  "layout_profile": "demo-pins-v1",
  "parser_version": "demo-parser-v1"
}
```

### SourceBlock

```json
{
  "schema_version": "1.0",
  "block_id": "SRC-3692f31f1ba069fd155910c544facd7d04a2d19c68f4a7777306347d75fcd96c",
  "document_id": "DOC-DEMO-PINS-R1",
  "document_hash": "sha256:cd0ae5ea7c937481dba1c94d53e3fc764d0c052760463b7eb24a73c88e2fe050",
  "locator": {
    "kind": "xlsx",
    "sheet": "Pins",
    "cells": [
      "G12"
    ],
    "text_span": {
      "start": 0,
      "end": 4
    }
  },
  "raw_text": "demo",
  "effective_status": "CURRENT",
  "formatting": {}
}
```

### DecisionRevision

```json
{
  "schema_version": "1.0",
  "decision_revision_id": "DECISION-DEMO-1",
  "payload": {
    "schema_version": "1.0",
    "order_snapshot_id": "ORDER-DEMO-R1",
    "knowledge_snapshot_id": "KNOWLEDGE-DEMO-R1",
    "input_generation": 1,
    "parent_revision_id": null,
    "selections": {},
    "facts": [
      {
        "fact_id": "FACT-DEMO-1",
        "order_snapshot_id": "ORDER-DEMO-R1",
        "subject_id": "DEVICE-DEMO-1",
        "property": "observed_state",
        "value_state": "KNOWN",
        "value": {
          "enabled": false,
          "count": 0,
          "sequence": [
            0,
            1
          ]
        },
        "assertion_ids": [
          "ASSERT-DEMO-1"
        ],
        "resolution_method": "SYNTHETIC_FIXTURE",
        "review_state": "UNREVIEWED"
      }
    ],
    "assessments": [
      {
        "function_id": "FUNC-DEMO-1",
        "demand_state": "REQUIRED",
        "resolution": "NEEDS_EVIDENCE",
        "candidate_revision_ids": [
          "CONFIG-DEMO-1-R1"
        ],
        "preferred_config_revision_id": null,
        "unresolved_questions": [
          "Which synthetic binding applies?"
        ]
      }
    ],
    "issues": [
      {
        "issue_id": "ISSUE-DEMO-1",
        "code": "UNKNOWN_REQUIRED_FIELD",
        "severity": "BLOCKING",
        "scope": "FUNC-DEMO-1",
        "evidence_ids": [
          "SRC-3692f31f1ba069fd155910c544facd7d04a2d19c68f4a7777306347d75fcd96c"
        ],
        "resolution_target": "Confirm the synthetic binding",
        "message": "Synthetic evidence is incomplete."
      }
    ],
    "evidence_ids": [
      "SRC-3692f31f1ba069fd155910c544facd7d04a2d19c68f4a7777306347d75fcd96c"
    ]
  },
  "payload_hash": "sha256:441c7ec11fa7023dea24a7b1721595217f8422c022afeef556d84d8a231862bf"
}
```

### ValidationReport

```json
{
  "schema_version": "1.0",
  "report_id": "REPORT-DEMO-1",
  "decision_revision_id": "DECISION-DEMO-1",
  "payload_hash": "sha256:441c7ec11fa7023dea24a7b1721595217f8422c022afeef556d84d8a231862bf",
  "validator_version": "demo-validator-v1",
  "checks": [],
  "issues": [
    {
      "issue_id": "ISSUE-DEMO-1",
      "code": "UNKNOWN_REQUIRED_FIELD",
      "severity": "BLOCKING",
      "scope": "FUNC-DEMO-1",
      "evidence_ids": [
        "SRC-3692f31f1ba069fd155910c544facd7d04a2d19c68f4a7777306347d75fcd96c"
      ],
      "resolution_target": "Confirm the synthetic binding",
      "message": "Synthetic evidence is incomplete."
    }
  ],
  "evidence_ids": [
    "SRC-3692f31f1ba069fd155910c544facd7d04a2d19c68f4a7777306347d75fcd96c"
  ],
  "approval_eligible": false,
  "report_hash": "sha256:d19b92f1ea5d62bafd28ac97b1e2e18fd59ce43eedb45bc0949c68c9de6dceb4"
}
```
