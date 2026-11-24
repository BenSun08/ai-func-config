"""Audit hand-authored answers against the invented world, without a matcher."""

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from docx import Document
from openpyxl import load_workbook

from evals.types import build_anchor_suite
from synthetic.inputs import load_order_input
from synthetic.renderers.fixtures import render

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "evals/gold/anchors.json"
WORLD = ROOT / "synthetic/worlds/core.yaml"
INPUT_MANIFEST = WORLD.with_name("manifest.json")
SPLITS = ROOT / "evals/splits.json"


def render_fixtures(destination, cwd=ROOT):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "synthetic.renderers.fixtures",
            "--suite",
            "anchors",
            "--output",
            str(destination),
        ],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def native_content(path):
    """Read structure, locators and typed values independently of the renderer."""
    if path.suffix == ".xlsx":
        book = load_workbook(path)
        return [
            (
                s.title,
                sorted(str(area) for area in s.merged_cells.ranges),
                [
                    (c.coordinate, c.data_type, c.value)
                    for row in s
                    for c in row
                    if c.value is not None
                ],
            )
            for s in book
        ]
    assert path.suffix == ".docx"
    document = Document(path)
    return [
        (block.style.name, block.text)
        if hasattr(block, "text")
        else [[c.text for c in row.cells] for row in block.rows]
        for block in document.iter_inner_content()
    ]


def test_fixture_manifest_hashes(tmp_path, world, native_bundle):
    expected_paths = {
        "knowledge/attributes.xlsx",
        "knowledge/experience.xlsx",
        "knowledge/function-library.docx",
        "orders/M38-r1/submission.xlsx",
        "orders/M42-r2/parent-decision.xlsx",
    }
    for order_id, order in world["orders"].items():
        directory = "E01" if order_id == "M31-r1" else order_id
        expected_paths.update(
            f"orders/{directory}/{r['table']}.xlsx" for r in order["rows"].values()
        )

    second = tmp_path / "second"
    command = render_fixtures(second)
    assert command.returncode == 0, command.stderr
    snapshots = []
    for destination in (native_bundle, second, ROOT / "tests/fixtures/anchors"):
        manifest_path = destination / "manifest.json"
        assert manifest_path.is_file(), f"missing native fixture manifest: {manifest_path}"
        manifest = json.loads(manifest_path.read_bytes())
        assert manifest["knowledge_id"] == "MICA-K1"
        assert manifest["world_sha256"] == hashlib.sha256(WORLD.read_bytes()).hexdigest()
        entries = {entry["path"]: entry for entry in manifest["files"]}
        assert len(entries) == len(manifest["files"])
        assert entries.keys() == expected_paths
        order_sources = {
            entry.get("order_id", entry["business_revision"])
            for path, entry in entries.items()
            if path.startswith("orders/")
        }
        assert order_sources == set(json.loads(INPUT_MANIFEST.read_bytes())["order_ids"])
        assert {
            p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()
        } == expected_paths | {"manifest.json"}
        snapshot = {}
        for relative, entry in entries.items():
            path = destination / relative
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
            snapshot[relative] = (entry | {"sha256": None}, native_content(path))
        snapshots.append(snapshot)
    assert snapshots[0] == snapshots[1] == snapshots[2]


@pytest.fixture(scope="module")
def native_bundle(tmp_path_factory):
    path = tmp_path_factory.mktemp("rendered")
    result = render_fixtures(path)
    assert result.returncode == 0, result.stderr
    return path


def test_order_cells_headers_and_scopes_match_world(native_bundle, world):
    manifest = json.loads((native_bundle / "manifest.json").read_bytes())
    entries = {(entry["business_revision"], entry["role"]): entry for entry in manifest["files"]}
    for order_id, order in world["orders"].items():
        for row_id, row in order["rows"].items():
            table, number = row["table"], row["row"]
            entry = entries[order_id, table]
            assert entry["rows"][row_id] == number
            sheet = load_workbook(native_bundle / entry["path"])[table]
            for column, field in world["tables"][table].items():
                assert sheet[f"{column}{entry['header_row']}"].value == field["header"]
                scope_cell = sheet[f"{column}{entry['header_row'] - 1}"]
                for area in sheet.merged_cells.ranges:
                    if scope_cell.coordinate in area:
                        scope_cell = sheet.cell(area.min_row, area.min_col)
                assert scope_cell.value == field["scope"]
                cell = sheet[f"{column}{number}"]
                value = row["cells"].get(column)
                assert type(cell.value) is type(value) and cell.value == value
                assert cell.data_type != "f"


