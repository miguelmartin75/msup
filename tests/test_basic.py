import json
import unittest
from dataclasses import MISSING, dataclass, field as dataclass_field
from enum import Enum, IntEnum
from functools import partial
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Callable, Union, cast

from msup.base import (
    Kwargs,
    Metadata,
    dict_from_str,
    dump_callable,
    effective_type,
    fields_or_init_kwargs,
    from_dict,
    from_dict_value,
    from_json,
    from_kwargs,
    is_compat,
    kwargs_from_dict,
    load_callable,
    metadata_from_annotations,
    selected_target_fields,
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


class State(Enum):
    READY = "ready"
    STOPPED = "stopped"


class Priority(IntEnum):
    LOW = 1
    HIGH = 2


class InvalidState(Enum):
    PAIR = ("not", "a scalar")


@dataclass
class EnumChild:
    state: State


@dataclass
class EnumValues:
    state: State
    priority: Priority
    optional: State | None
    states: list[State]
    child: EnumChild


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


def function_self_cls_values(self: int, cls: str) -> None:
    pass


def function_serialization_values(
    message: Annotated[str, "message metadata"],
    count: int,
    nested: Nested,
    values: list[int],
    callback: Callable[[int], int],
    omitted: str = "default value",
):
    return message, count, nested, values, callback, omitted


class QualifiedCallable:
    @staticmethod
    def nested(value: int) -> int:
        return value + 1


def relation_target(value: int, *, label: str = "default") -> None:
    pass


relation_target_calls = 0
relation_class_calls = 0
relation_factory_calls = {"target": 0, "kwargs": 0}
declared_kwargs_copy_calls = 0


def counted_relation_target(value: int, state: State = State.READY, values: list[int] | None = None) -> None:
    global relation_target_calls
    relation_target_calls += 1


def default_relation_target(value: int = 2, *, label: str = "default") -> None:
    pass


class CountedRelationClass:
    def __init__(self, value: int, nested: Nested, states: list[State]) -> None:
        global relation_class_calls
        relation_class_calls += 1


def relation_target_factory() -> Callable[..., Any]:
    relation_factory_calls["target"] += 1
    return default_relation_target


def relation_kwargs_factory() -> dict[str, Any]:
    relation_factory_calls["kwargs"] += 1
    return {"label": "factory"}


def identity_mismatch(value: int) -> int:
    return value


@dataclass
class RelationValues:
    target: Callable[..., Any]
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")]


def direct_relation_values(
    target: Callable[..., Any],
    kwargs: Annotated[dict[str, Any], Metadata(kwargs_for="target")],
) -> None:
    pass


@dataclass
class NestedRelationValues:
    target: Callable[..., Any] = dataclass_field(default_factory=relation_target_factory)
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = dataclass_field(default_factory=relation_kwargs_factory)


@dataclass
class NestedRelationOwner:
    nested: NestedRelationValues


@dataclass
class StrictNestedRelationValues:
    target: Callable[..., Any] = relation_target
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = dataclass_field(default_factory=dict)


@dataclass
class StrictNestedRelationOwner:
    nested: StrictNestedRelationValues


@dataclass
class SelectedRelationConfig:
    target: Callable[..., Any] = relation_target
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = dataclass_field(default_factory=dict)


def selected_relation_config_target(config: SelectedRelationConfig | None = None) -> None:
    pass


@dataclass
class StructuredTargetRelationOwner:
    target: Callable[..., Any] = selected_relation_config_target
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = dataclass_field(default_factory=dict)


def selected_union_relation_config_target(config: SelectedRelationConfig | int) -> None:
    pass


@dataclass
class UnionStructuredTargetRelationOwner:
    target: Callable[..., Any] = selected_union_relation_config_target
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = dataclass_field(default_factory=dict)


@dataclass
class MultipleRelationValues:
    first_target: Callable[..., Any] = relation_target
    first_kwargs: Annotated[Kwargs, Metadata(kwargs_for="first_target")] = dataclass_field(
        default_factory=relation_kwargs_factory
    )
    second_target: Callable[..., Any] = relation_target
    second_kwargs: Annotated[Kwargs, Metadata(kwargs_for="second_target")] = dataclass_field(
        default_factory=relation_kwargs_factory
    )


@dataclass
class FactoryRelationValues:
    target: Callable[..., Any] = dataclass_field(default_factory=relation_target_factory)
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = dataclass_field(default_factory=relation_kwargs_factory)


class HashableKwargs(dict[str, Any]):
    __hash__ = object.__hash__

    def __deepcopy__(self, memo: dict[int, Any]) -> "HashableKwargs":
        global declared_kwargs_copy_calls
        declared_kwargs_copy_calls += 1
        result = HashableKwargs(self)
        memo[id(self)] = result
        return result


declared_kwargs = HashableKwargs({"label": "declared"})


@dataclass
class DeclaredDefaultRelationValues:
    target: Callable[..., Any] = relation_target
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")] = declared_kwargs


class MethodFieldValues:
    def method(self: Any, required: int, defaulted: str = "default value"):
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

    def test_method_field_discovery_omits_reserved_names(self):
        expected = [("required", MISSING), ("defaulted", "default value")]
        for method in (MethodFieldValues.method, MethodFieldValues().method):
            with self.subTest(method=method):
                self.assertEqual(
                    [(field.name, field.default) for field in fields_or_init_kwargs(method)],
                    expected,
                )
        self.assertEqual(
            [(field.name, field.default) for field in fields_or_init_kwargs(function_self_cls_values)],
            [],
        )

    def test_selected_target_fields_preserve_explicit_reserved_names(self):
        self.assertEqual(
            [field.name for field in selected_target_fields(function_self_cls_values)],
            ["self", "cls"],
        )
        self.assertEqual(
            [field.name for field in selected_target_fields(MethodFieldValues.method)],
            ["self", "required", "defaulted"],
        )
        self.assertEqual(
            [field.name for field in selected_target_fields(MethodFieldValues().method)],
            ["required", "defaulted"],
        )

    def test_shared_field_discovery_preserves_all_annotated_metadata(self):
        field_info = fields_or_init_kwargs(AnnotatedMetadataValues)[0]
        self.assertEqual(field_info.annotation, int)
        self.assertEqual(field_info.annotations, ["first", CliArg(help="value"), ("second",)])

    def test_kwargs_relations_link_preceding_callable_fields(self):
        dataclass_fields = fields_or_init_kwargs(RelationValues)
        function_fields = fields_or_init_kwargs(direct_relation_values)

        self.assertIs(dataclass_fields[1].kwargs_relation, dataclass_fields[0])
        self.assertIs(function_fields[1].kwargs_relation, function_fields[0])
        self.assertIs(dataclass_fields[1].annotation, Kwargs)
        self.assertEqual(dataclass_fields[1].annotation.__value__, dict[str, Any])
        value = from_dict(RelationValues, {"target": relation_target, "kwargs": {"value": "3"}})
        self.assertIs(value.target, relation_target)
        self.assertEqual(value.kwargs, {"value": 3})

    def test_kwargs_relations_convert_serialize_and_never_invoke_targets(self):
        global declared_kwargs_copy_calls, relation_target_calls, relation_class_calls
        relation_target_calls = relation_class_calls = 0
        relation_factory_calls.update(target=0, kwargs=0)
        value = from_dict(
            RelationValues,
            {"target": counted_relation_target, "kwargs": {"value": "3", "state": "stopped", "values": ["1", 2]}},
        )
        self.assertEqual(value.kwargs, {"value": 3, "state": State.STOPPED, "values": [1, 2]})
        self.assertEqual(
            to_dict(value),
            {
                "target": f"{__name__}.counted_relation_target",
                "kwargs": {"value": 3, "state": "stopped", "values": [1, 2]},
            },
        )
        self.assertEqual(from_json(RelationValues, s=to_json(value, indent=None)), value)
        self.assertEqual(
            from_kwargs(direct_relation_values, {"target": relation_target, "kwargs": {"value": "4"}}),
            {"target": relation_target, "kwargs": {"value": 4}},
        )
        self.assertEqual(to_dict({}, type_class=direct_relation_values), {})
        self.assertEqual(
            to_dict({"target": relation_target}, type_class=direct_relation_values),
            {"target": f"{__name__}.relation_target"},
        )
        self.assertEqual(
            to_dict({"target": relation_target, "kwargs": {"value": "4"}}, type_class=direct_relation_values),
            {"target": f"{__name__}.relation_target", "kwargs": {"value": 4}},
        )
        self.assertEqual(
            json.loads(
                cast(
                    str,
                    to_json(
                        {"target": relation_target, "kwargs": {"value": "4"}},
                        indent=None,
                        type_class=direct_relation_values,
                    ),
                )
            ),
            {"target": f"{__name__}.relation_target", "kwargs": {"value": 4}},
        )
        class_value = from_dict(
            RelationValues,
            {
                "target": CountedRelationClass,
                "kwargs": {"value": "5", "nested": {"a": "1", "b": 2}, "states": ["ready"]},
            },
        )
        self.assertEqual(class_value.kwargs, {"value": 5, "nested": Nested(1, 2), "states": [State.READY]})
        self.assertEqual(from_json(RelationValues, s=to_json(class_value, indent=None)), class_value)
        self.assertEqual(relation_target_calls, 0)
        self.assertEqual(relation_class_calls, 0)
        relation_factory_calls.update(target=0, kwargs=0)
        nested_explicit = from_dict(
            NestedRelationOwner,
            {"nested": {"target": relation_target, "kwargs": {"value": "6"}}},
        )
        self.assertEqual(nested_explicit.nested.kwargs, {"value": 6, "label": "factory"})
        self.assertEqual(relation_factory_calls, {"target": 0, "kwargs": 1})
        relation_factory_calls.update(target=0, kwargs=0)
        nested = from_dict(NestedRelationOwner, {"nested": {"kwargs": {"value": "6"}}})
        self.assertEqual(nested.nested.kwargs, {"value": 6, "label": "factory"})
        multiple = from_dict(
            MultipleRelationValues,
            {"first_kwargs": {"value": "7"}, "second_kwargs": {"value": "8", "label": "second"}},
        )
        self.assertEqual(multiple.first_kwargs, {"value": 7, "label": "factory"})
        self.assertEqual(multiple.second_kwargs, {"value": 8, "label": "second"})
        self.assertEqual(relation_factory_calls, {"target": 1, "kwargs": 2})
        fully_supplied = from_dict(
            FactoryRelationValues,
            {"target": relation_target, "kwargs": {"value": "9", "label": "supplied"}},
        )
        self.assertEqual(fully_supplied.kwargs, {"value": 9, "label": "supplied"})
        self.assertEqual(relation_factory_calls, {"target": 1, "kwargs": 2})
        explicit = from_dict(FactoryRelationValues, {"target": relation_target, "kwargs": {"value": "9"}})
        self.assertEqual(explicit.kwargs, {"value": 9, "label": "factory"})
        self.assertEqual(relation_factory_calls, {"target": 1, "kwargs": 3})
        defaulted = from_dict(FactoryRelationValues, {})
        self.assertEqual(defaulted.kwargs, {"label": "factory"})
        self.assertEqual(relation_factory_calls, {"target": 2, "kwargs": 4})
        declared_kwargs_copy_calls = 0
        copied = from_dict(DeclaredDefaultRelationValues, {"kwargs": {"value": "10"}})
        self.assertEqual(copied.kwargs, {"value": 10, "label": "declared"})
        self.assertEqual(declared_kwargs_copy_calls, 1)
        copied.kwargs["label"] = "updated"
        self.assertEqual(declared_kwargs, {"label": "declared"})
        declared_kwargs_copy_calls = 0
        fully_supplied_declared = from_dict(
            DeclaredDefaultRelationValues,
            {"kwargs": {"value": "10", "label": "supplied"}},
        )
        self.assertEqual(fully_supplied_declared.kwargs, {"value": 10, "label": "supplied"})
        self.assertEqual(declared_kwargs_copy_calls, 0)
        relation_factory_calls.update(target=0, kwargs=0)
        self.assertEqual(
            to_dict(FactoryRelationValues(target=relation_target, kwargs={"value": 11})),
            {"target": f"{__name__}.relation_target", "kwargs": {"value": 11}},
        )
        self.assertEqual(relation_factory_calls, {"target": 0, "kwargs": 0})
        with self.assertRaisesRegex(TypeError, "RelationValues.kwargs.unknown: unknown"):
            kwargs_from_dict(relation_target, {"unknown": 1}, field_name="RelationValues.kwargs")
        with self.assertRaisesRegex(TypeError, "RelationValues.kwargs.value: missing"):
            kwargs_from_dict(relation_target, {}, field_name="RelationValues.kwargs")
        with self.assertRaisesRegex(TypeError, "RelationValues.kwargs: expected a mapping"):
            kwargs_from_dict(relation_target, cast(Any, []), field_name="RelationValues.kwargs")
        with self.assertRaisesRegex(TypeError, "direct_relation_values.target: missing selector"):
            from_kwargs(direct_relation_values, {"kwargs": {"value": 1}})
        with self.assertRaisesRegex(TypeError, "direct_relation_values.kwargs: missing selector"):
            to_dict({"kwargs": {"value": 1}}, type_class=direct_relation_values)

    def test_nested_kwargs_errors_keep_the_containing_path(self):
        with self.assertRaisesRegex(TypeError, "StrictNestedRelationOwner.nested.kwargs.value: missing"):
            from_dict(StrictNestedRelationOwner, {"nested": {}})
        with self.assertRaisesRegex(TypeError, "StrictNestedRelationOwner.nested.kwargs.unknown: unknown"):
            from_dict(StrictNestedRelationOwner, {"nested": {"kwargs": {"unknown": 1}}})

        def unsupported(values: set[int]) -> None:
            pass

        with self.assertRaisesRegex(TypeError, "StrictNestedRelationOwner.nested.kwargs: values: unsupported"):
            from_dict(StrictNestedRelationOwner, {"nested": {"target": unsupported, "kwargs": {}}})
        with self.assertRaisesRegex(TypeError, "StrictNestedRelationOwner.nested.kwargs.unknown: unknown"):
            to_dict(StrictNestedRelationOwner(StrictNestedRelationValues(kwargs={"unknown": 1})))
        with self.assertRaisesRegex(TypeError, "StructuredTargetRelationOwner.kwargs.config.kwargs.unknown: unknown"):
            to_dict(StructuredTargetRelationOwner(kwargs={"config": SelectedRelationConfig(kwargs={"unknown": 1})}))
        with self.assertRaisesRegex(
            TypeError, "UnionStructuredTargetRelationOwner.kwargs.config.kwargs.unknown: unknown"
        ):
            to_dict(
                UnionStructuredTargetRelationOwner(kwargs={"config": SelectedRelationConfig(kwargs={"unknown": 1})})
            )
        self.assertEqual(
            to_dict(StructuredTargetRelationOwner(kwargs={"config": None})),
            {"target": f"{__name__}.selected_relation_config_target", "kwargs": {"config": None}},
        )

    def test_kwargs_relation_schemas_reject_invalid_links(self):
        with self.assertRaisesRegex(TypeError, "^an annotation can contain at most one CliArg or Metadata$"):
            metadata_from_annotations([Metadata(), Metadata()])

        @dataclass
        class DuplicateMetadata:
            value: Annotated[int, Metadata(), Metadata()] = 1

        @dataclass
        class WrongDependentType:
            target: Callable[..., Any]
            kwargs: Annotated[dict[str, int], Metadata(kwargs_for="target")]

        @dataclass
        class MissingSelector:
            kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")]

        @dataclass
        class SelfSelector:
            kwargs: Annotated[Kwargs, Metadata(kwargs_for="kwargs")]

        @dataclass
        class ForwardSelector:
            kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")]
            target: Callable[..., Any]

        @dataclass
        class NonCallableSelector:
            target: int
            kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")]

        @dataclass
        class ReusedSelector:
            target: Callable[..., Any]
            first: Annotated[Kwargs, Metadata(kwargs_for="target")]
            second: Annotated[dict[str, Any], Metadata(kwargs_for="target")]

        @dataclass
        class RelationSelector:
            target: Callable[..., Any]
            kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")]
            other: Annotated[dict[str, Any], Metadata(kwargs_for="kwargs")]

        class RegularRelationOwner:
            def __init__(
                self,
                target: Callable[..., Any],
                kwargs: Annotated[dict[str, Any], Metadata(kwargs_for="target")],
            ):
                self.target = target
                self.kwargs = kwargs

        cases = [
            (DuplicateMetadata, "value", "at most one CliArg"),
            (WrongDependentType, "kwargs", "dict\\[str, Any\\].*Kwargs"),
            (MissingSelector, "kwargs", "does not exist"),
            (SelfSelector, "kwargs", "different selector"),
            (ForwardSelector, "kwargs", "must precede"),
            (NonCallableSelector, "kwargs", "must be annotated as Callable"),
            (ReusedSelector, "second", "already has a kwargs field"),
            (RelationSelector, "other", "cannot be a kwargs field"),
            (RegularRelationOwner, "kwargs", "only supported by dataclasses and functions"),
        ]
        for owner, field_name, message in cases:
            with self.subTest(owner=owner):
                with self.assertRaisesRegex(TypeError, f"{owner.__name__}\\.{field_name}.*{message}"):
                    fields_or_init_kwargs(owner)

    def test_canonical_callable_references_support_qualified_names(self):
        reference = f"{__name__}.QualifiedCallable.nested"
        self.assertIs(load_callable(reference), QualifiedCallable.nested)
        self.assertEqual(dump_callable(QualifiedCallable.nested), reference)
        self.assertEqual(to_dict(CallableValue(QualifiedCallable.nested)), {"callback": reference})
        with self.assertRaises(ModuleNotFoundError):
            load_callable("malformed")
        with self.assertRaises(ModuleNotFoundError):
            load_callable("missing.module.target")
        with self.assertRaises(AttributeError):
            load_callable(f"{__name__}.QualifiedCallable.missing")

        def local(value: int) -> int:
            return value

        for value in (local, lambda value: value, partial(increment, 1)):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "importable"):
                    dump_callable(value)

        original_qualname = identity_mismatch.__qualname__
        try:
            identity_mismatch.__qualname__ = QualifiedCallable.nested.__qualname__
            with self.assertRaisesRegex(TypeError, "same object"):
                dump_callable(identity_mismatch)
        finally:
            identity_mismatch.__qualname__ = original_qualname

    def test_selected_target_signatures_are_strict(self):
        class ClassTarget:
            def __init__(self, value: int, *, enabled: bool = False):
                self.value = value
                self.enabled = enabled

        def keyword_only(value: int, *, label: str) -> None:
            pass

        def unannotated(value) -> None:
            pass

        def positional_only(value: int, /) -> None:
            pass

        def variadic_positional(*values: int) -> None:
            pass

        def variadic_keyword(**values: int) -> None:
            pass

        def unsupported(values: set[int]) -> None:
            pass

        class CallableInstance:
            def __call__(self, value: int) -> None:
                pass

        self.assertEqual([field.name for field in selected_target_fields(ClassTarget)], ["value", "enabled"])
        self.assertEqual([field.name for field in selected_target_fields(keyword_only)], ["value", "label"])
        cases = [
            (unannotated, "must have an annotation"),
            (positional_only, "cannot be positional-only"),
            (variadic_positional, "cannot use \\*args"),
            (variadic_keyword, "cannot use \\*\\*kwargs"),
            (unsupported, "unsupported selected target annotation"),
            (CallableInstance(), "selected targets must be classes, functions, or methods"),
            (3, "selected targets must be classes, functions, or methods"),
        ]
        for target, message in cases:
            with self.subTest(target=target):
                with self.assertRaisesRegex(TypeError, message):
                    selected_target_fields(cast(Any, target))

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
            to_dict(CallableValue(cast(Callable[[int], int], 3)))

    def test_enum_values_round_trip_through_base_and_json_conversion(self):
        expected = EnumValues(
            state=State.READY,
            priority=Priority.HIGH,
            optional=State.READY,
            states=[State.STOPPED, State.READY],
            child=EnumChild(state=State.STOPPED),
        )
        serialized = {
            "state": "ready",
            "priority": 2,
            "optional": "ready",
            "states": ["stopped", "ready"],
            "child": {"state": "stopped"},
        }
        self.assertEqual(from_dict(EnumValues, serialized), expected)
        self.assertEqual(to_dict(expected), serialized)
        self.assertEqual(from_json(EnumValues, s=to_json(expected, indent=None)), expected)
        with self.assertRaisesRegex(TypeError, "state.*invalid State value"):
            from_dict(EnumValues, {**serialized, "state": "unknown"})
        with self.assertRaisesRegex(TypeError, "invalid State value"):
            from_dict(EnumValues, {**serialized, "child": {"state": "unknown"}})
        with self.assertRaisesRegex(TypeError, "invalid.*must be str, int, float, or bool"):
            from_dict_value("not", InvalidState, str, "invalid")
        with self.assertRaisesRegex(TypeError, "value.*must be str, int, float, or bool"):
            is_compat(InvalidState, str)

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
        @dataclass(frozen=True)
        class Child:
            value: int

        @dataclass
        class Owner:
            payload: Any = Child(1)

        @dataclass
        class OptionalOwner:
            payload: Child | None = None

        child = Child(2)
        self.assertIs(to_dict(Owner(child))["payload"], child)
        self.assertEqual(to_dict(OptionalOwner()), {"payload": None})
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
        assert serialized is not None
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
