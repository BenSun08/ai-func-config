"""Synthetic proofs of the design's single-choice input boundary."""

import pytest
from pydantic import ValidationError

from busconfig.domain.contracts import (
    FunctionInstance,
    Selection,
    SelectionInput,
    SelectionRequest,
)
from busconfig.domain.invariants import SelectionInvariantError, validate_selection_rows


@pytest.mark.parametrize("second_config", ["DEMO-C1-R1", "DEMO-C2-R1", "DEMO-C1-R2"])
def test_duplicate_function_rows_are_rejected(second_config):
    rows = [
        SelectionInput(function_id="DEMO-F1", config_revision_id="DEMO-C1-R1"),
        SelectionInput(function_id="DEMO-F1", config_revision_id=second_config),
    ]
    with pytest.raises(SelectionInvariantError) as caught:
        validate_selection_rows(rows)
    assert caught.value.code == "MULTIPLE_CONFIGS_FOR_FUNCTION"
    assert caught.value.function_id == "DEMO-F1"


def test_distinct_functions_keep_scalar_selections():
    rows = [
        SelectionInput(function_id="DEMO-F1", config_revision_id="DEMO-C1-R1"),
        SelectionInput(function_id="DEMO-F2", config_revision_id="DEMO-C2-R1"),
    ]
    assert validate_selection_rows(rows) == {"DEMO-F1": "DEMO-C1-R1", "DEMO-F2": "DEMO-C2-R1"}


def test_null_selection_is_allowed_in_draft():
    assert validate_selection_rows([]) == {}
    request = SelectionRequest(
        expected_decision_revision_id="DEMO-REV1",
        config_revision_id=None,
        reason="Synthetic choice cleared for review",
    )
    assert request.model_dump()["config_revision_id"] is None
    with pytest.raises(ValidationError):
        SelectionInput(function_id="DEMO-F1", config_revision_id=None)
    with pytest.raises(ValidationError):
        Selection(decision_revision_id="DEMO-REV1", function_id="DEMO-F1", config_revision_id=None)


def test_clear_request_requires_explicit_configuration_field():
    with pytest.raises(ValidationError):
        SelectionRequest(expected_decision_revision_id="DEMO-REV1", reason="Synthetic review")


@pytest.mark.parametrize("value", [["DEMO-C1-R1"], [], "DEMO-C1-R1,DEMO-C2-R1", "", " ", 0, False])
def test_selected_configuration_requires_one_nonblank_scalar_id(value):
    with pytest.raises(ValidationError):
        SelectionInput(function_id="DEMO-F1", config_revision_id=value)
    with pytest.raises(ValidationError):
        SelectionRequest(
            expected_decision_revision_id="DEMO-REV1",
            config_revision_id=value,
            reason="Synthetic review",
        )


@pytest.mark.parametrize("function_id", [["DEMO-F1"], ("DEMO-F1", "DEMO-FRONT"), "", " ", None, 1])
def test_selection_key_is_a_scalar_function_id(function_id):
    with pytest.raises(ValidationError):
        SelectionInput(function_id=function_id, config_revision_id="DEMO-C1-R1")


def test_instances_do_not_change_selection_key():
    front = FunctionInstance(instance_id="DEMO-FRONT", scope="front device", function_id="DEMO-F1")
    rear = FunctionInstance(instance_id="DEMO-REAR", scope="rear device", function_id="DEMO-F1")
    assert front.scope != rear.scope
    rows = [
        SelectionInput(function_id=front.function_id, config_revision_id="DEMO-C1-R1"),
        SelectionInput(function_id=rear.function_id, config_revision_id="DEMO-C2-R1"),
    ]
    with pytest.raises(SelectionInvariantError, match="MULTIPLE_CONFIGS_FOR_FUNCTION"):
        validate_selection_rows(rows)
    for instance in (front, rear):
        with pytest.raises(ValidationError):
            SelectionInput(
                function_id=instance.function_id,
                config_revision_id="DEMO-C1-R1",
                instance_id=instance.instance_id,
            )
    assert validate_selection_rows(rows[:1]) == {"DEMO-F1": "DEMO-C1-R1"}


def test_unmapped_instance_does_not_invent_a_function():
    instance = FunctionInstance(instance_id="DEMO-UNMAPPED", scope="unmapped device")
    assert instance.function_id is None
    with pytest.raises(ValidationError):
        SelectionInput(function_id=instance.function_id, config_revision_id="DEMO-C1-R1")


def test_external_rows_are_checked_before_dictionary_conversion():
    rows = [
        {"function_id": "DEMO-F1", "config_revision_id": "DEMO-C1-R1"},
        {"function_id": "DEMO-F1", "config_revision_id": "DEMO-C1-R1"},
    ]
    with pytest.raises(SelectionInvariantError, match="MULTIPLE_CONFIGS_FOR_FUNCTION"):
        validate_selection_rows(rows)
    with pytest.raises(ValidationError):
        validate_selection_rows({"DEMO-F1": "DEMO-C1-R1"})