def test_native_knowledge_and_order_history(native_bundle, world):
    knowledge = native_bundle / "knowledge"
    document = Document(knowledge / "function-library.docx")
    headings = [
        (p.style.name, p.text) for p in document.paragraphs if p.style.name.startswith("Heading")
    ]
    expected = []
    for owner, function in world["functions"].items():
        expected.append(("Heading 1", f"{owner} — {function['name']}"))
        expected.extend(("Heading 2", revision) for revision in function["revisions"])
    assert headings == expected
    assert world["functions"]["F-LEVEL"]["behavior"] in [p.text for p in document.paragraphs]
    sheet = load_workbook(knowledge / "attributes.xlsx")["ConfigAttributes"]
    facts = list(sheet.values)
    assert ("F-BEACON", "GLINT.1", "resets_on_clear", False, "REQUIRED_CONDITION") in facts
    assert ("F-BEACON", "GLINT.1", "lens", "lilac", "PREFERENCE") in facts
    delay = next(row[3] for row in facts if row[1:3] == ("SEND.1", "emit_delay_ms"))
    assert type(delay) is int and delay == 0
    rules = load_workbook(knowledge / "experience.xlsx")
    assert (
        "FOLLOW.1",
        "RELEASED",
        "F-CALL",
        "SEND.1",
        "F-LAMP",
        "PULSE.1",
        world["dependency_rules"]["FOLLOW.1"]["basis"],
    ) in list(rules["Dependencies"].values)
    assert ("RELAY.1", 28, True, False, False, 1, True) in list(rules["ReviewedTrace"].values)
    orders = native_bundle / "orders"
    submitted = list(load_workbook(orders / "M38-r1/submission.xlsx").active.values)
    assert submitted[1:] == [("TRIM-D4", "F-TAG", "INK.1"), ("TRIM-D4", "F-TAG", "INK.2")]
    parent = load_workbook(orders / "M42-r2/parent-decision.xlsx")
    assert list(parent["Selections"].values)[1:] == [
        ("CALL-D1", "F-CALL", "SEND.1"),
        ("CALL-D1", "F-LAMP", "PULSE.1"),
    ]
    assert "HISTORICAL_REFERENCE" in list(parent["Decision"].values)[1]


def test_render_reuses_intact_bundle_and_rejects_foreign_files(tmp_path):
    destination = tmp_path / "anchors"
    assert render_fixtures(destination).returncode == 0
    manifest = destination / "manifest.json"
    original = manifest.read_bytes()
    assert render_fixtures(destination).returncode == 0
    assert manifest.read_bytes() == original
    foreign = destination / "unexpected.txt"
    foreign.write_text("keep this file")
    assert render_fixtures(destination).returncode != 0
    assert foreign.read_text() == "keep this file"
    assert manifest.read_bytes() == original


def test_native_logic_keeps_multiline_parent_and_exception(native_bundle):
    sheet = load_workbook(native_bundle / "orders/M32-r1/logic.xlsx")["logic"]
    assert sheet["B8"].value == (
        "Tide step. While the gallery is awake advance through 0/2/5/0, once per actuation.\n"
        "While asleep ignore it."
    )


def test_empty_order_inventory_cannot_publish_a_native_manifest(input_dir, tmp_path):
    inventory = input_dir / "manifest.json"
    inventory.write_text(json.dumps(json.loads(inventory.read_bytes()) | {"order_ids": []}))
    destination = tmp_path / "out"
    with pytest.raises(ValueError):
        render(destination, input_dir)
    assert not destination.exists()


def test_render_uses_native_columns_and_literal_text(input_dir, world, tmp_path):
    fields = world["tables"]["pins"]
    # YAML mapping order has no bearing on the position of a spreadsheet column.
    world["tables"]["pins"] = {col: fields[col] for col in "ADBEC"}
    world["orders"]["M32-r1"]["rows"]["P32"]["cells"]["C"] = "=1+2"
    repin_world(input_dir, world)
    dest = tmp_path / "out"
    render(dest, input_dir)
    pins = load_workbook(dest / "orders/M32-r1/pins.xlsx").active
    assert {str(area) for area in pins.merged_cells.ranges} >= {"A4:C4"}
    assert pins["D4"].value == "HISTORICAL_REFERENCE"
    assert pins["E4"].value == "PLANNED_USE"
    assert (pins["C6"].value, pins["C6"].data_type) == ("=1+2", "s")


