import hashlib
from pathlib import Path

import pytest
from openpyxl import load_workbook

from busconfig.domain.contracts import ParseResult, SourceDocument
from busconfig.domain.invariants import SourceIdentityError
from busconfig.ingest.xlsx_parser import PARSER_VERSION, load_layout_profile, parse_xlsx

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = ROOT / "tests/fixtures/anchors/orders/M32-r1"
SAMPLES = ROOT / "tests/fixtures/xlsx"


def source_for(path, role, revision="M32-r1"):
    profile_id = f"mica-{role}-v1"
    return SourceDocument(
        document_id=f"DOC-{revision}-{role}",
        role=role,
        business_revision=revision,
        byte_hash="sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        original_path=str(path),
        layout_profile=profile_id,
        parser_version=PARSER_VERSION,
    )


def parse(path, role, revision="M32-r1"):
    source = source_for(path, role, revision)
    profile = load_layout_profile(ROOT / "config/layouts" / f"{source.layout_profile}.yaml")
    return parse_xlsx(source, profile)


def test_merged_multiline_cells_keep_provenance():
    result = parse(ANCHOR / "logic.xlsx", "logic")
    assert result.completeness.complete
    assert {"logic!A8", "logic!B8", "logic!C8"} <= set(result.completeness.supported_regions)
    assert not result.issues
    blocks = {block.locator.cells: block for block in result.source_blocks}
    description = blocks[("B8",)]
    assert description.locator.sheet == "logic"
    assert description.raw_text == (
        "Tide step. While the gallery is awake advance through 0/2/5/0, once per actuation.\n"
        "While asleep ignore it."
    )
    assert description.formatting["header"] == "Control description"
    assert description.formatting["header_cell"] == "B7"
    assert description.formatting["scope_cell"] == "A6"
    assert description.formatting["scope_range"] == "A6:C6"
    assert description.formatting["statement_scope"] == "CURRENT_ORDER"
    assert description.locator.text_span.end == len(description.raw_text)
    assert blocks[("C8",)].raw_text == ""
    assert ParseResult.model_validate_json(result.model_dump_json()) == result


def test_current_history_planned_columns_stay_separate():
    result = parse(ANCHOR / "pins.xlsx", "pins")
    assert result.completeness.complete
    assert not result.issues
    endpoints = {
        block.locator.cells: (block.raw_text, block.formatting["statement_scope"])
        for block in result.source_blocks
    }
    assert endpoints[("B6",)] == ("DIAL-A", "CURRENT_ORDER")
    assert endpoints[("D6",)] == ("DIAL-B", "HISTORICAL_REFERENCE")
    assert endpoints[("E6",)] == ("spare input", "PLANNED_USE")
    assert result.document.business_revision == "M32-r1"


def test_reordered_columns_follow_their_native_headers():
    result = parse(SAMPLES / "reordered/pins.xlsx", "pins", "reordered-r1")
    assert result.completeness.complete
    by_cell = {block.locator.cells: block for block in result.source_blocks}
    assert by_cell[("D6",)].formatting["statement_scope"] == "PLANNED_USE"
    assert by_cell[("E6",)].formatting["statement_scope"] == "HISTORICAL_REFERENCE"
    assert by_cell[("E6",)].raw_text == "DIAL-B"
    assert by_cell[("C6",)].raw_text == "Reed collar\n  Keep original spacing."


def test_unmerged_blank_band_and_wrong_scope_remain_unmapped():
    result = parse(SAMPLES / "partial/pins.xlsx", "pins", "partial-r1")
    assert not result.completeness.complete
    assert not result.completeness.mandatory_sections_found
    assert result.completeness.unmapped_columns == ("pins!B", "pins!C", "pins!D")
    assert "Unprofiled" in result.completeness.unsupported_regions
    assert "pins!A6" in result.completeness.supported_regions
    assert "pins!D6" not in result.completeness.supported_regions
    assert all(issue.code == "PARSE_INCOMPLETE" for issue in result.issues)
    assert any(
        "D5" in issue.message and "Prior order connection" in issue.message
        for issue in result.issues
    )
    by_cell = {block.locator.cells: block for block in result.source_blocks}
    assert by_cell[("D6",)].raw_text == "DIAL-B"
    for ref in ("B6", "C6", "D6"):
        assert by_cell[(ref,)].effective_status == "UNRESOLVED"
        assert by_cell[(ref,)].formatting["statement_scope"] is None
    assert by_cell[("E6",)].formatting["statement_scope"] == "PLANNED_USE"


def test_ambiguous_header_never_picks_first_match(tmp_path):
    book = load_workbook(ANCHOR / "logic.xlsx", keep_links=False)
    book["logic"]["C7"] = "Control description"
    path = tmp_path / "duplicate.xlsx"
    book.save(path)
    result = parse(path, "logic")
    assert not result.completeness.mandatory_sections_found
    assert result.completeness.unmapped_columns == ("logic!B", "logic!C")
    assert result.issues


def test_field_header_merged_into_data_is_not_a_valid_mapping(tmp_path):
    book = load_workbook(ANCHOR / "pins.xlsx", keep_links=False)
    book["pins"].merge_cells("D5:D6")
    path = tmp_path / "vertical-header.xlsx"
    book.save(path)
    result = parse(path, "pins")
    assert result.completeness.unmapped_columns == ("pins!D",)
    assert "pins!D5:D6" in result.completeness.unsupported_regions
    assert not result.completeness.mandatory_sections_found
    cell = next(b for b in result.source_blocks if b.locator.cells == ("D6",))
    assert cell.formatting["statement_scope"] is None


