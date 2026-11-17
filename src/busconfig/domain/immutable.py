"""Immutable mappings with validated Pydantic JSON-object boundaries."""

from collections.abc import Iterator, Mapping
from typing import Generic, TypeVar, get_args

from pydantic_core import core_schema

K = TypeVar("K")
V = TypeVar("V")


class FrozenMap(Mapping[K, V], Generic[K, V]):
    __slots__ = ("_items",)
    _items: tuple[tuple[K, V], ...]

    def __init__(self, values: Mapping[K, V]):
        object.__setattr__(self, "_items", tuple(values.items()))

    def __setattr__(self, name, value):
        raise TypeError("FrozenMap is immutable")

    def __getitem__(self, key: K) -> V:
        for item_key, value in self._items:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[K]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        key, value = get_args(source)
        dictionary = handler.generate_schema(dict[key, value])
        validated = core_schema.no_info_after_validator_function(
            cls,
            dictionary,
            serialization=core_schema.plain_serializer_function_ser_schema(
                dict,
                return_schema=dictionary,
            ),
        )
        # A before-validator on JSON would turn nested arrays into Python lists
        # before strict tuple fields can interpret them as JSON arrays.
        return core_schema.json_or_python_schema(
            json_schema=validated,
            python_schema=core_schema.no_info_before_validator_function(
                lambda value: dict(value) if isinstance(value, FrozenMap) else value,
                validated,
            ),
        )


def immutable_sequences(value):
    """Copy JSON arrays into tuples; mapping children are validated recursively."""
    if isinstance(value, list):
        return tuple(value)
    return value
