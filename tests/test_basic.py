import json
import unittest
from dataclasses import MISSING, dataclass, field as dataclass_field
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Callable, Union

from msup.base import (
    dict_from_str,
    effective_type,
    fields_or_init_kwargs,
    from_dict,
    from_dict_value,
    from_json,
    is_compat,
    to_dict,
    to_dict_value,
    to_json,
    to_kwargs,
)
from msup.cli import CliArg


@dataclass
class Nested:
    a: int
    b: int


@dataclass
class ConversionValues:
    nested: Annotated[Nested | None, CliArg()] = None
    raw: Annotated[dict | None, CliArg()] = None
    values: Annotated[list[int] | None, CliArg()] = None
    pair: Annotated[tuple[int, str], CliArg()] = (0, "")
    mapping: Annotated[dict[int, list[float]] | None, CliArg()] = None
    anything: Annotated[list[Any] | None, CliArg()] = None
    enabled: Annotated[bool, CliArg()] = False
    primitive: Annotated[Union[int, None], CliArg()] = 3


@dataclass
class Defaults:
    required: int
    label: str = "default label"
    values: list[int] = dataclass_field(default_factory=lambda: [1, 2])
    optional: int | None = 9


@dataclass
class CallableValue:
    callback: Annotated[Callable[[int], int], CliArg()]


class BasicClass:
    def __init__(self, name: Annotated[str, CliArg(help="ignored")], count: int | None = None):
        self.name = name
        self.count = count


class VarArgsClass:
    def __init__(self, name: str, *values: int, **options: str):
        self.name = name
        self.values = values
        self.options = options


@dataclass
class AnnotatedMetadataValues:
    value: Annotated[int, "first", CliArg(help="value"), ("second",)] = 1


def increment(value: int) -> int:
    return value + 1


def function_field_values(
    required: Annotated[int, "required value", CliArg(help="required")],
    callback: Callable[[int], int] = increment,
    defaulted: str = "default value",
    unannotated=None,
    *values: int,
    **options: str,
):
    return required, callback, defaulted, unannotated, values, options


def function_serialization_values(
    message: Annotated[str, "message metadata"],
    count: int,
    nested: Nested,
    values: list[int],
    callback: Callable[[int], int],
    omitted: str = "default value",
):
    return message, count, nested, values, callback, omitted


class MethodFieldValues:
    def method(self, required: int, defaulted: str = "default value"):
        return required, defaulted


class BasicTests(unittest.TestCase):
    def test_function_field_discovery_preserves_annotations_and_defaults(self):
        field_info = fields_or_init_kwargs(function_field_values)
        self.assertEqual([field.name for field in field_info], ["required", "callback", "defaulted", "unannotated"])
        self.assertEqual(field_info[0].annotation, int)
        self.assertEqual(field_info[0].annotations, ["required value", CliArg(help="required")])
        self.assertIs(field_info[0].default, MISSING)
        self.assertEqual(field_info[1].annotation, Callable[[int], int])
        self.assertIs(field_info[1].default, increment)
        self.assertEqual(field_info[2].default, "default value")
        self.assertIsNone(field_info[3].annotation)
        self.assertIsNone(field_info[3].default)

    def test_method_field_discovery_supports_bound_and_unbound_methods(self):
        expected = [("required", MISSING), ("defaulted", "default value")]
        for method in (MethodFieldValues.method, MethodFieldValues().method):
            with self.subTest(method=method):
                self.assertEqual(
                    [(field.name, field.default) for field in fields_or_init_kwargs(method)],
                    expected,
                )

    def test_shared_field_discovery_preserves_all_annotated_metadata(self):
        field_info = fields_or_init_kwargs(AnnotatedMetadataValues)[0]
        self.assertEqual(field_info.annotation, int)
        self.assertEqual(field_info.annotations, ["first", CliArg(help="value"), ("second",)])

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

    def test_callable_annotation_accepts_direct_callables_and_rejects_invalid_serialization(self):
        self.assertIs(from_dict(CallableValue, {"callback": increment}).callback, increment)
        with self.assertRaisesRegex(TypeError, "expected callable value"):
            to_dict(CallableValue(3))

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

    def test_regular_classes_ignore_variadic_constructor_parameters(self):
        value = from_dict(VarArgsClass, {"name": "ok", "values": [1], "options": {"color": "blue"}})
        self.assertEqual(value.name, "ok")
        self.assertEqual(value.values, ())
        self.assertEqual(value.options, {})
        self.assertEqual(to_dict(value), {"name": "ok"})

    def test_to_kwargs_accepts_regular_class_instances(self):
        self.assertEqual(to_kwargs(BasicClass, BasicClass("ok", 3)), {"name": "ok", "count": 3})

    def test_conversion_rejects_incompatible_values_and_fixed_tuple_lengths(self):
        @dataclass
        class NestedOrValues:
            value: Nested | list[int]

        with self.assertRaisesRegex(TypeError, "cannot be converted from <class 'int'>"):
            from_dict(NestedOrValues, {"value": 3})
        with self.assertRaisesRegex(TypeError, r"list\[int\].*cannot be converted from <class 'int'>"):
            from_dict(ConversionValues, {"values": 3})
        with self.assertRaisesRegex(TypeError, r"tuple\[int, str\].*cannot be converted from None"):
            from_dict(ConversionValues, {"pair": None})
        with self.assertRaisesRegex(TypeError, "expected 2 tuple values, got 1"):
            from_dict(ConversionValues, {"pair": [3]})

    def test_unparameterized_tuples_preserve_values(self):
        @dataclass
        class TupleValues:
            values: tuple

        value = from_dict(TupleValues, {"values": [1, "two"]})
        self.assertEqual(value, TupleValues((1, "two")))
        self.assertEqual(to_dict(value), {"values": (1, "two")})

    def test_function_argument_mappings_serialize_typed_values(self):
        expected = {
            "message": "hello",
            "count": 2,
            "nested": {"a": 3, "b": 4},
            "values": [5, 6],
            "callback": f"{increment.__module__}.increment",
        }

        def serialize_locals(message, count, nested, values, callback):
            helper = "not a function argument"
            as_dict = to_dict(locals(), type_class=function_serialization_values)
            as_json = to_json(locals(), indent=None, type_class=function_serialization_values)
            buffer = StringIO()
            to_json(locals(), buffer, None, type_class=function_serialization_values)
            with TemporaryDirectory() as directory:
                path = Path(directory) / "function-values.json"
                to_json(locals(), str(path), None, type_class=function_serialization_values)
                with path.open() as in_f:
                    from_path = json.load(in_f)
            return as_dict, as_json, buffer.getvalue(), from_path, helper

        as_dict, as_json, buffer_json, path_json, helper = serialize_locals(
            "hello", 2, Nested(a=3, b=4), [5, 6], increment
        )
        self.assertEqual(as_dict, expected)
        self.assertEqual(json.loads(as_json), expected)
        self.assertEqual(json.loads(buffer_json), expected)
        self.assertEqual(path_json, expected)
        self.assertEqual(helper, "not a function argument")

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