def test_hidden_rows_blanks_and_formulas_remain_source_data(tmp_path):
    book = load_workbook(ANCHOR / "logic.xlsx", keep_links=False)
    sheet = book["logic"]
    sheet["B9"] = "  Keep both spaces.\n   And the indentation.  "
    sheet["B9"].hyperlink = "https://example.invalid/external.xlsx"
    sheet.row_dimensions[9].hidden = True
    sheet["C10"] = "='[external.xlsx]Sheet1'!A1"
    path = tmp_path / "unresolved.xlsx"
    book.save(path)
    result = parse(path, "logic")
    by_cell = {block.locator.cells: block for block in result.source_blocks}
    assert by_cell[("A9",)].raw_text == ""
    assert by_cell[("B9",)].raw_text == "  Keep both spaces.\n   And the indentation.  "
    assert by_cell[("B9",)].formatting["row_hidden"] is True
    assert by_cell[("B9",)].formatting["hyperlink"] == "https://example.invalid/external.xlsx"
    assert by_cell[("B9",)].effective_status == "UNRESOLVED"
    assert by_cell[("C10",)].raw_text == "='[external.xlsx]Sheet1'!A1"
    assert by_cell[("C10",)].formatting["data_type"] == "f"
    assert by_cell[("C10",)].effective_status == "UNRESOLVED"
    assert not result.completeness.complete
    assert result.assertions == ()


@pytest.mark.parametrize(
    ("role", "cell", "raw"),
    [
        ("switches", "D5", "PETAL"),
        ("trim", "A4", "Route tag"),
    ],
)
def test_other_order_layouts_have_their_own_mappings(role, cell, raw):
    directory = ANCHOR if role == "switches" else ANCHOR.parent / "M33-r1"
    result = parse(directory / f"{role}.xlsx", role, revision=directory.name)
    assert result.completeness.complete
    block = next(b for b in result.source_blocks if b.locator.cells == (cell,))
    assert block.locator.sheet == role
    assert block.raw_text == raw
    assert block.formatting["statement_scope"] == "CURRENT_ORDER"


def test_header_only_sheet_reports_missing_data(tmp_path):
    book = load_workbook(ANCHOR / "pins.xlsx", keep_links=False)
    book["pins"].delete_rows(6)
    path = tmp_path / "only-headers.xlsx"
    book.save(path)
    result = parse(path, "pins")
    assert not result.completeness.complete
    assert not result.completeness.mandatory_sections_found
    assert result.issues
    assert not result.source_blocks


@pytest.mark.parametrize("heading", ["Prior order connection", "Archived endpoint designation"])
def test_second_table_cannot_inherit_first_tables_scopes(tmp_path, heading):
    book = load_workbook(ANCHOR / "pins.xlsx", keep_links=False)
    sheet = book["pins"]
    sheet["B8"] = "HISTORICAL_REFERENCE"
    sheet["B9"] = heading
    sheet["B10"] = "archived endpoint"
    path = tmp_path / "two-tables.xlsx"
    book.save(path)
    result = parse(path, "pins")
    assert not result.completeness.complete
    assert result.issues
    assert any(
        "B8" in region and "B10" in region for region in result.completeness.unsupported_regions
    )
    assert all(
        b.formatting["statement_scope"] != "CURRENT_ORDER"
        for b in result.source_blocks
        if b.raw_text == "archived endpoint"
    )


def test_scope_word_in_data_does_not_start_a_header_band(tmp_path):
    book = load_workbook(ANCHOR / "logic.xlsx", keep_links=False)
    book["logic"]["B9"] = "HISTORICAL_REFERENCE"
    book["logic"]["B10"] = "Keep this line as well."
    path = tmp_path / "scope-word.xlsx"
    book.save(path)
    result = parse(path, "logic")
    assert result.completeness.complete
    blocks = {b.locator.cells: b for b in result.source_blocks}
    assert blocks[("B9",)].raw_text == "HISTORICAL_REFERENCE"
    assert blocks[("B9",)].formatting["statement_scope"] == "CURRENT_ORDER"
    assert blocks[("B10",)].raw_text == "Keep this line as well."


def test_link_target_does_not_fill_a_blank_cell(tmp_path):
    book = load_workbook(ANCHOR / "logic.xlsx", keep_links=False)
    sheet = book["logic"]
    target = "https://example.invalid/linked.xlsx"
    sheet["B10"] = target
    sheet["B10"].hyperlink = target
    sheet["B10"].hyperlink.ref = "B9:B10"
    path = tmp_path / "link-labels.xlsx"
    book.save(path)
    blocks = {b.locator.cells: b for b in parse(path, "logic").source_blocks}
    assert blocks[("B9",)].raw_text == ""
    assert blocks[("B10",)].raw_text == target
    assert blocks[("B9",)].formatting["hyperlink"] == target


def test_hash_and_declared_layout_are_verified_before_mapping():
    path = ANCHOR / "pins.xlsx"
    source = source_for(path, "pins")
    pins = load_layout_profile(ROOT / "config/layouts/mica-pins-v1.yaml")
    logic = load_layout_profile(ROOT / "config/layouts/mica-logic-v1.yaml")
    with pytest.raises(SourceIdentityError, match="SOURCE_HASH_MISMATCH"):
        parse_xlsx(source.model_copy(update={"byte_hash": "sha256:" + "0" * 64}), pins)
    with pytest.raises(ValueError, match="layout"):
        parse_xlsx(source, logic)
