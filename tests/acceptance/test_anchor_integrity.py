"""Audit hand-authored answers against the invented world, without a matcher."""

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "evals/gold/anchors.json"
WORLD = ROOT / "synthetic/worlds/core.yaml"


def distinct_keys(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"repeated gold key {key!r}"
        result[key] = value
    return result


def test_anchor_selection_cardinality():
    assert GOLD.is_file(), "missing hand-authored E01–E10 reference outcomes"
    cases = json.loads(GOLD.read_text(), object_pairs_hook=distinct_keys)["cases"]
    world = yaml.safe_load(WORLD.read_text())
    assert {case["scenario_id"] for case in cases} == {f"E{i:02}" for i in range(1, 11)}
    for case in cases:
        outcome = case["outcome"]
        if outcome["kind"] == "select":
            assert outcome["acceptable_plans"]
            for plan in outcome["acceptable_plans"]:
                assert plan
                for function, revision in plan.items():
                    assert isinstance(revision, str)
                    assert revision in world["functions"][function]["revisions"]
        else:
            assert "acceptable_plans" not in outcome
        if case["scenario_id"] == "E04":
            assert outcome["kind"] == "abstain"
            assert outcome["function_id"] == "F-BEACON"
            assert "SAME_FUNCTION_COMPOSITION_FORBIDDEN" in case["expected_issues"]


@pytest.fixture
def cases():
    from evals.types import build_anchor_suite

    suite = build_anchor_suite()
    indexed = {case.case_id: case for case in suite.cases}
    assert len(indexed) == len(suite.cases)
    return indexed


@pytest.fixture
def world():
    return yaml.safe_load(WORLD.read_text())


def test_references_point_to_the_pinned_orders_and_source_cells(cases, world):
    targets = set(world["functions"]) | set(world["policies"]) | set(world["signals"])
    targets.update(world["composition_templates"])
    for function in world["functions"].values():
        targets.update(function["revisions"])
    for case in cases.values():
        assert case.input_paths == ("synthetic/worlds/core.yaml",)
        assert case.knowledge_id == world["knowledge_id"]
        order = world["orders"][case.order_id]
        for link in case.evidence_links:
            assert link.target in targets
            for ref in link.sources:
                row_id, column = ref.split(".")
                row = order["rows"][row_id]
                assert column in row["cells"]
                assert world["tables"][row["table"]][column]["scope"] == link.scope


def test_signed_absence_and_blank_fitment_have_different_outcomes(cases, world):
    excluded, unknown = cases["E02"], cases["E03"]
    absent = world["orders"][excluded.order_id]["rows"]["T33"]["cells"]
    blank = world["orders"][unknown.order_id]["rows"]["T34"]["cells"]
    assert absent["D"] == blank["D"] == "trim desk"
    assert absent["B"] is False and blank["B"] == "/"
    assert excluded.outcome.function_id == unknown.outcome.function_id == "F-TAG"
    assert excluded.outcome.kind == "exclude" and not excluded.expected_issues
    assert world["policies"][excluded.outcome.basis_id]["review_state"] == "RELEASED"
    assert unknown.outcome.resolution == "NEEDS_EVIDENCE" and unknown.outcome.question


def test_incompatible_instances_share_one_unresolved_function(cases, world):
    case = cases["E05"]
    rows = world["orders"][case.order_id]["rows"]
    assert {row["cells"]["B"] for row in rows.values()} == {"momentary", "latching"}
    assert case.outcome.resolution == "CONFLICT"
    assert case.outcome.function_id == "F-BEACON"


def test_submitted_revisions_are_rejected_together(cases, world):
    rejected = cases["E06"]
    assert rejected.outcome.kind == "reject"
    assert rejected.expected_issues == ("MULTIPLE_CONFIGS_FOR_FUNCTION",)
    order = world["orders"][rejected.order_id]
    assert order["submission_revision_id"] == rejected.outcome.submission_revision_id
    rows = order["submitted_rows"]
    assert len(rows) == 2 and {r["function_id"] for r in rows} == {"F-TAG"}
    revisions = world["functions"]["F-TAG"]["revisions"]
    assert len({r["config_revision_id"] for r in rows}) == 2
    assert {revisions[r["config_revision_id"]]["config_id"] for r in rows} == {"INK"}


def test_tie_and_reviewed_composition(cases, world):
    tie = cases["E07"].outcome
    assert (tie.kind, tie.resolution) == ("abstain", "AMBIGUOUS_CHOICE")
    assert set(tie.tied_revisions) == {"INK.2", "WAX.1"}
    socket = world["orders"][cases["E07"].order_id]["rows"]["T39"]["cells"]["C"]
    revisions = world["functions"][tie.function_id]["revisions"]
    assert {rev for rev, data in revisions.items() if data["socket"] == socket} == set(
        tie.tied_revisions
    )
    joined = cases["E08"].outcome
    assert joined.acceptable_plans == ({"F-CALL": "SEND.1", "F-LAMP": "PULSE.1"},)
    template = world["composition_templates"][joined.template_revision_id]
    assert template["review_state"] == "RELEASED"
    assert set(template["obligations"]) == set(joined.acceptable_plans[0])
    assert template["connection"]["signal"] == "CALL-EDGE"
    assert template["reviewed_trace"][-1]["lamp_on"] is False


def test_relay_revisions_supply_the_reviewed_timing_and_signal(cases, world):
    joined = cases["E08"].outcome
    (plan,) = joined.acceptable_plans
    sender = world["functions"]["F-CALL"]["revisions"][plan["F-CALL"]]
    receiver = world["functions"]["F-LAMP"]["revisions"][plan["F-LAMP"]]
    assert sender["emits"] == receiver["input"] == "CALL-EDGE"
    assert receiver["output"] == "CALL-LIGHT"
    assert sender["emit_delay_ms"] + receiver["set_delay_ms"] <= 12
    assert receiver["ack_clear_delay_ms"] <= 12


def test_e08_review_trace_respects_order_input_spacing(cases, world):
    template_id = cases["E08"].outcome.template_revision_id
    trace = world["composition_templates"][template_id]["reviewed_trace"]
    # M40 requires at least 30 ms between input edges, including releases.
    edge_times = [
        current["ms"]
        for previous, current in zip(trace, trace[1:])
        for signal in ("button", "ack")
        if previous[signal] != current[signal]
    ]
    assert len(edge_times) >= 2
    assert all(later - earlier >= 30 for earlier, later in zip(edge_times, edge_times[1:]))


def test_dependency_conflict_and_replacement(cases, world):
    rule = world["dependency_rules"]["FOLLOW.1"]
    assert rule["when_selected"] == {"function_id": "F-CALL", "config_revision_id": "SEND.1"}
    assert rule["requires"] == {"function_id": "F-LAMP", "config_revision_id": "PULSE.1"}
    assert cases["E09"].outcome.acceptable_plans == ({"F-CALL": "STORE.1", "F-LAMP": "DC.1"},)
    case = cases["E10"]
    prior = world["orders"][case.order_id]["parent_decision"]
    assert prior["selections"] == {"F-CALL": "SEND.1", "F-LAMP": "PULSE.1"}
    assert prior["active_dependency_rules"] == ["FOLLOW.1"]
    assert case.outcome.acceptable_plans == ({"F-CALL": "STORE.1"},)
    assert case.outcome.active_dependency_rules == ()
    assert case.outcome.derived_function_ids == ()


def test_three_table_row_cutoff_misses_the_only_compatible_revision(cases, world):
    case = cases["E01.three-table"]
    probe = case.row_probe
    revisions = world["functions"]["F-LEVEL"]["revisions"]
    rows = world["orders"][case.order_id]["rows"]
    assert {rows[r]["table"] for r in probe.ranks} == {"pins", "logic", "switches"}
    assert probe.cutoff == 1
    assert cases["E01"].outcome.acceptable_plans == ({"F-LEVEL": "LEVEL-A.1"},)
    assert case.outcome.acceptable_plans == ({"F-LEVEL": "LEVEL-A.1"},)
    assert rows["P32"]["cells"]["B"] == "DIAL-A"
    assert rows["S32"]["cells"]["B"] == "momentary"
    assert "0/2/5/0" in rows["L32"]["cells"]["B"]
    compatible = {
        rev
        for rev, data in revisions.items()
        if (data["binding"], data["mechanism"], data["sequence"])
        == ("DIAL-A", "momentary", [0, 2, 5, 0])
    }
    assert compatible == {"LEVEL-A.1"}
    for row_id, ranking in probe.ranks.items():
        row = rows[row_id]
        current = " ".join(
            str(value).lower()
            for column, value in row["cells"].items()
            if world["tables"][row["table"]][column]["scope"] == "CURRENT_ORDER"
        )
        counts = {
            rev: sum(term in current for term in data["terms"]) for rev, data in revisions.items()
        }
        assert tuple(sorted(counts, key=lambda rev: (-counts[rev], rev))) == ranking
        assert ranking.index("LEVEL-A.1") >= probe.cutoff


def test_positive_score_cannot_pay_for_a_failed_condition(cases, world):
    case = cases["E04.positive"]
    assert (case.outcome.kind, case.outcome.resolution) == ("abstain", "CONFLICT")
    probe = case.score_probe
    rows = world["orders"][case.order_id]["rows"]
    revisions = world["functions"]["F-BEACON"]["revisions"]
    assert set(probe.scores) == set(revisions)
    roles = world["functions"]["F-BEACON"]["attribute_roles"]
    for revision, expected_score in probe.scores.items():
        mismatches = set()
        for attr, ref in probe.observations.items():
            row_id, column = ref.split(".")
            actual = revisions[revision][attr]
            required = rows[row_id]["cells"][column]
            if type(actual) is not type(required) or actual != required:
                mismatches.add(attr)
        assert len(probe.observations) - 2 * len(mismatches) == expected_score
        assert {attr for attr in mismatches if roles[attr] == "REQUIRED_CONDITION"} == set(
            probe.failed_conditions[revision]
        )
        assert probe.failed_conditions[revision]
    assert dict(probe.scores) == {"GLINT.1": 2, "SHADE.1": 0}
