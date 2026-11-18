"""Synthetic identity, immutable decision and canonical serialization boundaries."""

import json

import pytest
from pydantic import ValidationError

from busconfig.domain.contracts import SourceAssertion, ValueState


def source_assertion(value):
    return SourceAssertion(
        assertion_id="DEMO-A1",
        subject_id="DEMO-DEVICE",
        property="binding",
        source_block_ids=("DEMO-B1",),
        statement_scope="CURRENT_ORDER",
        value_state=ValueState.KNOWN,
        value=value,
    )


def test_nested_fact_values_cannot_be_mutated():
    supplied = {"enabled": False, "steps": [0, 1]}
    assertion = source_assertion(supplied)
    supplied["steps"].append(2)
    assert tuple(assertion.value["steps"]) == (0, 1)
    with pytest.raises(TypeError):
        assertion.value["enabled"] = True
    with pytest.raises(TypeError):
        assertion.value["steps"][0] = 2


def revision(value=None, **changes):
    from busconfig.domain.contracts import DecisionPayload, DecisionRevision, ResolvedFact

    fact = ResolvedFact(
        fact_id="DEMO-FACT1",
        order_snapshot_id="DEMO-ORDER-R1",
        subject_id="DEMO-DEVICE",
        property="binding",
        value_state=ValueState.KNOWN,
        value={"enabled": False, "count": 0, "sequence": [0, 1]} if value is None else value,
        assertion_ids=("DEMO-A1",),
        resolution_method="REVIEWED",
        review_state="CONFIRMED",
    )
    payload = {
        "order_snapshot_id": "DEMO-ORDER-R1",
        "knowledge_snapshot_id": "DEMO-KNOWLEDGE-R1",
        "input_generation": 1,
        "parent_revision_id": None,
        "selections": {"DEMO-F2": "DEMO-C2-R1", "DEMO-F1": "DEMO-C1-R1"},
        "facts": (fact,),
        "assessments": (),
        "issues": (),
        "evidence_ids": ("DEMO-B2", "DEMO-B1"),
    }
    payload.update(changes)
    return DecisionRevision(decision_revision_id="DEMO-REV1", payload=DecisionPayload(**payload))


def test_revision_hash_is_order_independent():
    first = revision()
    second = revision(
        value={"sequence": [0, 1], "count": 0, "enabled": False},
        selections={"DEMO-F1": "DEMO-C1-R1", "DEMO-F2": "DEMO-C2-R1"},
        evidence_ids=("DEMO-B1", "DEMO-B2"),
    )
    assert first.payload_hash == second.payload_hash
    assert (
        first.payload_hash
        != revision(value={"enabled": True, "count": 0, "sequence": [0, 1]}).payload_hash
    )
    assert (
        first.payload_hash
        != revision(value={"enabled": False, "count": 0, "sequence": [1, 0]}).payload_hash
    )
    assert revision(value=False).payload_hash != revision(value=0).payload_hash


def test_decision_pins_snapshot_generation_and_parent():
    initial = revision().payload_hash
    for changed in (
        {"order_snapshot_id": "DEMO-ORDER-R2", "facts": ()},
        {"knowledge_snapshot_id": "DEMO-KNOWLEDGE-R2"},
        {"input_generation": 2},
        {"parent_revision_id": "DEMO-PARENT"},
        {"selections": {}},
    ):
        assert revision(**changed).payload_hash != initial


def test_decision_payload_is_deeply_immutable():
    decision = revision()
    initial = decision.payload_hash
    with pytest.raises(TypeError):
        decision.payload.selections["DEMO-F1"] = "DEMO-C2-R1"
    with pytest.raises(TypeError):
        decision.payload.facts[0].value["count"] = 2
    with pytest.raises(ValidationError):
        decision.payload.input_generation = 2
    exported = decision.model_dump(mode="json")
    exported["payload"]["selections"].clear()
    assert decision.payload_hash == initial


