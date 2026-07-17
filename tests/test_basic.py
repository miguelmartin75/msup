from __future__ import annotations

import unittest
from dataclasses import dataclass, field as dataclass_field
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, Union

from msup.base import dict_from_str, from_dict, from_json, to_dict, to_json, to_kwargs


@dataclass
class Foo:
    a: int
    b: int


@dataclass
class Bar:
    x: list[float]
    yy: str = "lol"


@dataclass
class Foobar:
    dd: dict
    primitive: Union[int, None] = 3
    foo: Foo | None = None
    z: Dict[int, int] | None = None
    bar: Bar | None = None


@dataclass
class Converted:
    values: list[int] | None = None
    pair: tuple[int, str] = (0, "")
    mapping: dict[int, list[float]] | None = None
    anything: list[Any] | None = None


@dataclass
class Defaults:
    required: int
    label: str = "default label"
    values: list[int] = dataclass_field(default_factory=lambda: [1, 2])
    optional: int | None = 9


@dataclass
class CallableValue:
    callback: Callable[[int], int]


@dataclass
class BooleanValue:
    value: bool


class BasicClass:
    def __init__(self, name: str, count: int | None = None):
        self.name = name
        self.count = count


def increment(value: int) -> int:
    return value + 1


class BasicTests(unittest.TestCase):
    def test_round_trip_dataclasses(self):
        value = Foobar(dd={}, foo=Foo(a=3, b=5), bar=Bar(x=[1.5]), z=None)
        self.assertEqual(from_dict(Foobar, to_dict(value)), value)
        self.assertEqual(from_dict(Foo, {"a": 1, "b": 5}), Foo(a=1, b=5))

    def test_declared_collection_elements_are_converted(self):
        value = from_dict(
            Converted,
            {
                "values": ["1", "2"],
                "pair": ["3", 4],
                "mapping": {"5": ["1.5", 2]},
                "anything": ["value", 3],
            },
        )
        self.assertEqual(value.values, [1, 2])
        self.assertEqual(value.pair, (3, "4"))
        self.assertEqual(value.mapping, {5: [1.5, 2.0]})
        self.assertEqual(value.anything, ["value", 3])
        self.assertEqual(from_dict(Converted, to_dict(value)), value)

    def test_optional_none_is_preserved_regardless_of_union_order(self):
        self.assertIsNone(from_dict(Converted, {"values": None}).values)

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

    def test_ambiguous_union_is_rejected(self):
        @dataclass
        class Ambiguous:
            value: int | float

        with self.assertRaisesRegex(TypeError, "ambiguous conversion"):
            from_dict(Ambiguous, {"value": "1"})

    def test_string_boolean_values_are_converted(self):
        self.assertTrue(from_dict(BooleanValue, {"value": "yes"}).value)
        self.assertFalse(from_dict(BooleanValue, {"value": "off"}).value)

    def test_invalid_string_boolean_value_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "invalid boolean value 'maybe'"):
            from_dict(BooleanValue, {"value": "maybe"})

    def test_regular_classes_keep_main_serialization_support(self):
        value = from_dict(BasicClass, {"name": "ok", "count": None})
        self.assertEqual(value.name, "ok")
        self.assertIsNone(value.count)
        self.assertEqual(to_dict(BasicClass("ok", 3)), {"name": "ok", "count": 3})
        self.assertEqual(to_kwargs(BasicClass, {"name": "ok", "count": 3, "ignored": 1}), {"name": "ok", "count": 3})

    def test_json_helpers_accept_strings_file_objects_and_paths(self):
        value = Foobar(dd={"key": 1}, foo=Foo(a=2, b=4), bar=Bar(x=[1.5, 2.5]))
        serialized = to_json(value, indent=None)
        self.assertEqual(from_json(Foobar, s=serialized), value)

        buffer = StringIO()
        to_json(value, file_like=buffer, indent=None)
        buffer.seek(0)
        self.assertEqual(from_json(Foobar, file_like=buffer), value)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            to_json(value, file_like=str(path), indent=None)
            self.assertEqual(from_json(Foobar, path=str(path)), value)
            self.assertEqual(dict_from_str(str(path)), to_dict(value))
        self.assertEqual(dict_from_str('{"key": 1}'), {"key": 1})


if __name__ == "__main__":
    unittest.main()
