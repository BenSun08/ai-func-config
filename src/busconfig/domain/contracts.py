"""Shared domain types from design §§2, 8 and 20; no planner/model dependencies."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from busconfig.domain.immutable import FrozenMap, immutable_sequences
from busconfig.domain.serialization import canonical_hash, reject_duplicate_json_keys

# Opaque IDs are validated, never split, trimmed or manufactured from device scope.
Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[^\s,]+$")]
FunctionId = Identifier
ConfigRevisionId = Identifier
DecisionRevisionId = Identifier
SelectionMap = dict[FunctionId, ConfigRevisionId]
SourceDocumentId = Identifier
SourceBlockId = Identifier
OrderSnapshotId = Identifier
KnowledgeSnapshotId = Identifier
Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
Nonblank = Annotated[str, StringConstraints(pattern=r"\S")]
SCHEMA_VERSION = "1.0"

# Typed JSON-compatible values include structured bindings, not only scalars.
type FactValue = Annotated[
    bool | int | float | str | tuple[FactValue, ...] | FrozenMap[str, FactValue] | None,
    BeforeValidator(immutable_sequences),
]


class ValueState(StrEnum):
    KNOWN = "KNOWN"
    MISSING = "MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONFLICT = "CONFLICT"


class DomainModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )

    @classmethod
    def model_validate_json(cls, json_data, **kwargs):
        reject_duplicate_json_keys(json_data)
        return super().model_validate_json(json_data, **kwargs)

    def model_copy(self, *, update=None, deep=False):
        # Pydantic's default copy(update=...) bypasses validation. Public domain
        # copies must instead recheck nested contracts and any supplied hashes.
        values = {field: getattr(self, field) for field in type(self).model_fields}
        values.update(update or {})
        return type(self).model_validate(values)


class SelectionInput(DomainModel):
    """One external selected row; null/instance keys are not selected rows."""

    function_id: FunctionId
    config_revision_id: ConfigRevisionId


class Selection(SelectionInput):
    """A selected row belonging to exactly one decision revision."""

    decision_revision_id: DecisionRevisionId


class SelectionRequest(DomainModel):
    """Design §16.2 request body; the route supplies the function ID.

    Explicit null means clear, while an omitted field is malformed. Applying the
    request, checking ownership and persisting revisions belong to later tasks.
    """

    expected_decision_revision_id: DecisionRevisionId
    config_revision_id: ConfigRevisionId | None
    reason: Annotated[str, StringConstraints(pattern=r"\S")]


class FunctionInstance(DomainModel):
    """Evidence scope, optionally mapped to a maintained catalog function."""

    instance_id: Identifier
    scope: Annotated[str, StringConstraints(pattern=r"\S")]
    function_id: FunctionId | None = None


class SourceAssertion(DomainModel):
    """Design §8.1 assertion fields with explicit §8.2 value state.

    Block IDs retain provenance without substituting text for source identity.
    Source-document versions/locators are retained through the referenced blocks.
    Raw text distinguishes an observed blank from absent text. Interpreting a
    standalone slash as a blank is a parser responsibility, not value coercion.
    """

    assertion_id: Identifier
    subject_id: Identifier
    property: Annotated[str, StringConstraints(pattern=r"\S")]
    source_block_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    statement_scope: Literal["CURRENT_ORDER", "HISTORICAL_REFERENCE", "PLANNED_USE"]
    value_state: ValueState
    value: FactValue = None
    raw_text: str | None = None
    origin: Literal[
        "UNSPECIFIED",
        "NATIVE_DOCUMENT",
        "INHERITED",
        "DEFAULT",
        "MODEL_PROPOSAL",
        "HUMAN_CONFIRMED",
    ] = "UNSPECIFIED"
    review_state: Literal["UNREVIEWED", "CONFIRMED", "REJECTED"] = "UNREVIEWED"

    @model_validator(mode="after")
    def check_value_state(self) -> Self:
        if self.value_state == ValueState.KNOWN:
            if self.value is None:
                raise ValueError("KNOWN requires an explicit non-null value")
        elif self.value is not None:
            raise ValueError("Only KNOWN can carry a resolved value")
        return self


class VersionedModel(DomainModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION


class TextSpan(DomainModel):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError("Text span end precedes start")
        return self


class XlsxLocator(DomainModel):
    kind: Literal["xlsx"] = "xlsx"
    sheet: Nonblank
    cells: Annotated[
        tuple[Annotated[str, StringConstraints(pattern=r"^[A-Z]+[1-9][0-9]*$")], ...],
        Field(min_length=1),
    ]
    text_span: TextSpan | None = None


class DocxLocator(DomainModel):
    kind: Literal["docx"] = "docx"
    heading_path: tuple[str, ...] = ()
    block_index: Annotated[int, Field(ge=0)]
    xml_path: Nonblank
    table_path: tuple[Annotated[int, Field(ge=0)], ...] = ()
    cell: tuple[Annotated[int, Field(ge=0)], Annotated[int, Field(ge=0)]] | None = None
    text_span: TextSpan | None = None


SourceLocator = Annotated[XlsxLocator | DocxLocator, Field(discriminator="kind")]


class SourceDocument(VersionedModel):
    document_id: SourceDocumentId
    role: Nonblank
    business_revision: Nonblank
    byte_hash: Digest
    original_path: Nonblank
    layout_profile: Identifier
    parser_version: Nonblank


class SourceBlock(VersionedModel):
    block_id: SourceBlockId
    document_id: SourceDocumentId
    document_hash: Digest
    locator: SourceLocator
    raw_text: str
    effective_status: Literal["CURRENT", "DELETED", "SUPERSEDED", "UNRESOLVED"]
    formatting: FrozenMap[str, FactValue] = Field(default_factory=lambda: FrozenMap({}))


class ResolvedFact(DomainModel):
    fact_id: Identifier
    order_snapshot_id: OrderSnapshotId
    subject_id: Identifier
    property: Nonblank
    value_state: ValueState
    value: FactValue = None
    assertion_ids: tuple[Identifier, ...]
    resolution_method: Nonblank
    review_state: Literal["UNREVIEWED", "CONFIRMED", "REJECTED"]

    @field_validator("assertion_ids")
    @classmethod
    def canonical_references(cls, value):
        return sorted_ids(value)

    @model_validator(mode="after")
    def check_value_state(self) -> Self:
        if (self.value_state == ValueState.KNOWN) != (self.value is not None):
            raise ValueError("Only KNOWN has a non-null resolved value")
        return self


def unique_sorted(records, key):
    identities = [getattr(record, key) for record in records]
    if len(identities) != len(set(identities)):
        raise ValueError("DUPLICATE_ID")
    return tuple(sorted(records, key=lambda record: getattr(record, key)))


def sorted_ids(values):
    if len(values) != len(set(values)):
        raise ValueError("DUPLICATE_ID")
    return tuple(sorted(values))


class Issue(DomainModel):
    issue_id: Identifier
    code: Nonblank
    severity: Literal["BLOCKING", "INFO"] = "BLOCKING"
    scope: Identifier
    evidence_ids: tuple[Identifier, ...]
    resolution_target: Nonblank
    message: Nonblank

    @model_validator(mode="after")
    def severity_policy(self) -> Self:
        expected = "INFO" if self.code == "METADATA_NOTE" else "BLOCKING"
        if self.severity != expected:
            raise ValueError("Issue severity cannot be downgraded")
        return self

    _evidence = field_validator("evidence_ids")(sorted_ids)


class FunctionAssessment(DomainModel):
    function_id: FunctionId
    demand_state: Literal["REQUIRED", "NOT_REQUIRED", "UNDETERMINED"]
    resolution: Literal[
        "PROPOSED",
        "EXCLUDED",
        "NEEDS_EVIDENCE",
        "AMBIGUOUS_CHOICE",
        "CONFLICT",
        "NO_MATCH_FOUND",
        "LIBRARY_GAP_CONFIRMED",
    ]
    candidate_revision_ids: tuple[ConfigRevisionId, ...]
    preferred_config_revision_id: ConfigRevisionId | None
    unresolved_questions: tuple[str, ...] = ()

    _candidates = field_validator("candidate_revision_ids")(sorted_ids)

    @model_validator(mode="after")
    def preferred_is_candidate(self) -> Self:
        if (
            self.preferred_config_revision_id is not None
            and self.preferred_config_revision_id not in self.candidate_revision_ids
        ):
            raise ValueError("Preferred configuration is not a candidate")
        return self


class CandidateCheck(DomainModel):
    check_id: Identifier
    config_revision_id: ConfigRevisionId
    requirement_ids: tuple[Identifier, ...]
    outcome: Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
    comparator: Nonblank
    evidence_ids: tuple[Identifier, ...]
    counterexample: FactValue = None
    applicable: bool | None = None

    _references = field_validator("requirement_ids", "evidence_ids")(sorted_ids)

    @model_validator(mode="after")
    def explicit_applicability(self) -> Self:
        if self.outcome == "NOT_APPLICABLE" and self.applicable is not False:
            raise ValueError("NOT_APPLICABLE requires an explicit false applicability predicate")
        return self


class DecisionPayload(VersionedModel):
    order_snapshot_id: OrderSnapshotId
    knowledge_snapshot_id: KnowledgeSnapshotId
    input_generation: Annotated[int, Field(ge=0)]
    parent_revision_id: DecisionRevisionId | None
    selections: FrozenMap[FunctionId, ConfigRevisionId]
    facts: tuple[ResolvedFact, ...]
    assessments: tuple[FunctionAssessment, ...]
    issues: tuple[Issue, ...]
    evidence_ids: tuple[Identifier, ...]

    @field_validator("selections", mode="before")
    @classmethod
    def external_rows(cls, value):
        if isinstance(value, list):
            from busconfig.domain.invariants import validate_selection_rows

            return validate_selection_rows(value)
        return value

    _evidence = field_validator("evidence_ids")(sorted_ids)

    @field_validator("facts", "assessments", "issues")
    @classmethod
    def indexed_records(cls, value, info):
        return unique_sorted(
            value,
            {"facts": "fact_id", "assessments": "function_id", "issues": "issue_id"}[
                info.field_name
            ],
        )

    @model_validator(mode="after")
    def fact_scope(self) -> Self:
        if any(fact.order_snapshot_id != self.order_snapshot_id for fact in self.facts):
            raise ValueError("Fact belongs to another order snapshot")
        return self


class DecisionRevision(VersionedModel):
    decision_revision_id: DecisionRevisionId
    payload: DecisionPayload
    payload_hash: Digest | None = None

    @model_validator(mode="after")
    def verify_hash(self) -> Self:
        if self.payload.parent_revision_id == self.decision_revision_id:
            raise ValueError("SELF_PARENT_REVISION")
        digest = canonical_hash(self.payload)
        if self.payload_hash is not None and self.payload_hash != digest:
            raise ValueError("HASH_MISMATCH")
        object.__setattr__(self, "payload_hash", digest)
        return self


class ValidationReport(VersionedModel):
    report_id: Identifier
    decision_revision_id: DecisionRevisionId
    payload_hash: Digest
    validator_version: Nonblank
    checks: tuple[CandidateCheck, ...]
    issues: tuple[Issue, ...]
    evidence_ids: tuple[Identifier, ...]
    approval_eligible: bool
    report_hash: Digest | None = None

    _evidence = field_validator("evidence_ids")(sorted_ids)

    @field_validator("checks", "issues")
    @classmethod
    def indexed_records(cls, value, info):
        return unique_sorted(value, "check_id" if info.field_name == "checks" else "issue_id")

    @model_validator(mode="after")
    def verify_hash(self) -> Self:
        if self.approval_eligible and (
            any(issue.severity == "BLOCKING" for issue in self.issues)
            or any(check.outcome in ("FAIL", "UNKNOWN") for check in self.checks)
        ):
            raise ValueError("Blocking findings cannot be approval eligible")
        digest = canonical_hash(self.model_dump(mode="json", exclude={"report_hash"}))
        if self.report_hash is not None and self.report_hash != digest:
            raise ValueError("HASH_MISMATCH")
        object.__setattr__(self, "report_hash", digest)
        return self


class Completeness(DomainModel):
    complete: bool
    supported_regions: tuple[str, ...]
    unsupported_regions: tuple[str, ...]
    mapped_columns: tuple[str, ...]
    unmapped_columns: tuple[str, ...]
    mandatory_sections_found: bool

    @model_validator(mode="after")
    def incomplete_regions(self) -> Self:
        if self.complete and (
            self.unsupported_regions or self.unmapped_columns or not self.mandatory_sections_found
        ):
            raise ValueError("Unsupported or missing mandatory input cannot be complete")
        return self


class ParseResult(VersionedModel):
    document: SourceDocument
    source_blocks: tuple[SourceBlock, ...]
    assertions: tuple[SourceAssertion, ...]
    issues: tuple[Issue, ...]
    completeness: Completeness

    @model_validator(mode="after")
    def source_identity(self) -> Self:
        from busconfig.domain.invariants import validate_source_ids

        validate_source_ids([self.document], list(self.source_blocks), list(self.assertions))
        return self


class Requirement(DomainModel):
    requirement_id: Identifier
    order_snapshot_id: OrderSnapshotId
    scope: Nonblank
    condition: str
    action: str
    timing: str | None
    source_assertion_ids: tuple[Identifier, ...]
    extraction_status: Literal["PROPOSED", "CONFIRMED", "UNRESOLVED"]


class OrderSnapshot(VersionedModel):
    snapshot_id: OrderSnapshotId
    order_id: Identifier
    input_generation: Annotated[int, Field(ge=0)]
    documents: tuple[SourceDocument, ...]
    context: FrozenMap[str, FactValue]

    @field_validator("documents")
    @classmethod
    def source_identity(cls, value):
        from busconfig.domain.invariants import validate_source_ids

        validate_source_ids(list(value), [])
        return unique_sorted(value, "document_id")


class AttributeValue(DomainModel):
    value_state: ValueState
    value: FactValue = None
    evidence_ids: tuple[Identifier, ...]
    review_state: Literal["UNREVIEWED", "CONFIRMED", "REJECTED"]

    @model_validator(mode="after")
    def explicit_value_state(self) -> Self:
        if (self.value_state == ValueState.KNOWN) != (self.value is not None):
            raise ValueError("Only KNOWN has a non-null attribute value")
        return self


class ConfigRevision(DomainModel):
    config_revision_id: ConfigRevisionId
    configuration_id: Identifier
    function_id: FunctionId
    revision: Nonblank
    behavior: str
    attributes: FrozenMap[str, AttributeValue]
    applicability: str
    source_block_ids: tuple[SourceBlockId, ...]


class RuleRevision(DomainModel):
    rule_revision_id: Identifier
    revision: Nonblank
    scope: Nonblank
    predicate: Nonblank
    effect: Nonblank
    exceptions: tuple[str, ...]
    evidence_ids: tuple[Identifier, ...]
    review_state: Literal["UNREVIEWED", "CONFIRMED", "REJECTED"]


class SignalBinding(DomainModel):
    binding_id: Identifier
    signal_role: Nonblank
    source_entity_id: Identifier
    target_entity_id: Identifier
    controller_id: Identifier | None
    network_id: Identifier | None
    interface: str | None
    polarity: str | None
    evidence_ids: tuple[Identifier, ...]


class KnowledgeSnapshot(VersionedModel):
    snapshot_id: KnowledgeSnapshotId
    function_ids: tuple[FunctionId, ...]
    config_revisions: tuple[ConfigRevision, ...]
    attribute_revision_ids: tuple[Identifier, ...]
    rule_revision_ids: tuple[Identifier, ...]
    composition_template_revision_ids: tuple[Identifier, ...]

    _membership = field_validator(
        "function_ids",
        "attribute_revision_ids",
        "rule_revision_ids",
        "composition_template_revision_ids",
    )(sorted_ids)

    @field_validator("config_revisions")
    @classmethod
    def unique_configs(cls, value):
        return unique_sorted(value, "config_revision_id")

    @model_validator(mode="after")
    def owners_in_catalog(self) -> Self:
        if any(config.function_id not in self.function_ids for config in self.config_revisions):
            raise ValueError("CONFIG_FUNCTION_MISMATCH")
        return self


class KnowledgeCompilation(VersionedModel):
    draft_snapshot: KnowledgeSnapshot
    issues: tuple[Issue, ...]


class EntityLink(DomainModel):
    link_id: Identifier
    source_entity_id: Identifier
    target_entity_id: Identifier
    relationship: Nonblank
    evidence_ids: tuple[Identifier, ...]
    method: Nonblank
    review_state: Literal["UNREVIEWED", "CONFIRMED", "REJECTED"]


class OrderInterpretation(VersionedModel):
    order_snapshot_id: OrderSnapshotId
    facts: tuple[ResolvedFact, ...]
    requirements: tuple[Requirement, ...]
    instances: tuple[FunctionInstance, ...]
    unresolved_items: tuple[str, ...]
    issues: tuple[Issue, ...]


class LinkedOrder(OrderInterpretation):
    links: tuple[EntityLink, ...]


class OrderEvidenceContext(LinkedOrder):
    knowledge_snapshot_id: KnowledgeSnapshotId
    function_id: FunctionId
    source_blocks: tuple[SourceBlock, ...]
    unanswered_questions: tuple[str, ...]
    bindings: tuple[SignalBinding, ...] = ()


class SearchMetadata(DomainModel):
    complete: bool
    budget_exhausted: bool
    searched_revision_ids: tuple[ConfigRevisionId, ...]
    unresolved_function_ids: tuple[FunctionId, ...]
    nodes_visited: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def budget_is_not_completeness(self) -> Self:
        if self.complete and self.budget_exhausted:
            raise ValueError("Budget exhaustion cannot establish complete search")
        return self


class CandidateSet(VersionedModel):
    candidates: tuple[ConfigRevision, ...]
    search: SearchMetadata

    @field_validator("candidates")
    @classmethod
    def unique_configs(cls, value):
        return unique_sorted(value, "config_revision_id")


class CandidateAssessment(VersionedModel):
    config_revision_id: ConfigRevisionId
    checks: tuple[CandidateCheck, ...]
    evidence_sufficient: bool
    issues: tuple[Issue, ...]

    @model_validator(mode="after")
    def checks_belong_to_candidate(self) -> Self:
        if any(check.config_revision_id != self.config_revision_id for check in self.checks):
            raise ValueError("CONFIG_FUNCTION_MISMATCH")
        return self


class ObligationAllocation(DomainModel):
    requirement_id: Identifier
    function_id: FunctionId
    contribution_role: Nonblank
    source_assertion_ids: tuple[Identifier, ...]


class BranchGuard(DomainModel):
    rule_revision_id: Identifier
    function_id: FunctionId
    config_revision_id: ConfigRevisionId | None
    predicate: Nonblank


class EvidencePacket(VersionedModel):
    context: OrderEvidenceContext
    candidates: CandidateSet
    assessments: tuple[CandidateAssessment, ...]
    rules: tuple[RuleRevision, ...]
    obligations: tuple[ObligationAllocation, ...]


class BehaviorCheck(VersionedModel):
    outcome: Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
    verifier_version: Nonblank
    evidence_ids: tuple[Identifier, ...]
    counterexample: FactValue
    verification_scope: Nonblank
    unknowns: tuple[str, ...]
    applicable: bool | None = None

    @model_validator(mode="after")
    def explicit_applicability(self) -> Self:
        if self.outcome == "NOT_APPLICABLE" and self.applicable is not False:
            raise ValueError("NOT_APPLICABLE requires an explicit false applicability predicate")
        return self


class ObligationResult(DomainModel):
    allocation: ObligationAllocation
    result: BehaviorCheck


class CompositionCheck(VersionedModel):
    template_revision_id: Identifier
    obligation_results: tuple[ObligationResult, ...]
    connection_checks: tuple[CandidateCheck, ...]
    behavior: BehaviorCheck
    remaining_unknowns: tuple[str, ...]


class SourceSpan(DomainModel):
    block_id: SourceBlockId
    text_span: TextSpan


class OrderExtractionProposal(VersionedModel):
    assertions: tuple[SourceAssertion, ...]
    requirements: tuple[Requirement, ...]
    source_spans: tuple[SourceSpan, ...]
    alternatives: tuple[str, ...]
    issues: tuple[Issue, ...]
    approved: Literal[False] = False

    @model_validator(mode="after")
    def proposals_are_unreviewed(self) -> Self:
        if any(
            assertion.review_state != "UNREVIEWED" or assertion.origin != "MODEL_PROPOSAL"
            for assertion in self.assertions
        ):
            raise ValueError("Model assertions must remain unreviewed proposals")
        if any(requirement.extraction_status != "PROPOSED" for requirement in self.requirements):
            raise ValueError("Model requirements must remain proposals")
        return self


class LinkProposalSet(VersionedModel):
    proposed_links: tuple[EntityLink, ...]
    source_spans: tuple[SourceSpan, ...]
    alternatives: tuple[EntityLink, ...]
    issues: tuple[Issue, ...]
    approved: Literal[False] = False

    @model_validator(mode="after")
    def links_are_unreviewed(self) -> Self:
        if any(
            link.review_state != "UNREVIEWED" for link in (*self.proposed_links, *self.alternatives)
        ):
            raise ValueError("Model links must remain unreviewed proposals")
        return self


class SemanticFinding(DomainModel):
    requirement_id: Identifier
    outcome: Literal["AGREEMENT", "DIFFERENCE", "INSUFFICIENT_EVIDENCE"]
    evidence_ids: tuple[Identifier, ...]
    summary: str


class SemanticComparison(VersionedModel):
    function_id: FunctionId
    candidate_config_revision_id: ConfigRevisionId
    findings: tuple[SemanticFinding, ...]
    unresolved_questions: tuple[str, ...]
    recommendation: Literal["SUPPORT", "REJECT", "REVIEW"]
    rationale_summary: str


class RuleOutcome(DomainModel):
    rule_revision_id: Identifier
    outcome: Literal["TRUE", "FALSE", "UNKNOWN"]
    evidence_ids: tuple[Identifier, ...]


class RuleEvaluation(VersionedModel):
    outcomes: tuple[RuleOutcome, ...]
    derived_requirements: tuple[Requirement, ...]
    guards: tuple[BranchGuard, ...]
    issues: tuple[Issue, ...]


class AssessmentPreparation(VersionedModel):
    assessments: FrozenMap[Digest, tuple[CandidateAssessment, ...]]
    guards: tuple[BranchGuard, ...]
    allocations: tuple[ObligationAllocation, ...]
    completeness: Completeness
    issues: tuple[Issue, ...]


class CoverageLink(DomainModel):
    requirement_id: Identifier
    config_revision_id: ConfigRevisionId
    covered_behavior: str
    verification_method: Nonblank
    result: BehaviorCheck


class DependencyEdge(DomainModel):
    source_function_id: FunctionId
    target_function_id: FunctionId
    rule_revision_id: Identifier
    evidence_ids: tuple[Identifier, ...]


class SelectionPlan(VersionedModel):
    selections: FrozenMap[FunctionId, ConfigRevisionId]
    assessments: tuple[FunctionAssessment, ...]
    coverage_claims: tuple[CoverageLink, ...]
    active_derived_requirements: tuple[Requirement, ...]
    dependency_edges: tuple[DependencyEdge, ...]
    issues: tuple[Issue, ...]
    search: SearchMetadata

    _rows = field_validator("selections", mode="before")(DecisionPayload.external_rows.__func__)


class Approval(VersionedModel):
    decision_revision_id: DecisionRevisionId
    payload_hash: Digest
    validation_hash: Digest
    reviewer: Identifier
    timestamp: Nonblank


class ExportManifest(VersionedModel):
    decision_revision_id: DecisionRevisionId
    payload_hash: Digest
    validation_hash: Digest
    destination: Nonblank
    file_hash: Digest
    label: Literal["DRAFT", "APPROVED"]


class ModelRequest(VersionedModel):
    """Data-only adapter contract; authentication is supplied outside this payload."""

    request_id: Identifier
    allowed_schema: FrozenMap[str, FactValue]
    payload: FactValue
    execution_settings: FrozenMap[str, FactValue]


class ModelResponse(VersionedModel):
    """Raw untrusted data, distinct from semantic proposals and domain checks."""

    request_id: Identifier
    response_id: Identifier
    model_revision: Nonblank
    content: FactValue