def test_report_does_not_mutate_payload_hash():
    from busconfig.domain.contracts import ValidationReport

    decision = revision()
    initial = decision.payload_hash
    report = ValidationReport(
        report_id="DEMO-REPORT1",
        decision_revision_id=decision.decision_revision_id,
        payload_hash=initial,
        validator_version="demo-validator-1",
        checks=(),
        issues=(),
        evidence_ids=("DEMO-B1",),
        approval_eligible=False,
    )
    later = ValidationReport(
        **(report.model_dump(exclude={"report_hash"}) | {"validator_version": "demo-validator-2"})
    )
    assert report.report_hash != later.report_hash
    assert report.payload_hash == later.payload_hash == decision.payload_hash == initial
    assert "report" not in decision.model_dump_json()
    with pytest.raises(ValidationError):
        report.approval_eligible = True


def test_payload_rejects_reports_lifecycle_and_duplicate_rows():
    from busconfig.domain.invariants import SelectionInvariantError

    for field in ("validation_report", "status", "payload_hash", "export_timestamp"):
        with pytest.raises(ValidationError):
            revision(**{field: "untrusted"})
    with pytest.raises(
        (SelectionInvariantError, ValidationError), match="MULTIPLE_CONFIGS_FOR_FUNCTION"
    ):
        revision(
            selections=[
                {"function_id": "DEMO-F1", "config_revision_id": "DEMO-C1-R1"},
                {"function_id": "DEMO-F1", "config_revision_id": "DEMO-C2-R1"},
            ]
        )


def document(**changes):
    from busconfig.domain.contracts import SourceDocument

    fields = dict(
        document_id="DEMO-DOC1",
        role="PIN_DEFINITION",
        business_revision="R1",
        byte_hash="sha256:" + "1" * 64,
        original_path="synthetic/引脚.xlsx",
        layout_profile="demo-pins-v1",
        parser_version="demo-parser-v1",
    )
    fields.update(changes)
    return SourceDocument(**fields)


def test_source_id_collision_is_rejected():
    from busconfig.domain.invariants import SourceIdentityError, validate_source_ids

    for reused in (
        document(),
        document(byte_hash="sha256:" + "2" * 64),
        document(business_revision="R2"),
    ):
        with pytest.raises(SourceIdentityError, match="SOURCE_ID_COLLISION"):
            validate_source_ids([document(), reused], [])


def test_source_locator_and_version_determine_stable_block_identity():
    from busconfig.domain.contracts import SourceBlock, TextSpan, XlsxLocator
    from busconfig.domain.invariants import source_block_id, validate_source_ids

    doc = document()
    locator = XlsxLocator(sheet="引脚", cells=("G12", "H12"), text_span=TextSpan(start=0, end=4))
    identity = source_block_id(doc, locator)
    assert identity == source_block_id(
        doc, XlsxLocator.model_validate_json(locator.model_dump_json())
    )
    assert identity != source_block_id(document(business_revision="R2"), locator)
    assert identity != source_block_id(document(byte_hash="sha256:" + "2" * 64), locator)
    assert identity != source_block_id(doc, XlsxLocator(sheet="引脚", cells=("G13",)))
    block = SourceBlock(
        block_id=identity,
        document_id=doc.document_id,
        document_hash=doc.byte_hash,
        locator=locator,
        raw_text="合成信号",
        effective_status="CURRENT",
    )
    validate_source_ids([doc], [block])
    assert SourceBlock.model_validate_json(block.model_dump_json()) == block
    with pytest.raises(ValueError, match="SOURCE_ID_COLLISION"):
        validate_source_ids([doc], [block, block])
    with pytest.raises(ValueError, match="SOURCE_REFERENCE_MISMATCH"):
        validate_source_ids([document(byte_hash="sha256:" + "2" * 64)], [block])


def test_canonical_json_preserves_unicode_types_and_sequences():
    from busconfig.domain.serialization import canonical_json

    assert (
        canonical_json({"z": False, "a": [0, "合成", None]})
        == '{"a":[0,"合成",null],"z":false}'.encode()
    )
    assert canonical_json({"a": [0, 1]}) != canonical_json({"a": [1, 0]})
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})


