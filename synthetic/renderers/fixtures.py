"""Render the Mica development anchors from the input-only world."""

import argparse
import hashlib
import json
import re
import stat
from collections import defaultdict
from io import BytesIO
from itertools import chain, groupby
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree.ElementTree import canonicalize
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import column_index_from_string, get_column_letter

from synthetic.inputs import iter_order_inputs

WORLDS = Path(__file__).resolve().parents[1] / "worlds"


def native_value(value):
    """Lists and records use ordered JSON. Excel scalars keep their native types."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value


def write_cell(sheet, row, column, value):
    value = native_value(value)
    if isinstance(value, str) and len(value) > 32767:
        raise ValueError(f"{sheet.title} row {row} column {column} exceeds 32767 characters")
    cell = sheet.cell(row, column, value)
    if isinstance(cell.value, str):
        cell.data_type = "s"  # Source text beginning with '=' is still literal evidence.
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def header(cell):
    cell.fill = PatternFill("solid", fgColor="294960")
    cell.font = Font(color="FFFFFF", bold=True)


def fit_sheet(sheet):
    for cells in sheet.columns:
        width = max(
            (len(line) for c in cells if c.value is not None for line in str(c.value).splitlines()),
            default=0,
        )
        sheet.column_dimensions[get_column_letter(cells[0].column)].width = min(
            62, max(14, width + 3)
        )
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0


def table(book, name, headings, rows):
    sheet = book.create_sheet(name)
    for number, values in enumerate((headings, *rows), 1):
        for column, value in enumerate(values, 1):
            cell = write_cell(sheet, number, column, value)
            if number == 1:
                header(cell)
    sheet.freeze_panes = "A2"
    fit_sheet(sheet)


def workbook():
    book = Workbook()
    book.remove(book.active)
    return book


def order_table(order_id, name, columns, rows):
    book = workbook()
    sheet = book.create_sheet(name)
    locations = {row_id: row["row"] for row_id, row in rows.items()}
    if len(set(locations.values())) != len(locations):
        raise ValueError(f"overlapping source rows in {order_id}/{name}")
    header_row = min(locations.values()) - 1
    if header_row < 3:
        raise ValueError("source rows overlap the title or column headers")
    scopes = {column_index_from_string(col): field["scope"] for col, field in columns.items()}
    last = max(scopes)
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last)
    write_cell(sheet, 1, 1, f"{order_id}  ·  {name}").font = Font(bold=True, size=14)
    sheet.row_dimensions[1].height = 24
    scope_row = header_row - 1
    for scope, group in groupby(range(1, last + 1), key=scopes.get):
        if scope is None:
            continue
        indexes = list(group)
        if len(indexes) > 1:
            sheet.merge_cells(
                start_row=scope_row,
                start_column=indexes[0],
                end_row=scope_row,
                end_column=indexes[-1],
            )
        write_cell(sheet, scope_row, indexes[0], scope)
    for column, field in columns.items():
        header(write_cell(sheet, header_row, column_index_from_string(column), field["header"]))
    for row in rows.values():
        if row["cells"].keys() - columns.keys():
            raise ValueError(f"source cells without column definitions in {order_id}/{name}")
        for column, value in row["cells"].items():
            write_cell(sheet, row["row"], column_index_from_string(column), value)
    fit_sheet(sheet)
    for row in rows.values():
        # Leave space for wrapped parent conditions and their dependent clauses.
        sheet.row_dimensions[row["row"]].height = 64 if name == "logic" else 36
    sheet.freeze_panes = f"A{header_row + 1}"
    return book, {"header_row": header_row, "rows": locations}


def attributes(world):
    book = workbook()
    facts = []
    for owner, function in world["functions"].items():
        roles = function.get("attribute_roles", {})
        for revision, fields in function["revisions"].items():
            facts.extend(
                (owner, revision, key, value, roles.get(key)) for key, value in fields.items()
            )
    table(
        book,
        "ConfigAttributes",
        ("Function", "Revision", "Attribute", "Value", "Decision role"),
        facts,
    )
    for group in ("controllers", "signals", "switches"):
        table(
            book,
            group.title(),
            ("ID", "Field", "Value"),
            (
                (key, field, value)
                for key, fields in world[group].items()
                for field, value in fields.items()
            ),
        )
    return book


def experience(world):
    book = workbook()
    table(
        book,
        "Policies",
        ("Policy", "Review state", "Scope", "Meaning", "When true"),
        (
            (key, p["review_state"], p["scope"], p["meaning"], p["true_means"])
            for key, p in world["policies"].items()
        ),
    )
    table(
        book,
        "Dependencies",
        (
            "Rule",
            "Review state",
            "When function",
            "When revision",
            "Required function",
            "Required revision",
            "Basis",
        ),
        (
            (
                key,
                r["review_state"],
                r["when_selected"]["function_id"],
                r["when_selected"]["config_revision_id"],
                r["requires"]["function_id"],
                r["requires"]["config_revision_id"],
                r["basis"],
            )
            for key, r in world["dependency_rules"].items()
        ),
    )
    templates = world["composition_templates"]
    table(
        book,
        "Compositions",
        ("Template", "Field", "Value"),
        (
            (key, field, value)
            for key, template in templates.items()
            for field, value in template.items()
            if field != "reviewed_trace"
        ),
    )
    signals = ("ms", "button", "ack", "call_edge", "count", "lamp_on")
    table(
        book,
        "ReviewedTrace",
        ("Template", *signals),
        (
            (key, *(sample[s] for s in signals))
            for key, template in templates.items()
            for sample in template["reviewed_trace"]
        ),
    )
    return book


def library(world):
    document = Document()
    normal = document.styles["Normal"]
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(1)
    document.add_heading(f"Mica function library  ·  {world['knowledge_id']}", 0)
    for index, (key, function) in enumerate(world["functions"].items()):
        heading = document.add_heading(f"{key} — {function['name']}", 1)
        heading.paragraph_format.page_break_before = index > 0
        if "behavior" in function:
            document.add_paragraph(function["behavior"])
        for revision, fields in function["revisions"].items():
            document.add_heading(revision, 2)
            grid = document.add_table(rows=0, cols=2)
            grid.style = "Light Shading Accent 1"
            for field, value in fields.items():
                label, data = grid.add_row().cells
                label.text = field
                data.text = str(native_value(value))
    return document


def submission(order):
    book = workbook()
    table(
        book,
        "Submission",
        ("Submission revision", "Function", "Submitted revision"),
        (
            (order["submission_revision_id"], row["function_id"], row["config_revision_id"])
            for row in order["submitted_rows"]
        ),
    )
    return book


def parent_decision(parent):
    book = workbook()
    table(
        book,
        "Decision",
        ("Revision", "Order", "Knowledge", "Scope", "Root demand", "Active rules"),
        [
            (
                parent["revision_id"],
                parent["order_id"],
                parent["knowledge_id"],
                "HISTORICAL_REFERENCE",
                parent["root_demand"],
                parent["active_dependency_rules"],
            )
        ],
    )
    table(
        book,
        "Selections",
        ("Parent revision", "Function", "Historical selection"),
        ((parent["revision_id"], owner, rev) for owner, rev in parent["selections"].items()),
    )
    return book


def save_native(document, path):
    # Omit wall-clock authoring dates from fixtures and give ZIP members fixed timestamps.
    # This also lets a retry recognize its own intact output without trusting an old manifest.
    buffer = BytesIO()
    document.save(buffer)
    with ZipFile(buffer) as source, ZipFile(path, "w") as target:
        for name in sorted(source.namelist()):
            data = source.read(name)
            if name == "docProps/core.xml":
                dates = {
                    f"{{http://purl.org/dc/terms/}}{field}" for field in ("created", "modified")
                }
                data = canonicalize(data, exclude_tags=dates).encode()
            target.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)


def build(directory, worlds):
    entries = []
    order_folders = set()

    def emit(document, folder, role, revision, metadata=None):
        suffix = ".xlsx" if isinstance(document, Workbook) else ".docx"
        path = directory / folder / (role + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError(f"duplicate native source path: {path}")
        save_native(document, path)
        entries.append(
            {
                "path": path.relative_to(directory).as_posix(),
                "role": role,
                "business_revision": revision,
                "layout_profile": f"mica-{role}-v1",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **(metadata or {}),
            }
        )

    for index, (world_hash, order_id, world) in enumerate(iter_order_inputs(worlds)):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", order_id):
            raise ValueError("unsafe order directory name")
        if index == 0:
            for role, render in (
                ("attributes", attributes),
                ("experience", experience),
                ("function-library", library),
            ):
                emit(render(world), "knowledge", role, world["knowledge_id"])
        # The documented model-free demo opens orders/E01. Its business revision is M31-r1.
        folder = Path("orders") / ("E01" if order_id == "M31-r1" else order_id)
        folder_key = folder.name.casefold()
        if folder_key in order_folders:
            raise ValueError(f"duplicate native order directory: {folder}")
        order_folders.add(folder_key)
        first_order_entry = len(entries)
        order = world["orders"][order_id]
        groups = defaultdict(dict)
        for row_id, row in order["rows"].items():
            groups[row["table"]][row_id] = row
        for name, rows in groups.items():
            if name not in ("pins", "logic", "switches", "trim"):
                raise ValueError(f"unknown order table: {name}")
            book, locations = order_table(order_id, name, world["tables"][name], rows)
            emit(book, folder, name, order_id, locations)
        if "submitted_rows" in order:
            emit(
                submission(order),
                folder,
                "submission",
                order["submission_revision_id"],
                {"order_id": order_id},
            )
        if "parent_decision" in order:
            parent = order["parent_decision"]
            emit(
                parent_decision(parent),
                folder,
                "parent-decision",
                parent["revision_id"],
                {"order_id": order_id, "scope": "HISTORICAL_REFERENCE"},
            )
        if len(entries) == first_order_entry:
            raise ValueError(f"no native sources for order: {order_id}")
    manifest = {
        "knowledge_id": world["knowledge_id"],
        "world_sha256": world_hash,
        "files": sorted(entries, key=lambda e: e["path"]),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _inventory(directory):
    versions = {}
    for path in chain((directory,), directory.rglob("*")):
        info = path.lstat()
        versions[path.relative_to(directory)] = (
            info.st_mode,
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )
    return versions


def _verify_existing(staged, output):
    # Bracket all content reads with two inventories. A per-file check alone can
    # combine successes from different versions of a directory during a retry.
    before = _inventory(output)
    expected = {p.relative_to(staged) for p in staged.rglob("*")} | {Path(".")}
    if expected != before.keys():
        raise ValueError(f"output differs from the authored bundle: {output}")
    for relative, (mode, *_) in before.items():
        source = staged / relative
        if source.is_dir() and stat.S_ISDIR(mode):
            continue
        if not (
            source.is_file()
            and stat.S_ISREG(mode)
            and source.read_bytes() == (output / relative).read_bytes()
        ):
            raise ValueError(f"output differs from the authored bundle: {output / relative}")
    if _inventory(output) != before:
        raise ValueError(f"output changed during comparison: {output}")


def render(output, worlds=WORLDS):
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temp:
        staged = Path(temp) / "anchors"
        staged.mkdir()
        build(staged, worlds)
        if output.is_symlink():
            raise ValueError("output must be a directory, not a symlink")
        try:
            staged.rename(output)
        except OSError:
            if not output.is_dir():
                raise
            _verify_existing(staged, output)
    return output / "manifest.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["anchors"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(render(args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
