"""Structural extraction of profiled native order worksheets."""

import hashlib
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import get_args

import yaml
from openpyxl import load_workbook
from openpyxl.cell.rich_text import CellRichText
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from busconfig.domain.contracts import (
    Completeness,
    Issue,
    LayoutProfile,
    ParseResult,
    SourceBlock,
    SourceDocument,
    StatementScope,
    TextSpan,
    XlsxLocator,
)
from busconfig.domain.invariants import SourceIdentityError, source_block_id

PARSER_VERSION = "xlsx-structure-v1"


def load_layout_profile(path: Path) -> LayoutProfile:
    """Load the caller's local layout configuration, independent of workbook content."""
    return LayoutProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@dataclass
class _Extraction:
    blocks: list[SourceBlock] = field(default_factory=list)
    supported: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    mapped: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    mandatory_found: bool = False

    def unsupported_region(self, region: str, reason: str) -> None:
        self.unsupported.append(region)
        self.messages.append(f"{region}: {reason}")

    def result(self, source: SourceDocument) -> ParseResult:
        return ParseResult(
            document=source,
            source_blocks=tuple(self.blocks),
            assertions=(),
            issues=tuple(
                Issue(
                    issue_id=f"{source.document_id}-parse-{number}",
                    code="PARSE_INCOMPLETE",
                    scope=source.document_id,
                    evidence_ids=(),
                    resolution_target=source.layout_profile,
                    message=message,
                )
                for number, message in enumerate(self.messages, 1)
            ),
            completeness=Completeness(
                complete=not self.messages,
                supported_regions=tuple(self.supported),
                unsupported_regions=tuple(self.unsupported),
                mapped_columns=tuple(self.mapped),
                unmapped_columns=tuple(self.unmapped),
                mandatory_sections_found=self.mandatory_found,
            ),
        )


def _raw_text(cell):
    value = cell.value
    if isinstance(value, ArrayFormula):
        return value.text or ""
    if isinstance(value, DataTableFormula) or value is None:
        return ""
    return str(value)


def _table_rows(sheet, rows, header_row, profile, extracted):
    """Stop at a second scope band. The profile describes exactly one table."""
    data_rows = sorted(row for row in rows if row > header_row)
    scopes = get_args(StatementScope)
    labels = {name for names in profile.required_headers.values() for name in names}
    for index, row in enumerate(data_rows):
        values = [sheet.cell(row, col).value for col in rows[row]]
        if not any(value in scopes for value in values):
            continue
        separate_band = all(value in scopes for value in values) and (
            row - 1 not in rows or len(values) > 1
        )
        known_header = any(
            _raw_text(sheet.cell(row + 1, col)) in labels for col in rows.get(row + 1, ())
        )
        if separate_band or known_header:
            remainder = set.union(*(rows[r] for r in data_rows[index:]))
            start = sheet.cell(row, min(remainder)).coordinate
            end = sheet.cell(data_rows[-1], max(remainder)).coordinate
            extracted.unsupported_region(f"{sheet.title}!{start}:{end}", "unexpected scope band")
            return data_rows[:index]
    return data_rows


def _map_headers(sheet, band_row, columns, profile, unsupported_merges, extracted):
    # Only a horizontal merge *in the scope band* grants inheritance.
    band_merges = {
        col: region
        for region in sheet.merged_cells.ranges
        if region.min_row == region.max_row == band_row
        for col in range(region.min_col, region.max_col + 1)
    }
    contexts = {}
    pairs = {}
    for col in columns:
        merge = band_merges.get(col)
        scope = sheet.cell(band_row, merge.min_col if merge else col)
        header = sheet.cell(band_row + 1, col)
        contexts[col] = {
            "header": _raw_text(header),
            "header_cell": header.coordinate,
            "scope_text": _raw_text(scope),
            "scope_cell": scope.coordinate,
            "scope_range": str(merge) if merge else None,
            "statement_scope": None,
        }
        if any(header.coordinate in r or scope.coordinate in r for r in unsupported_merges):
            continue
        if scope.data_type == header.data_type == "s" and not (
            scope.font.strike
            or header.font.strike
            or isinstance(scope.value, CellRichText)
            or isinstance(header.value, CellRichText)
        ):
            pairs[col] = (scope.value, header.value)

    counts = Counter(pairs.values())
    required = {
        (scope, name) for scope, names in profile.required_headers.items() for name in names
    }
    mapped = set()
    for col, context in contexts.items():
        pair = pairs.get(col)
        address = f"{sheet.title}!{get_column_letter(col)}"
        if pair in required and counts[pair] == 1:
            extracted.mapped.append(address)
            mapped.add(pair)
            context["statement_scope"] = pair[0]
            extracted.supported.append(f"{sheet.title}!{context['header_cell']}")
        else:
            extracted.unmapped.append(address)
            extracted.messages.append(
                f"{sheet.title}!{context['header_cell']}: unmapped or ambiguous header "
                f"{context['header']!r} under {context['scope_text']!r} at {context['scope_cell']}"
            )
    missing = required - mapped
    extracted.mandatory_found = not missing
    for scope, name in sorted(missing):
        extracted.messages.append(f"{sheet.title}: missing required header {name!r} in {scope}")
    return contexts


def _data_block(cell, source, metadata, unresolved):
    raw = _raw_text(cell)
    locator = XlsxLocator(
        sheet=cell.parent.title,
        cells=(cell.coordinate,),
        text_span=TextSpan(start=0, end=len(raw)),
    )
    return SourceBlock(
        block_id=source_block_id(source, locator),
        document_id=source.document_id,
        document_hash=source.byte_hash,
        locator=locator,
        raw_text=raw,
        effective_status="UNRESOLVED" if unresolved else "CURRENT",
        formatting=metadata,
    )


