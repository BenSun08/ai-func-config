"""Domain invariants independent of model responses and planning."""

from pydantic import TypeAdapter

from busconfig.domain.contracts import FunctionId, SelectionInput, SelectionMap


class SelectionInvariantError(ValueError):
    """A stable domain conflict code; full issue/report records arrive in T01.3."""

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
