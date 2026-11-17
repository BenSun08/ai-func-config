"""Shared domain types from design §§2, 8 and 20; no planner/model dependencies."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Opaque IDs are validated, never split, trimmed or manufactured from device scope.
Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[^\s,]+$")]
FunctionId = Identifier
ConfigRevisionId = Identifier
DecisionRevisionId = Identifier
SelectionMap = dict[FunctionId, ConfigRevisionId]

# Typed JSON-compatible values include structured bindings, not only scalars.
type FactValue = bool | int | float | str | list[FactValue] | dict[str, FactValue] | None


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
    Source-document versions/locators and collision checks are owned by T01.3.
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

    @model_validator(mode="after")
    def check_value_state(self) -> Self:
        if self.value_state == ValueState.KNOWN:
            if self.value is None:
                raise ValueError("KNOWN requires an explicit non-null value")
        elif self.value is not None:
            raise ValueError("Only KNOWN can carry a resolved value")
        return self
