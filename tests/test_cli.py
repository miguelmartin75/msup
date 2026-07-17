import os
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
from typing import Any, Callable, Optional

from msup.cli import cli, cliarg


received = []


def callback(value: int) -> int:
    return value + 1


@dataclass
class OptionalListArgs:
    values: list[int] | None = None


def optional_list_command(args: OptionalListArgs):
    received.append(args)


@dataclass
class ReversedOptionalListArgs:
    values: None | list[int] = None


def reversed_optional_list_command(args: ReversedOptionalListArgs):
    received.append(args)


@dataclass
class TypingOptionalListArgs:
    values: Optional[list[int]] = None


def typing_optional_list_command(args: TypingOptionalListArgs):
    received.append(args)


@dataclass
class OptionalBoolArgs:
    enabled: bool | None = None


def optional_bool_command(args: OptionalBoolArgs):
    received.append(args)


@dataclass
class OptionalDictArgs:
    values: dict[str, int] | None = None


def optional_dict_command(args: OptionalDictArgs):
    received.append(args)


@dataclass
class ChildArgs:
    count: int = 1


@dataclass
class OptionalDataclassArgs:
    child: ChildArgs | None = None


def optional_dataclass_command(args: OptionalDataclassArgs):
    received.append(args)


@dataclass
class OptionalCallableArgs:
    transform: Callable[[int], int] | None = None


def optional_callable_command(args: OptionalCallableArgs):
    received.append(args)


@dataclass
class PrimitiveArgs:
    count: int = 1
    ratio: float = 1.5
    name: str = "default"
    enabled: bool = False


def primitive_command(args: PrimitiveArgs):
    received.append(args)


@dataclass
class CollectionArgs:
    numbers: list[int] = field(default_factory=list)
    labels: list = field(default_factory=list)
    coordinates: tuple[int, ...] = ()


def collection_command(args: CollectionArgs):
    received.append(args)


@dataclass
class StructuredArgs:
    values: dict[str, int] = field(default_factory=dict)
    child: ChildArgs = field(default_factory=ChildArgs)
    transform: Callable[[int], int] = callback


def structured_command(args: StructuredArgs):
    received.append(args)


@dataclass
class AnyArgs:
    value: Any = None


def any_command(args: AnyArgs):
    received.append(args)


@dataclass
class RemainderArgs:
    extra: list[str] = cliarg(pos=True, opt=False, default_factory=list)


def remainder_command(args: RemainderArgs):
    received.append(args)


@dataclass
class SourceArgs:
    selected: int = cliarg(env="MSUP_TEST_SELECTED", default=1)
    from_config: int = 2
    default_only: str = "default"


def source_command(args: SourceArgs):
    received.append(args)


@dataclass
class EnvironmentBoolArgs:
    enabled: bool = cliarg(env="MSUP_TEST_ENABLED", default=False)


def environment_bool_command(args: EnvironmentBoolArgs):
    received.append(args)


@dataclass
class NestedArgs:
    child: ChildArgs = field(default_factory=ChildArgs)


def nested_command(args: NestedArgs):
    received.append(args)


@dataclass
class UnsupportedUnionArgs:
    value: int | str = 1


def unsupported_union_command(args: UnsupportedUnionArgs):
    received.append(args)


@dataclass
class FixedTupleArgs:
    coordinates: tuple[int, str] = (0, "")


def fixed_tuple_command(args: FixedTupleArgs):
    received.append(args)


class Choice(Enum):
    FIRST = "first"


@dataclass
class EnumArgs:
    choice: Choice = Choice.FIRST


def enum_command(args: EnumArgs):
    received.append(args)


@dataclass
class SubcommandArgs:
    value: int = 0