def test_revision_serialization_checks_claimed_hash_and_schema_version():
    from busconfig.domain.contracts import DecisionRevision

    decision = revision()
    exported = json.loads(decision.model_dump_json())
    assert exported["payload_hash"] == decision.payload_hash
    assert (
        DecisionRevision.model_validate_json(json.dumps(exported)).payload_hash
        == decision.payload_hash
    )
    exported["payload"]["input_generation"] = 99
    with pytest.raises(ValidationError, match="HASH_MISMATCH"):
        DecisionRevision.model_validate_json(json.dumps(exported))
    exported["payload"]["schema_version"] = "unsupported"
    with pytest.raises(ValidationError):
        DecisionRevision.model_validate_json(json.dumps(exported))


def test_duplicate_json_object_keys_are_not_silently_overwritten():
    from busconfig.domain.contracts import DecisionRevision

    encoded = (
        revision()
        .model_dump_json()
        .replace('"DEMO-F1":"DEMO-C1-R1"', '"DEMO-F1":"DEMO-C1-R1","DEMO-F1":"DEMO-C2-R1"')
    )
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        DecisionRevision.model_validate_json(encoded)


def test_copy_updates_cannot_bypass_contract_or_hash_validation():
    decision = revision()
    with pytest.raises(ValidationError):
        decision.payload.model_copy(update={"input_generation": -1})
    with pytest.raises(ValidationError, match="HASH_MISMATCH"):
        decision.model_copy(update={"payload_hash": "sha256:" + "0" * 64})


def test_indexed_collections_are_canonical_and_duplicate_ids_fail():
    from busconfig.domain.contracts import DecisionPayload, Issue

    a = Issue(
        issue_id="DEMO-I1",
        code="UNKNOWN_REQUIRED_FIELD",
        scope="DEMO-F1",
        evidence_ids=("DEMO-B2", "DEMO-B1"),
        resolution_target="binding",
        message="Synthetic missing binding",
    )
    b = Issue(**(a.model_dump() | {"issue_id": "DEMO-I2"}))
    assert revision(issues=(a, b)).payload_hash == revision(issues=(b, a)).payload_hash
    with pytest.raises(ValidationError, match="DUPLICATE_ID"):
        DecisionPayload(**(revision().payload.model_dump() | {"issues": (a, a)}))
    with pytest.raises(ValidationError):
        Issue(**(a.model_dump() | {"severity": "INFO"}))


def test_parse_result_preserves_native_provenance_and_rejects_aliasing():
    from busconfig.domain.contracts import Completeness, ParseResult, SourceBlock, XlsxLocator

    doc = document()
    block = SourceBlock(
        block_id="DEMO-B1",
        document_id=doc.document_id,
        document_hash=doc.byte_hash,
        locator=XlsxLocator(sheet="合成引脚", cells=("A1",)),
        raw_text="/",
        effective_status="CURRENT",
    )
    status = Completeness(
        complete=False,
        supported_regions=("sheet:合成引脚",),
        unsupported_regions=("chart:1",),
        mapped_columns=("A",),
        unmapped_columns=("B",),
        mandatory_sections_found=False,
    )
    parsed = ParseResult(
        document=doc, source_blocks=(block,), assertions=(), issues=(), completeness=status
    )
    restored = ParseResult.model_validate_json(parsed.model_dump_json())
    assert restored.source_blocks[0].raw_text == "/"
    assert restored.document.business_revision == "R1"
    assert restored.document.original_path == "synthetic/引脚.xlsx"
    assert restored.completeness.unsupported_regions == ("chart:1",)
    with pytest.raises(ValidationError, match="SOURCE_ID_COLLISION"):
        ParseResult(**(parsed.model_dump() | {"source_blocks": (block, block)}))
    with pytest.raises(ValidationError):
        Completeness(**(status.model_dump() | {"complete": True}))


