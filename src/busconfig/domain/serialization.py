"""Schema-v1 canonical UTF-8 JSON and SHA-256; semantic array order is retained."""

import hashlib
import json
from collections.abc import Mapping
from enum import Enum

from pydantic import BaseModel


def reject_duplicate_json_keys(encoded) -> None:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    json.loads(encoded, object_pairs_hook=unique)


def canonical_json(value) -> bytes:
    def plain(item):
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("Canonical JSON requires string object keys")
            return {key: plain(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [plain(child) for child in item]
        if isinstance(item, Enum):
            return item.value
        return item

    return json.dumps(
        plain(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()