def subcommand(args: SubcommandArgs):
    received.append(args)


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.old_argv = sys.argv
        self.old_selected = os.environ.pop("MSUP_TEST_SELECTED", None)
        self.old_enabled = os.environ.pop("MSUP_TEST_ENABLED", None)
        received.clear()

    def tearDown(self):
        sys.argv = self.old_argv
        if self.old_selected is None:
            os.environ.pop("MSUP_TEST_SELECTED", None)
        else:
            os.environ["MSUP_TEST_SELECTED"] = self.old_selected
        if self.old_enabled is None:
            os.environ.pop("MSUP_TEST_ENABLED", None)
        else:
            os.environ["MSUP_TEST_ENABLED"] = self.old_enabled
        received.clear()

    def invoke(self, command, argv, **kwargs):
        sys.argv = ["program", *argv]
        cli(command, **kwargs)
        return received.pop()

    def test_optional_list_accepts_multiple_values(self):
        result = self.invoke(optional_list_command, ["--values", "1", "2"])

        self.assertEqual(result, OptionalListArgs(values=[1, 2]))

    def test_reversed_optional_list_accepts_multiple_values(self):
        result = self.invoke(reversed_optional_list_command, ["--values", "1", "2"])

        self.assertEqual(result, ReversedOptionalListArgs(values=[1, 2]))

    def test_typing_optional_list_accepts_multiple_values(self):
        result = self.invoke(typing_optional_list_command, ["--values", "1", "2"])

        self.assertEqual(result, TypingOptionalListArgs(values=[1, 2]))

    def test_omitted_optional_list_is_none(self):
        result = self.invoke(optional_list_command, [])

        self.assertEqual(result, OptionalListArgs(values=None))

    def test_explicit_empty_optional_list_is_an_empty_list(self):
        result = self.invoke(optional_list_command, ["--values"])

        self.assertEqual(result, OptionalListArgs(values=[]))

    def test_optional_bool_parses_false(self):
        result = self.invoke(optional_bool_command, ["--enabled", "false"])

        self.assertEqual(result, OptionalBoolArgs(enabled=False))

    def test_optional_dict_parses_json(self):
        result = self.invoke(optional_dict_command, ["--values", '{"one": 1}'])

        self.assertEqual(result, OptionalDictArgs(values={"one": 1}))

    def test_optional_dataclass_parses_json(self):
        result = self.invoke(optional_dataclass_command, ["--child", '{"count": 4}'])

        self.assertEqual(result, OptionalDataclassArgs(child=ChildArgs(count=4)))

    def test_optional_callable_loads_function(self):
        result = self.invoke(optional_callable_command, ["--transform", f"{__name__}.callback"])

        self.assertIs(result.transform, callback)

    def test_direct_primitives_are_converted(self):
        result = self.invoke(
            primitive_command,
            ["--count", "4", "--ratio", "2.5", "--name", "updated", "--enabled", "true"],
        )

        self.assertEqual(result, PrimitiveArgs(count=4, ratio=2.5, name="updated", enabled=True))

    def test_direct_boolean_false_is_converted_to_false(self):
        result = self.invoke(primitive_command, ["--enabled", "false"])

        self.assertEqual(result, PrimitiveArgs(enabled=False))

    def test_invalid_direct_boolean_is_rejected(self):
        with self.assertRaises(SystemExit) as error:
            self.invoke(primitive_command, ["--enabled", "not-a-boolean"])

        self.assertEqual(error.exception.code, 2)

    def test_direct_collections_convert_elements_and_accept_multiple_values(self):
        result = self.invoke(
            collection_command,
            ["--numbers", "1", "2", "--labels", "one", "two", "--coordinates", "3", "4"],
        )

        self.assertEqual(result, CollectionArgs(numbers=[1, 2], labels=["one", "two"], coordinates=(3, 4)))

    def test_direct_structured_values_parse_from_json_and_callable_path(self):
        result = self.invoke(
            structured_command,
            ["--values", '{"one": 1}', "--child", '{"count": 4}', "--transform", f"{__name__}.callback"],
        )

        self.assertEqual(result.values, {"one": 1})
        self.assertEqual(result.child, ChildArgs(count=4))
        self.assertIs(result.transform, callback)

    def test_any_is_parsed_as_a_string(self):
        result = self.invoke(any_command, ["--value", "41"])

        self.assertEqual(result, AnyArgs(value="41"))

    def test_explicit_positional_list_captures_remaining_arguments(self):
        result = self.invoke(remainder_command, ["one", "two", "three"])

        self.assertEqual(result, RemainderArgs(extra=["one", "two", "three"]))

    def test_configuration_values_override_dataclass_defaults(self):
        result = self.invoke(source_command, ["--Args", '{"selected": 3, "from_config": 4}'])

        self.assertEqual(result, SourceArgs(selected=3, from_config=4, default_only="default"))

    def test_configuration_boolean_literals_are_converted(self):
        for config, expected in [("{\"enabled\": true}", True), ("{\"enabled\": false}", False)]:
            with self.subTest(config=config):
                result = self.invoke(primitive_command, ["--Args", config])

                self.assertEqual(result, PrimitiveArgs(enabled=expected))

    def test_configuration_boolean_strings_are_converted(self):
        for config, expected in [("{\"enabled\": \"true\"}", True), ("{\"enabled\": \"false\"}", False)]:
            with self.subTest(config=config):
                result = self.invoke(primitive_command, ["--Args", config])

                self.assertEqual(result, PrimitiveArgs(enabled=expected))

    def test_invalid_configuration_boolean_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "invalid boolean value"):
            self.invoke(primitive_command, ["--Args", '{"enabled": "not-a-boolean"}'])

    def test_environment_values_override_configuration(self):
        os.environ["MSUP_TEST_SELECTED"] = "7"
        result = self.invoke(source_command, ["--Args", '{"selected": 3, "from_config": 4}'])

        self.assertEqual(result, SourceArgs(selected=7, from_config=4, default_only="default"))

    def test_environment_false_is_converted_to_false(self):
        os.environ["MSUP_TEST_ENABLED"] = "false"

        result = self.invoke(environment_bool_command, [])

        self.assertEqual(result, EnvironmentBoolArgs(enabled=False))

    def test_environment_true_is_converted_to_true(self):
        os.environ["MSUP_TEST_ENABLED"] = "true"

        result = self.invoke(environment_bool_command, [])

        self.assertEqual(result, EnvironmentBoolArgs(enabled=True))

    def test_invalid_environment_boolean_is_rejected(self):
        os.environ["MSUP_TEST_ENABLED"] = "not-a-boolean"

        with self.assertRaisesRegex(TypeError, "invalid boolean value"):
            self.invoke(environment_bool_command, [])

    def test_cli_values_override_environment_and_configuration(self):
        os.environ["MSUP_TEST_SELECTED"] = "7"
        result = self.invoke(
            source_command,
            ["--Args", '{"selected": 3, "from_config": 4}', "--selected", "9"],
        )

        self.assertEqual(result, SourceArgs(selected=9, from_config=4, default_only="default"))

    def test_positional_configuration_is_loaded(self):
        result = self.invoke(source_command, ['{"selected": 3, "from_config": 4}'], pos_arg_config=True)

        self.assertEqual(result, SourceArgs(selected=3, from_config=4, default_only="default"))

    def test_dotted_nested_option_overrides_a_nested_default(self):
        result = self.invoke(nested_command, ["--child.count", "4"])

        self.assertEqual(result, NestedArgs(child=ChildArgs(count=4)))

    def test_non_optional_unions_report_the_field_and_annotation(self):
        sys.argv = ["program"]

        with self.assertRaisesRegex(TypeError, r"value.*int.*str"):
            cli(unsupported_union_command)

    def test_fixed_length_tuples_report_the_field_and_annotation(self):
        sys.argv = ["program"]

        with self.assertRaisesRegex(TypeError, r"coordinates.*tuple.*int.*str"):
            cli(fixed_tuple_command)

    def test_enum_annotations_report_the_field_and_annotation(self):
        sys.argv = ["program"]

        with self.assertRaisesRegex(TypeError, r"choice.*unsupported CLI annotation.*Choice"):
            cli(enum_command)

    def test_subcommand_uses_the_selected_command_parser(self):
        sys.argv = ["program", "subcommand", "--value", "4"]

        cli({subcommand: "run the subcommand"})

        self.assertEqual(received.pop(), SubcommandArgs(value=4))

    def test_subcommands_without_a_selection_print_help_without_invoking_a_handler(self):
        sys.argv = ["program"]
        output = StringIO()

        with redirect_stdout(output):
            cli({subcommand: "run the subcommand"})

        self.assertIn("subcommand", output.getvalue())
        self.assertEqual(received, [])