def test_report_binding_rejects_different_decision_content():
    from busconfig.domain.contracts import ValidationReport
    from busconfig.domain.invariants import validate_report_binding

    original = revision()
    report = ValidationReport(
        report_id="DEMO-R1",
        decision_revision_id="DEMO-REV1",
        payload_hash=original.payload_hash,
        validator_version="demo-v1",
        checks=(),
        issues=(),
        evidence_ids=(),
        approval_eligible=False,
    )
    validate_report_binding(original, report)
    with pytest.raises(ValueError, match="STALE_REVISION"):
        validate_report_binding(revision(input_generation=2), report)


def test_advisory_model_findings_cannot_be_candidate_checks():
    from busconfig.domain.contracts import CandidateCheck, SemanticComparison

    response = SemanticComparison.model_validate_json(
        json.dumps(
            {
                "function_id": "DEMO-F1",
                "candidate_config_revision_id": "DEMO-C1-R1",
                "findings": [
                    {
                        "requirement_id": "DEMO-REQ1",
                        "outcome": "AGREEMENT",
                        "evidence_ids": ["DEMO-B1"],
                        "summary": "Synthetic match",
                    }
                ],
                "unresolved_questions": [],
                "recommendation": "SUPPORT",
                "rationale_summary": "Advisory only",
            }
        )
    )
    assert response.recommendation == "SUPPORT"
    with pytest.raises(ValidationError):
        CandidateCheck.model_validate(response.model_dump())
    with pytest.raises(ValidationError):
        CandidateCheck(
            check_id="DEMO-CHECK1",
            config_revision_id="DEMO-C1-R1",
            requirement_ids=(),
            outcome="NOT_APPLICABLE",
            comparator="demo-v1",
            evidence_ids=(),
            applicable=None,
        )


def test_fact_reference_order_does_not_change_payload_hash():
    first = revision()
    fact = first.payload.facts[0]
    left = fact.model_copy(update={"assertion_ids": ("DEMO-A2", "DEMO-A1")})
    right = fact.model_copy(update={"assertion_ids": ("DEMO-A1", "DEMO-A2")})
    assert revision(facts=(left,)).payload_hash == revision(facts=(right,)).payload_hash


def test_untrusted_proposal_cannot_claim_human_confirmation():
    from busconfig.domain.contracts import OrderExtractionProposal

    confirmed = source_assertion(False).model_copy(update={"review_state": "CONFIRMED"})
    with pytest.raises(ValidationError):
        OrderExtractionProposal(
            assertions=(confirmed,), requirements=(), source_spans=(), alternatives=(), issues=()
        )


def test_typed_result_boundaries_preserve_candidates_and_search_limits():
    from busconfig.domain.contracts import (
        CandidateSet,
        ConfigRevision,
        SearchMetadata,
        SelectionPlan,
    )

    candidate = ConfigRevision(
        config_revision_id="DEMO-C1-R1",
        configuration_id="DEMO-C1",
        function_id="DEMO-F1",
        revision="R1",
        behavior="Synthetic on; except while reset",
        attributes={
            "enabled": {
                "value_state": ValueState.KNOWN,
                "value": False,
                "evidence_ids": ("DEMO-B1",),
                "review_state": "UNREVIEWED",
            }
        },
        applicability="synthetic_condition",
        source_block_ids=("DEMO-B1",),
    )
    search = SearchMetadata(
        complete=False,
        budget_exhausted=True,
        searched_revision_ids=("DEMO-C1-R1",),
        unresolved_function_ids=("DEMO-F1",),
        nodes_visited=1,
    )
    candidates = CandidateSet(candidates=(candidate,), search=search)
    restored = CandidateSet.model_validate_json(candidates.model_dump_json())
    assert restored.candidates[0].behavior == "Synthetic on; except while reset"
    assert restored.candidates[0].attributes["enabled"].value is False
    with pytest.raises(ValidationError):
        SearchMetadata(**(search.model_dump() | {"complete": True}))
    with pytest.raises(ValidationError, match="MULTIPLE_CONFIGS_FOR_FUNCTION"):
        SelectionPlan(
            selections=[{"function_id": "DEMO-F1", "config_revision_id": "DEMO-C1-R1"}] * 2,
            assessments=(),
            coverage_claims=(),
            active_derived_requirements=(),
            dependency_edges=(),
            issues=(),
            search=search,
        )


