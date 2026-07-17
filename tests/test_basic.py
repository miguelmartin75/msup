from __future__ import annotations

import unittest
from dataclasses import dataclass, field as dataclass_field
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Union

from msup.base import (
    dict_from_str, effective_type, from_dict, from_dict_value, from_json,
    is_compat, to_dict, to_dict_value, to_json, to_kwargs,
)


@dataclass
class Nested:
    a: int
    b: int


@dataclass
class ConversionValues:
    nested: Nested | None = None
    raw: dict | None = None
    values: list[int] | None = None
    pair: tuple[int, str] = (0, "")
    mapping: dict[int, list[float]] | None = None
    anything: list[Any] | None = None
    enabled: bool = False
    primitive: Union[int, None] = 3


@dataclass
class Defaults:
    required: int
    label: str = "default label"
    values: list[int] = dataclass_field(default_factory=lambda: [1, 2])
    optional: int | None = 9


@dataclass
class CallableValue:
    callback: Callable[[int], int]


class BasicClass:
    def __init__(self, name: str, count: int | None = None):
        self.name = name
        self.count = count


def increment(value: int) -> int:
    return value + 1


class BasicTests(unittest.TestCase):
    def test_representative_conversion_types_round_trip(self):
        value = from_dict(
            ConversionValues,
            {
                "nested": {"a": "3", "b": 5},
                "raw": {"key": 1},
                "values": ["1", "2"],
                "pair": ["3", 4],
                "mapping": {"5": ["1.5", 2]},
                "anything": ["value", 3],
                "enabled": "yes",
            },
        )
        expected = ConversionValues(
            nested=Nested(a=3, b=5),
            raw={"key": 1},
            values=[1, 2],
            pair=(3, "4"),
            mapping={5: [1.5, 2.0]},
            anything=["value", 3],
            enabled=True,
        )
        self.assertEqual(value, expected)
        self.assertEqual(from_dict(ConversionValues, to_dict(value)), value)
        self.assertIsNone(from_dict(ConversionValues, {"values": None}).values)

    def test_omitted_values_keep_dataclass_defaults(self):
        self.assertEqual(from_dict(Defaults, {"required": 3}), Defaults(required=3))

    def test_callable_values_round_trip_through_importable_reference(self):
        serialized = to_dict(CallableValue(increment))
        self.assertEqual(serialized, {"callback": f"{increment.__module__}.increment"})
        self.assertIs(from_dict(CallableValue, serialized).callback, increment)

    def test_callable_annotation_rejects_non_callable_values(self):
        with self.assertRaisesRegex(TypeError, "expected a callable"):
            from_dict(CallableValue, {"callback": 3})
        with self.assertRaisesRegex(TypeError, "does not resolve to a callable"):
            from_dict(CallableValue, {"callback": "msup.base.__name__"})

    def test_ambiguous_unions_and_invalid_dict_strings_are_rejected(self):
        @dataclass
        class Ambiguous:
            value: int | float

        @dataclass
        class NestedOrInt:
            value: Nested | int

        for value in (NestedOrInt(Nested(1, 2)), NestedOrInt(3)):
            with self.subTest(value=value):
                self.assertEqual(from_dict(NestedOrInt, to_dict(value)), value)
        with self.assertRaisesRegex(TypeError, "ambiguous conversion"):
            from_dict(Ambiguous, {"value": "1"})
        with self.assertRaisesRegex(AssertionError, "unexpected str"):
            dict_from_str("not-json")

    def test_string_boolean_values_are_converted_and_invalid_values_are_rejected(self):
        for value, expected in [("yes", True), ("off", False)]:
            with self.subTest(value=value):
                self.assertEqual(from_dict(ConversionValues, {"enabled": value}).enabled, expected)
        with self.assertRaisesRegex(TypeError, "invalid boolean value 'maybe'"):
            from_dict(ConversionValues, {"enabled": "maybe"})

    def test_public_conversion_helpers(self):
        self.assertEqual(effective_type(list[int] | None, "values"), list[int])
        self.assertEqual(is_compat(dict[int, float], str), (True, dict))
        self.assertEqual(from_dict_value(["1"], list[int], list, "values"), [1])
        self.assertEqual(to_dict_value([1], list[int]), [1])
        self.assertEqual(is_compat(int, dict), (False, None))
        with self.assertRaisesRegex(TypeError, "non-optional union"):
            effective_type(int | str, "value")

    def test_regular_classes_keep_main_serialization_support(self):
        value = from_dict(BasicClass, {"name": "ok", "count": None})
        self.assertEqual(value.name, "ok")
        self.assertIsNone(value.count)
        self.assertEqual(to_dict(BasicClass("ok", 3)), {"name": "ok", "count": 3})
        self.assertEqual(to_kwargs(BasicClass, {"name": "ok", "count": 3, "ignored": 1}), {"name": "ok", "count": 3})

    def test_json_helpers_accept_strings_file_objects_and_paths(self):
        value = ConversionValues(nested=Nested(a=2, b=4), mapping={1: [1.5, 2.5]})
        serialized = to_json(value, indent=None)
        self.assertEqual(from_json(ConversionValues, s=serialized), value)

        buffer = StringIO()
        to_json(value, file_like=buffer, indent=None)
        buffer.seek(0)
        self.assertEqual(from_json(ConversionValues, file_like=buffer), value)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            to_json(value, file_like=str(path), indent=None)
            self.assertEqual(from_json(ConversionValues, path=str(path)), value)
            self.assertEqual(dict_from_str(str(path)), dict_from_str(serialized))
        self.assertEqual(dict_from_str('{"key": 1}'), {"key": 1})


if __name__ == "__main__":
    unittest.main()
