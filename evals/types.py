"""Offline reference outcomes. Loading the suite reads only the authored gold file."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from busconfig.domain.contracts import (
    ConfigRevisionId,
    DomainModel,
    FunctionId,
    Identifier,
    KnowledgeSnapshotId,
    Nonblank,
    OrderSnapshotId,
    SelectionMap,
)


class AcceptableSelections(DomainModel):
    kind: Literal["select"]
    acceptable_plans: Annotated[
        tuple[Annotated[SelectionMap, Field(min_length=1)], ...], Field(min_length=1)
    ]
    active_dependency_rules: tuple[Identifier, ...] = ()
    derived_function_ids: tuple[FunctionId, ...] = ()
    template_revision_id: Identifier | None = None


class Exclusion(DomainModel):
    kind: Literal["exclude"]
    function_id: FunctionId
    basis_id: Identifier


class RequiredAbstention(DomainModel):
    kind: Literal["abstain"]
    function_id: FunctionId
    resolution: Literal["NEEDS_EVIDENCE", "CONFLICT", "AMBIGUOUS_CHOICE"]
    question: Nonblank | None = None
    tied_revisions: tuple[ConfigRevisionId, ...] = ()


class RejectedSubmission(DomainModel):
    kind: Literal["reject"]
    submission_revision_id: Identifier


class EvidenceLink(DomainModel):
    sources: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    target: Identifier
    relation: Nonblank
    scope: Literal["CURRENT_ORDER", "HISTORICAL_REFERENCE", "PLANNED_USE"]


class RowProbe(DomainModel):
    policy: Literal["literal-catalog-terms-v1"]
    cutoff: Annotated[int, Field(gt=0)]
    ranks: dict[Identifier, tuple[ConfigRevisionId, ...]]


class ScoreProbe(DomainModel):
    policy: Literal["signed-typed-v1"]
    observations: dict[Identifier, Identifier]
    scores: dict[ConfigRevisionId, int]
    failed_conditions: dict[ConfigRevisionId, tuple[Identifier, ...]]


class AnchorCase(DomainModel):
    case_id: Identifier
    scenario_id: Identifier
    family_id: Identifier
    split_id: Literal["development", "validation", "test"]
    input_paths: Annotated[tuple[Nonblank, ...], Field(min_length=1)]
    order_id: OrderSnapshotId
    knowledge_id: KnowledgeSnapshotId
    evidence_links: Annotated[tuple[EvidenceLink, ...], Field(min_length=1)]
    outcome: Annotated[
        AcceptableSelections | RequiredAbstention | Exclusion | RejectedSubmission,
        Field(discriminator="kind"),
    ]
    expected_issues: tuple[Identifier, ...]
    reference_notes: Nonblank
    row_probe: RowProbe | None = None
    score_probe: ScoreProbe | None = None


class AnchorSuite(DomainModel):
    cases: Annotated[tuple[AnchorCase, ...], Field(min_length=1)]


def build_anchor_suite() -> AnchorSuite:
    path = Path(__file__).parent / "gold" / "anchors.json"
    return AnchorSuite.model_validate_json(path.read_bytes())