@pytest.mark.parametrize(
    "model_name", ["OrderEvidenceContext", "OrderExtractionProposal", "LinkProposalSet"]
)
def test_evidence_and_proposal_contracts_do_not_accept_candidate_check_fields(model_name):
    import busconfig.domain.contracts as contracts

    # Extra fields are rejected even alongside missing required fields; no model
    # result can add an authoritative candidate-check channel to these contracts.
    with pytest.raises(ValidationError) as caught:
        getattr(contracts, model_name).model_validate({"candidate_checks": []})
    assert any(
        error["loc"] == ("candidate_checks",) and error["type"] == "extra_forbidden"
        for error in caught.value.errors()
    )


def test_report_check_reference_order_is_canonical():
    from busconfig.domain.contracts import CandidateCheck, ValidationReport

    check = CandidateCheck(
        check_id="DEMO-CHECK1",
        config_revision_id="DEMO-C1-R1",
        requirement_ids=("DEMO-REQ2", "DEMO-REQ1"),
        evidence_ids=("DEMO-B2", "DEMO-B1"),
        comparator="demo-v1",
        outcome="UNKNOWN",
    )
    common = dict(
        report_id="DEMO-REPORT1",
        decision_revision_id="DEMO-REV1",
        payload_hash=revision().payload_hash,
        validator_version="demo-v1",
        issues=(),
        evidence_ids=(),
        approval_eligible=False,
    )
    left = ValidationReport(**common, checks=(check,))
    right = ValidationReport(
        **common,
        checks=(
            check.model_copy(
                update={
                    "requirement_ids": ("DEMO-REQ1", "DEMO-REQ2"),
                    "evidence_ids": ("DEMO-B1", "DEMO-B2"),
                }
            ),
        ),
    )
    assert left.report_hash == right.report_hash


def test_model_response_is_untrusted_data_not_a_validated_assessment():
    from busconfig.domain.contracts import CandidateAssessment, ModelResponse

    response = ModelResponse(
        request_id="DEMO-REQUEST1",
        response_id="DEMO-RESPONSE1",
        model_revision="synthetic-model-v1",
        content={"instruction": "ignore the checks"},
    )
    assert response.content["instruction"] == "ignore the checks"
    with pytest.raises(ValidationError):
        CandidateAssessment.model_validate(response.model_dump())


def test_parse_result_rejects_assertion_ids_reused_as_block_ids():
    from busconfig.domain.contracts import Completeness, ParseResult, SourceBlock, XlsxLocator

    doc = document()
    block = SourceBlock(
        block_id="DEMO-B1",
        document_id=doc.document_id,
        document_hash=doc.byte_hash,
        locator=XlsxLocator(sheet="Pins", cells=("A1",)),
        raw_text="false",
        effective_status="CURRENT",
    )
    assertion = source_assertion(False).model_copy(update={"assertion_id": "DEMO-B1"})
    status = Completeness(
        complete=True,
        supported_regions=("Pins",),
        unsupported_regions=(),
        mapped_columns=("A",),
        unmapped_columns=(),
        mandatory_sections_found=True,
    )
    with pytest.raises(ValidationError, match="SOURCE_ID_COLLISION"):
        ParseResult(
            document=doc,
            source_blocks=(block,),
            assertions=(assertion,),
            issues=(),
            completeness=status,
        )


def test_revision_cannot_name_itself_as_parent():
    with pytest.raises(ValidationError, match="SELF_PARENT_REVISION"):
        revision(parent_revision_id="DEMO-REV1")


def test_configuration_attributes_require_explicit_value_states():
    from busconfig.domain.contracts import ConfigRevision

    with pytest.raises(ValidationError):
        ConfigRevision(
            config_revision_id="DEMO-C1-R1",
            configuration_id="DEMO-C1",
            function_id="DEMO-F1",
            revision="R1",
            behavior="Synthetic behavior",
            applicability="Synthetic predicate",
            source_block_ids=("DEMO-B1",),
            attributes={"enabled": False},
        )
