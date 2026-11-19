"""Read one order and its catalog from the authored input-only fixture directory."""

import hashlib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

import yaml
from pydantic import Field

from busconfig.domain.contracts import DomainModel, KnowledgeSnapshotId, OrderSnapshotId


class _InputManifest(DomainModel):
    world_file: Literal["core.yaml"]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    knowledge_id: KnowledgeSnapshotId
    order_ids: Annotated[tuple[OrderSnapshotId, ...], Field(min_length=1)]


# These are evaluator annotations. Submitted rows, previous selections and
# reviewed catalog traces are legitimate engineering records and stay intact.
_REFERENCE_FIELDS = {
    "acceptable_plans",
    "answer",
    "answers",
    "case_id",
    "evidence_links",
    "expected",
    "failed_conditions",
    "family_id",
    "gold",
    "ground_truth",
    "outcome",
    "ranks",
    "reference_notes",
    "row_probe",
    "scenario_id",
    "score_probe",
    "scores",
    "split_id",
    "tied_revisions",
}


def _check_label(name: str) -> None:
    label = name.strip().casefold().replace("-", "_").replace(" ", "_")
    # Engineering headers may legitimately describe expected use, voltage, etc.
    answer_prefixes = (
        "answer_",
        "gold_",
        "expected_answer",
        "expected_choice",
        "expected_config",
        "expected_issue",
        "expected_link",
        "expected_outcome",
        "expected_plan",
        "expected_rank",
        "expected_score",
        "expected_selection",
    )
    if label in _REFERENCE_FIELDS or label.startswith(answer_prefixes):
        raise ValueError(f"evaluation field in input: {name}")


def _check_reference_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            _check_label(str(key))
            if key == "header" and isinstance(child, str):
                _check_label(child)
            _check_reference_fields(child)
    elif isinstance(value, list):
        for child in value:
            _check_reference_fields(child)
    elif isinstance(value, str):
        parts = PurePosixPath(value.replace("\\", "/").casefold()).parts
        if len(parts) > 1 and {"evals", "gold"}.intersection(parts):
            raise ValueError("evaluation path in fixture content")


def _read_world(bundle_dir: Path):
    manifest_file = bundle_dir / "manifest.json"
    files = list(bundle_dir.iterdir())
    if {file.name for file in files} != {"manifest.json", "core.yaml"} or any(
        file.is_symlink() or not file.is_file() for file in files
    ):
        raise ValueError("fixture bundle must contain only the input manifest and its world file")
    manifest = _InputManifest.model_validate_json(manifest_file.read_bytes())
    source = (bundle_dir / manifest.world_file).read_bytes()
    if hashlib.sha256(source).hexdigest() != manifest.sha256:
        raise ValueError("fixture world digest differs from manifest")
    world = yaml.safe_load(source)
    _check_reference_fields(world)
    if not isinstance(world, dict) or world.get("knowledge_id") != manifest.knowledge_id:
        raise ValueError("fixture knowledge snapshot differs from manifest")
    orders = world.get("orders")
    if not isinstance(orders, dict) or sorted(orders) != sorted(manifest.order_ids):
        raise ValueError("fixture order inventory differs from manifest")
    return manifest, world


def _scope_order(world, order_id):
    if order_id not in world["orders"]:
        raise ValueError(f"unknown order: {order_id}")
    return {**world, "orders": {order_id: world["orders"][order_id]}}


def load_order_input(bundle_dir: Path, order_id: str) -> dict:
    """Load a verified catalog and exactly one order."""
    _, world = _read_world(bundle_dir)
    return _scope_order(world, order_id)


def iter_order_inputs(bundle_dir: Path):
    """Render every order from the same verified source bytes and inventory."""
    manifest, world = _read_world(bundle_dir)
    for order_id in manifest.order_ids:
        yield manifest.sha256, order_id, _scope_order(world, order_id)
