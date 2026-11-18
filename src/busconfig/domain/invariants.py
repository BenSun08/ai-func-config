"""Domain invariants independent of model responses and planning."""

from pydantic import TypeAdapter

from busconfig.domain.contracts import (
    DecisionRevision,
    FunctionId,
    SelectionInput,
    SelectionMap,
    SourceAssertion,
    SourceBlock,
    SourceDocument,
    SourceLocator,
    ValidationReport,
)
from busconfig.domain.serialization import canonical_hash


class SelectionInvariantError(ValueError):
    """A stable conflict code, independent of report construction."""

    code = "MULTIPLE_CONFIGS_FOR_FUNCTION"

    def __init__(self, function_id: FunctionId):
        self.function_id = function_id
        super().__init__(self.code)


def validate_selection_rows(rows: list[SelectionInput]) -> SelectionMap:
    """Validate one decision revision's complete selected-row list.

    Raw row dictionaries may enter at this boundary, but a pre-collapsed mapping
    cannot: it has already lost duplicates. Revalidate even constructed instances.
    """
    validated = TypeAdapter(list[SelectionInput]).validate_python(rows, strict=True)
    seen: set[FunctionId] = set()
    for row in validated:
        if row.function_id in seen:
            raise SelectionInvariantError(row.function_id)
        seen.add(row.function_id)
    # Only construct the authoritative map after the entire list passes.
    return {row.function_id: row.config_revision_id for row in validated}


class SourceIdentityError(ValueError):
    def __init__(self, code: str, source_id: str):
        self.code = code
        self.source_id = source_id
        super().__init__(code)


def source_block_id(document: SourceDocument, locator: SourceLocator) -> str:
    digest = canonical_hash(
        {
            "schema_version": "1.0",
            "document_id": document.document_id,
            "document_hash": document.byte_hash,
            "business_revision": document.business_revision,
            "locator": locator,
        }
    )
    return "SRC-" + digest.removeprefix("sha256:")


def validate_source_ids(
    documents: list[SourceDocument],
    blocks: list[SourceBlock],
    assertions: list[SourceAssertion] | None = None,
) -> None:
    documents = TypeAdapter(list[SourceDocument]).validate_python(documents, strict=True)
    blocks = TypeAdapter(list[SourceBlock]).validate_python(blocks, strict=True)
    assertions = TypeAdapter(list[SourceAssertion]).validate_python(
        [] if assertions is None else assertions,
        strict=True,
    )
    seen: set[str] = set()
    for record in (*documents, *blocks, *assertions):
        if isinstance(record, SourceDocument):
            identity = record.document_id
        elif isinstance(record, SourceBlock):
            identity = record.block_id
        else:
            identity = record.assertion_id
        if identity in seen:
            raise SourceIdentityError("SOURCE_ID_COLLISION", identity)
        seen.add(identity)
    by_id = {document.document_id: document for document in documents}
    for block in blocks:
        if (
            block.document_id not in by_id
            or by_id[block.document_id].byte_hash != block.document_hash
        ):
            raise SourceIdentityError("SOURCE_REFERENCE_MISMATCH", block.block_id)
    block_ids = {block.block_id for block in blocks}
    for assertion in assertions:
        if not set(assertion.source_block_ids) <= block_ids:
            raise SourceIdentityError("SOURCE_REFERENCE_MISMATCH", assertion.assertion_id)


def validate_report_binding(decision: DecisionRevision, report: ValidationReport) -> None:
    decision = DecisionRevision.model_validate(decision)
    report = ValidationReport.model_validate(report)
    if (
        report.decision_revision_id != decision.decision_revision_id
        or report.payload_hash != decision.payload_hash
    ):
        raise ValueError("STALE_REVISION")