def _restore_link_blanks(sheet, data):
    # The editable openpyxl view binds hyperlinks by filling an empty cell with
    # the target. Its streaming view reads the original value without that substitution.
    ambiguous = {
        cell.coordinate: cell
        for cell in sheet._cells.values()
        if cell.hyperlink and cell.value in (cell.hyperlink.target, cell.hyperlink.location)
    }
    if not ambiguous:
        return
    with closing(load_workbook(BytesIO(data), read_only=True, keep_links=False)) as raw_book:
        linked = ambiguous.values()
        region = raw_book[sheet.title].iter_rows(
            min_row=min(c.row for c in linked),
            max_row=max(c.row for c in linked),
            min_col=min(c.column for c in linked),
            max_col=max(c.column for c in linked),
        )
        for row in region:
            for cell in row:
                if cell.value is not None:
                    ambiguous.pop(cell.coordinate, None)
    for cell in ambiguous.values():
        cell.value = None


def _extract_sheet(sheet, source, profile, extracted):
    # iter_rows() materializes the bounding rectangle, including distant, unauthored cells.
    # Index the native cells once before requesting blank cells in profiled rows.
    rows = defaultdict(set)
    for cell in sheet._cells.values():
        if cell.row > profile.preamble_rows and (cell.value is not None or cell.hyperlink):
            rows[cell.row].add(cell.column)
    if not rows:
        extracted.unsupported_region(sheet.title, "missing scope band and field headers")
        return
    band_row = min(rows)
    header_row = band_row + 1
    data_rows = _table_rows(sheet, rows, header_row, profile, extracted)
    columns = sorted(set.union(rows[band_row], rows[header_row], *(rows[r] for r in data_rows)))
    # These profiles declare no grouped data rows or merged field labels.
    unsupported_merges = sorted(
        (
            r
            for r in sheet.merged_cells.ranges
            if r.max_row >= band_row and not (r.min_row == r.max_row == band_row)
        ),
        key=str,
    )
    for region in unsupported_merges:
        extracted.unsupported_region(f"{sheet.title}!{region}", "merge outside the scope band")
    contexts = _map_headers(sheet, band_row, columns, profile, unsupported_merges, extracted)
    if not data_rows:
        extracted.mandatory_found = False
        extracted.messages.append(f"{sheet.title}: missing data rows beneath the headers")
        return
    hidden_band = any(sheet.row_dimensions[r].hidden for r in (band_row, header_row))
    hidden_table = hidden_band or sheet.sheet_state != "visible"
    if hidden_table:
        extracted.unsupported_region(sheet.title, "sheet or header band is hidden")

    for row in data_rows:
        hidden_row = bool(sheet.row_dimensions[row].hidden)
        if hidden_row:
            extracted.unsupported_region(f"{sheet.title}!{row}:{row}", "hidden data row")
        for col, context in contexts.items():
            cell = sheet.cell(row, col)
            metadata = dict(context, row_hidden=hidden_row, data_type=cell.data_type)
            unresolved = hidden_table or hidden_row or context["statement_scope"] is None
            for region in unsupported_merges:
                if cell.coordinate in region:
                    unresolved = True
                    metadata["merged_range"] = str(region)
            if cell.hyperlink:
                metadata["hyperlink"] = cell.hyperlink.target or cell.hyperlink.location
            if isinstance(cell.value, (ArrayFormula, DataTableFormula)):
                metadata["formula_attributes"] = dict(cell.value)
            review = {"f": "formula requires value review", "e": "spreadsheet error"}.get(
                cell.data_type
            )
            if cell.font.strike or isinstance(cell.value, CellRichText):
                review = "effective text requires formatting review"
            if review:
                extracted.unsupported_region(f"{sheet.title}!{cell.coordinate}", review)
            block = _data_block(cell, source, metadata, unresolved or bool(review))
            extracted.blocks.append(block)
            if block.effective_status == "CURRENT":
                extracted.supported.append(f"{sheet.title}!{cell.coordinate}")


def parse_xlsx(source: SourceDocument, profile: LayoutProfile) -> ParseResult:
    """Read pinned local bytes. Formula expressions and link targets remain inert data."""
    if (source.layout_profile, source.role) != (profile.profile_id, profile.role):
        raise ValueError("Declared source role and layout must match the supplied profile")
    if source.parser_version != PARSER_VERSION:
        raise ValueError(f"Expected parser version {PARSER_VERSION}")
    data = Path(source.original_path).read_bytes()
    if "sha256:" + hashlib.sha256(data).hexdigest() != source.byte_hash:
        raise SourceIdentityError("SOURCE_HASH_MISMATCH", source.document_id)

    extracted = _Extraction()
    with closing(
        load_workbook(BytesIO(data), data_only=False, keep_links=False, rich_text=True)
    ) as book:
        for name in book.sheetnames:
            if name != profile.sheet:
                extracted.unsupported_region(name, "no sheet mapping in this layout")
        if profile.sheet in {sheet.title for sheet in book.worksheets}:
            sheet = book[profile.sheet]
            _restore_link_blanks(sheet, data)
            _extract_sheet(sheet, source, profile, extracted)
        else:
            extracted.unsupported_region(profile.sheet, "required worksheet missing")
    return extracted.result(source)