def test_boundary_revalidates_untrusted_constructed_rows():
    row = SelectionInput.model_construct(function_id="DEMO-F1", config_revision_id=["DEMO-C1-R1"])
    with pytest.raises(ValidationError):
        validate_selection_rows([row])


def test_different_decision_revisions_are_separate_selection_scopes():
    for revision, config in (("DEMO-REV1", "DEMO-C1-R1"), ("DEMO-REV2", "DEMO-C2-R1")):
        selection = Selection(
            decision_revision_id=revision,
            function_id="DEMO-F1",
            config_revision_id=config,
        )
        assert selection.decision_revision_id == revision
        assert validate_selection_rows(
            [
                SelectionInput(
                    function_id=selection.function_id,
                    config_revision_id=selection.config_revision_id,
                )
            ]
        ) == {"DEMO-F1": config}


def assertion(state, value=None, **overrides):
    from busconfig.domain.contracts import SourceAssertion

    return SourceAssertion(
        assertion_id="DEMO-A1",
        subject_id="DEMO-DEVICE1",
        property="synthetic_property",
        source_block_ids=("DEMO-BLOCK1",),
        statement_scope="CURRENT_ORDER",
        value_state=state,
        value=value,
        **overrides,
    )


def test_false_zero_missing_are_distinct():
    import json

    from busconfig.domain.contracts import ValueState

    false = assertion(ValueState.KNOWN, False)
    zero = assertion(ValueState.KNOWN, 0)
    missing = assertion(ValueState.MISSING)
    not_applicable = assertion(ValueState.NOT_APPLICABLE)
    conflict = assertion(ValueState.CONFLICT)
    assert false.value is False
    assert type(zero.value) is int and zero.value == 0
    assert missing.value is None
    assert missing.value_state != not_applicable.value_state != conflict.value_state
    assert json.loads(false.model_dump_json())["value"] is False
    assert type(json.loads(zero.model_dump_json())["value"]) is int
    assert json.loads(missing.model_dump_json())["value_state"] == "MISSING"


@pytest.mark.parametrize("state", ["MISSING", "NOT_APPLICABLE", "CONFLICT"])
@pytest.mark.parametrize("value", [False, 0, "", "synthetic"])
def test_unresolved_or_inapplicable_state_cannot_carry_a_resolved_value(state, value):
    from busconfig.domain.contracts import ValueState

    with pytest.raises(ValidationError):
        assertion(ValueState(state), value)


def test_known_requires_a_value_instead_of_defaulting_to_false():
    from busconfig.domain.contracts import ValueState

    with pytest.raises(ValidationError):
        assertion(ValueState.KNOWN)


def test_blank_and_absent_source_text_remain_distinct():
    from busconfig.domain.contracts import ValueState

    absent = assertion(ValueState.MISSING)
    blank = assertion(ValueState.MISSING, raw_text="")
    slash_blank = assertion(ValueState.MISSING, raw_text="/")
    assert absent.raw_text is None
    assert blank.raw_text == ""
    assert slash_blank.raw_text == "/"
    assert len({item.model_dump_json() for item in (absent, blank, slash_blank)}) == 3
    # Already interpreted domain values are preserved, never truthiness-normalized.
    assert assertion(ValueState.KNOWN, "").value == ""
    assert assertion(ValueState.KNOWN, "0/1/2/3").value == "0/1/2/3"


def test_structured_values_keep_scalar_types_and_source_scope():
    from busconfig.domain.contracts import SourceAssertion, ValueState

    value = {"enabled": False, "count": 0, "sequence": ["0/1/2/3", None]}
    for scope in ("CURRENT_ORDER", "HISTORICAL_REFERENCE", "PLANNED_USE"):
        item = SourceAssertion(
            assertion_id="DEMO-A1",
            subject_id="DEMO-DEVICE1",
            property="binding",
            source_block_ids=("DEMO-BLOCK1", "DEMO-BLOCK2"),
            statement_scope=scope,
            value_state=ValueState.KNOWN,
            value=value,
            raw_text="Synthetic binding",
        )
        restored = SourceAssertion.model_validate_json(item.model_dump_json())
        assert restored.value["enabled"] is False
        assert type(restored.value["count"]) is int
        assert restored.value["sequence"] == ("0/1/2/3", None)
        assert restored.assertion_id == "DEMO-A1"
        assert restored.source_block_ids == ("DEMO-BLOCK1", "DEMO-BLOCK2")
        assert restored.statement_scope == scope
        assert restored.raw_text == "Synthetic binding"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {"nested": float("inf")}, object()])
def test_values_reject_nonfinite_numbers_and_arbitrary_objects(value):
    from busconfig.domain.contracts import ValueState

    with pytest.raises(ValidationError):
        assertion(ValueState.KNOWN, value)