@pytest.mark.parametrize("fault", ["duplicate_locator", "unscoped_cell"])
def test_untraceable_rows_cannot_publish_an_order(input_dir, world, tmp_path, fault):
    rows = world["orders"]["M37-r1"]["rows"]
    if fault == "duplicate_locator":
        rows["S37b"]["row"] = rows["S37a"]["row"]
    else:
        rows["S37a"]["cells"]["J"] = "unmapped note"
    repin_world(input_dir, world)
    destination = tmp_path / "out"
    with pytest.raises(ValueError):
        render(destination, input_dir)
    assert not destination.exists()


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
    assert not runtime_eval_references(ROOT / "synthetic/renderers")
    # Run the real command in a checkout containing only the fixture code and its inputs.
    shutil.copytree(
        ROOT / "synthetic", tmp_path / "synthetic", ignore=shutil.ignore_patterns("__pycache__")
    )
    generated = render_fixtures(tmp_path / "native", cwd=tmp_path)
    assert generated.returncode == 0, generated.stderr


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
    encoded = yaml.safe_dump(world, sort_keys=False).encode()
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
        assert key not in result, f"repeated key {key!r}"
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


@pytest.mark.parametrize("label", ["Correct answer", "Reference answer", "Correct configuration"])
def test_correct_answer_header_cannot_reach_native_inputs(input_dir, world, tmp_path, label):
    world["tables"]["logic"]["D"] = {"header": label, "scope": "CURRENT_ORDER"}
    world["orders"]["M31-r1"]["rows"]["L31"]["cells"]["D"] = "LEVEL-A.1"
    repin_world(input_dir, world)
    destination = tmp_path / "native"
    with pytest.raises(ValueError, match="evaluation field"):
        render(destination, input_dir)
    assert not destination.exists()


def test_pinned_order_cannot_be_relabelled_into_a_holdout_split(tmp_path):
    evaluation = shutil.copytree(ROOT / "evals", tmp_path / "evals")
    answers = json.loads(GOLD.read_bytes())
    original = next(case for case in answers["cases"] if case["case_id"] == "E01")
    answers["cases"].append(
        original | {"case_id": "Mica-copy", "family_id": "renamed-shelf", "split_id": "test"}
    )
    partitions = json.loads(SPLITS.read_bytes())
    partitions["test"].append("renamed-shelf")
    (evaluation / "gold/anchors.json").write_text(json.dumps(answers))
    (evaluation / "splits.json").write_text(json.dumps(partitions))
    with pytest.raises(ValueError, match="family|split"):
        build_anchor_suite(evaluation_dir=evaluation)


@pytest.mark.parametrize(
    "original,repeated",
    [
        ("B: DIAL-A, C: Reed collar", "B: DIAL-B, B: DIAL-A, C: Reed collar"),
        ("B: DIAL-A, C: Reed collar", "<<: {B: DIAL-B, B: DIAL-A}, C: Reed collar"),
        ("      P32: {table:", "      P32: {}\n      P32: {table:"),
    ],
)
def test_raw_duplicate_yaml_key_rejected_before_render(input_dir, tmp_path, original, repeated):
    source = input_dir / "core.yaml"
    text = source.read_text()
    assert text.count(original) == 1
    source.write_text(text.replace(original, repeated))
    manifest = input_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            json.loads(manifest.read_bytes())
            | {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        )
    )
    destination = tmp_path / "out"
    with pytest.raises(ValueError, match="duplicate"):
        render(destination, input_dir)
    assert not destination.exists()


def test_scoped_orders_do_not_share_mutable_catalog_values(input_dir):
    from synthetic.inputs import iter_order_inputs

    orders = iter_order_inputs(input_dir)
    digest, _, first = next(orders)
    first["functions"]["F-TAG"]["revisions"]["INK.1"]["socket"] = "locally-edited"
    next_digest, _, second = next(orders)
    assert next_digest == digest
    assert second["functions"]["F-TAG"]["revisions"]["INK.1"]["socket"] == "slate"


@pytest.mark.parametrize("extra_id", ["E01", "M43-r1"])
def test_each_pinned_order_requires_its_own_native_sources(input_dir, world, tmp_path, extra_id):
    # A trim-only order would otherwise fit alongside the M31 logic book in orders/E01.
    world["orders"][extra_id] = world["orders"]["M33-r1"] if extra_id == "E01" else {"rows": {}}
    repin_world(input_dir, world)
    manifest = input_dir / "manifest.json"
    data = json.loads(manifest.read_bytes())
    data["order_ids"].append(extra_id)
    manifest.write_text(json.dumps(data))
    destination = tmp_path / "out"
    with pytest.raises(ValueError, match="order"):
        render(destination, input_dir)
    assert not destination.exists()


