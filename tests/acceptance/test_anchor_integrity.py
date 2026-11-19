"""Audit hand-authored answers against the invented world, without a matcher."""

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from evals.types import build_anchor_suite
from synthetic.inputs import load_order_input

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "evals/gold/anchors.json"
WORLD = ROOT / "synthetic/worlds/core.yaml"
INPUT_MANIFEST = WORLD.with_name("manifest.json")
SPLITS = ROOT / "evals/splits.json"


def test_gold_is_not_application_input(cases, world, tmp_path):
    assert INPUT_MANIFEST.is_file(), "missing input-only fixture manifest"
    isolated = shutil.copytree(INPUT_MANIFEST.parent, tmp_path / "worlds")
    evaluator_strings = {
        json.dumps(text) for case in cases.values() for text in (case.case_id, case.reference_notes)
    }
    for case in cases.values():
        assert case.input_paths == ("synthetic/worlds/manifest.json",)
        bundle = load_order_input(isolated, case.order_id)
        assert bundle == {**world, "orders": {case.order_id: world["orders"][case.order_id]}}
        encoded = json.dumps(bundle)
        assert not any(text in encoded for text in evaluator_strings)
    with pytest.raises(ValueError, match="unknown order"):
        load_order_input(isolated, "M42-r1")
    assert not runtime_eval_references(ROOT / "src/busconfig")


def runtime_eval_references(package):
    references = []
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_bytes(), filename=str(path))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Also covers literal dynamic imports and paths assembled with pathlib.
                names = [node.value]
            else:
                continue
            for name in names:
                if (
                    name.partition(".")[0] == "evals"
                    or "evals" in Path(name.replace("\\", "/")).parts
                ):
                    references.append((path.name, node.lineno))
    return references


@pytest.mark.parametrize(
    "statement",
    [
        "import evals.types as reference",
        "from evals import types",
        "from importlib import import_module\nimport_module('evals.types')",
        "from pathlib import Path\nPath('evals/gold/anchors.json').read_bytes()",
    ],
)
def test_runtime_evaluator_dependency_is_detected(tmp_path, statement):
    (tmp_path / "consumer.py").write_text(statement)
    assert runtime_eval_references(tmp_path)


@pytest.fixture
def input_dir(tmp_path):
    return shutil.copytree(INPUT_MANIFEST.parent, tmp_path / "worlds")


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"world_file": "../evals/gold/anchors.json"}, "world_file"),
        ({"expected_issues": []}, "expected_issues"),
        ({"knowledge_id": "MICA-K2"}, "knowledge snapshot"),
        ({"order_ids": ["M31-r1", "M31-r1"]}, "order inventory"),
    ],
)
def test_invalid_input_manifest(input_dir, changes, error):
    manifest = input_dir / "manifest.json"
    manifest.write_text(json.dumps(json.loads(manifest.read_bytes()) | changes))
    with pytest.raises(ValueError, match=error):
        load_order_input(input_dir, "M31-r1")


@pytest.mark.parametrize("symlink", [False, True], ids=["gold_sidecar", "redirected_world"])
def test_bundle_accepts_only_declared_regular_files(input_dir, symlink):
    if symlink:
        (input_dir / "core.yaml").unlink()
        (input_dir / "core.yaml").symlink_to(WORLD)
    else:
        (input_dir / "answers.json").write_bytes(GOLD.read_bytes())
    with pytest.raises(ValueError, match="fixture bundle"):
        load_order_input(input_dir, "M31-r1")


def test_authored_world_hash_is_checked(input_dir):
    with (input_dir / "core.yaml").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="digest"):
        load_order_input(input_dir, "M31-r1")


def repin_world(input_dir, world):
    encoded = yaml.safe_dump(world).encode()
    (input_dir / "core.yaml").write_bytes(encoded)
    manifest = input_dir / "manifest.json"
    data = json.loads(manifest.read_bytes())
    data["sha256"] = hashlib.sha256(encoded).hexdigest()
    manifest.write_text(json.dumps(data))


@pytest.mark.parametrize(
    ("keys", "value", "error"),
    [
        (("orders", "M31-r1", "rows", "L31", "acceptable_plans"), [], "evaluation field"),
        (
            ("functions", "F-BEACON", "revisions", "GLINT.1", "reference_notes"),
            "answer",
            "evaluation field",
        ),
        (("tables", "pins", "A", "header"), "Expected choice", "evaluation field"),
        (
            ("orders", "M31-r1", "rows", "L31", "cells", "B"),
            "evals/gold/anchors.json",
            "evaluation path",
        ),
    ],
)
def test_repinning_world_does_not_admit_answer_metadata(input_dir, world, keys, value, error):
    parent = world
    for key in keys[:-1]:
        parent = parent[key]
    parent[keys[-1]] = value
    repin_world(input_dir, world)
    with pytest.raises(ValueError, match=error):
        load_order_input(input_dir, "M31-r1")


def test_engineering_expectation_in_a_source_header_is_preserved(input_dir, world):
    world["tables"]["pins"]["F"] = {"header": "Expected input voltage", "scope": "PLANNED_USE"}
    world["orders"]["M32-r1"]["rows"]["P32"]["cells"]["F"] = "3 V"
    repin_world(input_dir, world)
    result = load_order_input(input_dir, "M32-r1")
    assert result["tables"]["pins"]["F"] == world["tables"]["pins"]["F"]


def test_near_duplicates_share_split(cases):
    assert SPLITS.is_file(), "missing family split manifest"
    partitions = json.loads(SPLITS.read_text(), object_pairs_hook=distinct_keys)
    assert set(partitions) == {"development", "validation", "test"}
    families = [family for members in partitions.values() for family in members]
    assert len(families) == len(set(families))
    assert set(families) == {case.family_id for case in cases.values()}
    for case in cases.values():
        assert case.family_id in partitions[case.split_id]
    for base, variant in [("E01", "E01.three-table"), ("E04", "E04.positive")]:
        assert cases[base].family_id == cases[variant].family_id
        assert cases[base].split_id == cases[variant].split_id == "development"


@pytest.mark.parametrize("change", ["two_partitions", "missing_family", "moved_variant"])
def test_split_drift_is_rejected(tmp_path, change):
    evaluation = tmp_path / "evals"
    (evaluation / "gold").mkdir(parents=True)
    partitions = json.loads(SPLITS.read_bytes())
    gold = json.loads(GOLD.read_bytes())
    if change == "two_partitions":
        partitions["test"].append("shelf-dial")
    elif change == "missing_family":
        partitions["development"].remove("shelf-dial")
    else:
        case = next(c for c in gold["cases"] if c["case_id"] == "E01.three-table")
        case["split_id"] = "validation"
    (evaluation / "splits.json").write_text(json.dumps(partitions))
    (evaluation / "gold/anchors.json").write_text(json.dumps(gold))
    with pytest.raises(ValueError, match="split|partition"):
        build_anchor_suite(evaluation_dir=evaluation)


def test_offline_case_cannot_direct_application_to_gold(tmp_path):
    (tmp_path / "gold").mkdir()
    shutil.copyfile(SPLITS, tmp_path / "splits.json")
    gold = json.loads(GOLD.read_bytes())
    gold["cases"][0]["input_paths"] = ["evals/gold/anchors.json"]
    (tmp_path / "gold/anchors.json").write_text(json.dumps(gold))
    with pytest.raises(ValueError, match="input manifest"):
        build_anchor_suite(evaluation_dir=tmp_path)


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