def test_xlsx_never_truncates_an_engineering_exception(input_dir, world, tmp_path):
    text = "x" * 32767 + " EXCEPT WHILE ASLEEP"
    world["orders"]["M31-r1"]["rows"]["L31"]["cells"]["B"] = text
    repin_world(input_dir, world)
    destination = tmp_path / "out"
    with pytest.raises(ValueError, match="32767|32,767"):
        render(destination, input_dir)
    assert not destination.exists()


def test_render_retry_rejects_files_changed_during_comparison(native_bundle, tmp_path, monkeypatch):
    import builtins
    import io

    destination = shutil.copytree(native_bundle, tmp_path / "retry")
    files = [destination / "orders/M33-r1/trim.xlsx", destination / "orders/M38-r1/submission.xlsx"]
    originals = {file: file.read_bytes() for file in files}
    edits = {file: b"X" + content[1:] for file, content in originals.items()}
    for file in files:
        file.write_bytes(edits[file])
    seen = []

    # Interleave real writes at the read boundaries, independent of traversal order.
    # One workbook is always wrong, although both reads receive their original bytes.
    def interleaved(open_file):
        def open_with_edits(path, mode="r", *args, **kwargs):
            if mode == "rb" and not isinstance(path, int):
                file = Path(path)
                if file in originals and file not in seen:
                    if seen:
                        seen[0].write_bytes(edits[seen[0]])
                    file.write_bytes(originals[file])
                    seen.append(file)
            return open_file(path, mode, *args, **kwargs)

        return open_with_edits

    monkeypatch.setattr(builtins, "open", interleaved(builtins.open))
    monkeypatch.setattr(io, "open", interleaved(io.open))
    with pytest.raises(ValueError, match="differs|changed"):
        render(destination)
    monkeypatch.undo()
    assert any(file.read_bytes() != originals[file] for file in files)


def test_e08_native_trace_meets_the_press_and_ack_deadlines(native_bundle):
    sheet = load_workbook(native_bundle / "knowledge/experience.xlsx")["ReviewedTrace"]
    trace = [row[1:] for row in list(sheet.values)[1:] if row[0] == "RELAY.1"]
    assert all(tuple(map(type, sample)) == (int, bool, bool, bool, int, bool) for sample in trace)
    # Hand-checked bench samples: ms, button, ACK, pulse, counted presses, lamp.
    # A held button counts once. The 20 ms edge lights by 32 ms; ACK at 60 clears by 72.
    assert trace == [
        (0, False, False, False, 0, False),
        (20, True, False, True, 1, False),
        (28, True, False, False, 1, True),
        (60, True, True, False, 1, True),
        (72, True, True, False, 1, False),
        (100, False, True, False, 1, False),
    ]


def test_native_revision_fields_stay_with_their_owner(native_bundle, world):
    from docx.table import Table

    doc = Document(native_bundle / "knowledge/function-library.docx")
    fields = {}
    owner = revision = None
    for block in doc.iter_inner_content():
        if isinstance(block, Table):
            key = (owner, revision)
            assert key not in fields
            pairs = [tuple(cell.text for cell in row.cells) for row in block.rows]
            fields[key] = distinct_keys(pairs)
        elif block.style.name == "Heading 1":
            owner, revision = block.text.split(" — ", 1)[0], None
        elif block.style.name == "Heading 2":
            revision = block.text
    # Independently reviewed native values for the only complete E01 alternative.
    dial = fields["F-LEVEL", "LEVEL-A.1"]
    assert (dial["binding"], dial["mechanism"], json.loads(dial["sequence"])) == (
        "DIAL-A",
        "momentary",
        [0, 2, 5, 0],
    )
    expected = {
        (owner, rev): values
        for owner, function in world["functions"].items()
        for rev, values in function["revisions"].items()
    }
    assert fields.keys() == expected.keys()
    for key, values in expected.items():
        assert fields[key].keys() == values.keys()
        for field, value in values.items():
            text = fields[key][field]
            if isinstance(value, (list, dict)):
                assert json.loads(text) == value
            else:
                assert text == str(value)
