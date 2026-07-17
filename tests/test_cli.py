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
class PrimitiveArgs:
    count: int = 1
    ratio: float = 1.5
    name: str = "default"
    enabled: bool = False


def primitive_command(args: PrimitiveArgs):
    received.append(args)


@dataclass
class ChildArgs:
    count: int = 1


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
class ParserVariantsArgs:
    name: str = cliarg(pos=True, short="n")
    values: list[int] = cliarg(default_factory=list, short="v")
    enabled: bool = cliarg(default=False, short="f")


def parser_variants_command(args: ParserVariantsArgs):
    received.append(args)


@dataclass
class RemainderArgs:
    extra: list[str] = cliarg(pos=True, opt=False, default_factory=list)


def remainder_command(args: RemainderArgs):
    received.append(args)


@dataclass
class RequiredArgs:
    name: str
    count: int = 3


def required_command(args: RequiredArgs):
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

    def test_optional_lists_preserve_all_supported_annotation_forms(self):
        cases = [
            (optional_list_command, OptionalListArgs),
            (reversed_optional_list_command, ReversedOptionalListArgs),
            (typing_optional_list_command, TypingOptionalListArgs),
        ]
        for command, args_type in cases:
            with self.subTest(args_type=args_type):
                self.assertEqual(self.invoke(command, ["--values", "1", "2"]), args_type(values=[1, 2]))
        self.assertEqual(self.invoke(optional_list_command, []), OptionalListArgs(values=None))
        self.assertEqual(self.invoke(optional_list_command, ["--values"]), OptionalListArgs(values=[]))

    def test_direct_primitives_convert_true_and_false(self):
        for value, expected in [("true", True), ("false", False)]:
            with self.subTest(value=value):
                result = self.invoke(primitive_command, ["--count", "4", "--ratio", "2.5", "--name", "updated", "--enabled", value])
                self.assertEqual(result, PrimitiveArgs(count=4, ratio=2.5, name="updated", enabled=expected))

    def test_invalid_direct_boolean_is_rejected(self):
        with self.assertRaises(SystemExit) as error:
            self.invoke(primitive_command, ["--enabled", "not-a-boolean"])
        self.assertEqual(error.exception.code, 2)

    def test_collections_convert_elements_and_accept_multiple_values(self):
        result = self.invoke(collection_command, ["--numbers", "1", "2", "--labels", "one", "two", "--coordinates", "3", "4"])
        self.assertEqual(result, CollectionArgs(numbers=[1, 2], labels=["one", "two"], coordinates=(3, 4)))

    def test_structured_values_parse_from_json_and_callable_paths(self):
        result = self.invoke(structured_command, ["--values", '{"one": 1}', "--child", '{"count": 4}', "--transform", f"{__name__}.callback"])
        self.assertEqual(result.values, {"one": 1})
        self.assertEqual(result.child, ChildArgs(count=4))
        self.assertIs(result.transform, callback)

    def test_any_is_parsed_as_a_string(self):
        self.assertEqual(self.invoke(any_command, ["--value", "41"]), AnyArgs(value="41"))

    def test_short_options_positional_and_list_arguments_are_parsed(self):
        result = self.invoke(parser_variants_command, ["positional-name", "-v", "1", "2", "3", "-f"])
        self.assertEqual(result, ParserVariantsArgs(name="positional-name", values=[1, 2, 3], enabled=True))

    def test_positional_remainder_captures_all_arguments(self):
        self.assertEqual(self.invoke(remainder_command, ["one", "two", "three"]), RemainderArgs(extra=["one", "two", "three"]))

    def test_required_values_can_come_from_configuration_and_are_enforced(self):
        self.assertEqual(self.invoke(required_command, ['--Args', '{"name": "cfg-name"}']), RequiredArgs(name="cfg-name"))
        with self.assertRaises(SystemExit) as error:
            self.invoke(required_command, [])
        self.assertEqual(error.exception.code, 3)

    def test_configuration_environment_and_cli_follow_source_precedence(self):
        config = '{"selected": 3, "from_config": 4}'
        self.assertEqual(self.invoke(source_command, ["--Args", config]), SourceArgs(selected=3, from_config=4, default_only="default"))
        os.environ["MSUP_TEST_SELECTED"] = "7"
        self.assertEqual(self.invoke(source_command, ["--Args", config]), SourceArgs(selected=7, from_config=4, default_only="default"))
        self.assertEqual(self.invoke(source_command, ["--Args", config, "--selected", "9"]), SourceArgs(selected=9, from_config=4, default_only="default"))

    def test_configuration_booleans_are_converted(self):
        cases = [
            ('{"enabled": true}', True),
            ('{"enabled": false}', False),
            ('{"enabled": "true"}', True),
            ('{"enabled": "false"}', False),
        ]
        for config, expected in cases:
            with self.subTest(config=config):
                self.assertEqual(self.invoke(primitive_command, ["--Args", config]), PrimitiveArgs(enabled=expected))

    def test_environment_boolean_false_is_converted(self):
        os.environ["MSUP_TEST_ENABLED"] = "false"
        self.assertEqual(self.invoke(environment_bool_command, []), EnvironmentBoolArgs(enabled=False))

    def test_positional_configuration_is_loaded(self):
        result = self.invoke(source_command, ['{"selected": 3, "from_config": 4}'], pos_arg_config=True)
        self.assertEqual(result, SourceArgs(selected=3, from_config=4, default_only="default"))

    def test_dotted_nested_option_overrides_nested_configuration(self):
        result = self.invoke(nested_command, ["--Args", '{"child": {"count": 2}}', "--child.count", "4"])
        self.assertEqual(result, NestedArgs(child=ChildArgs(count=4)))

    def test_unsupported_annotations_report_the_field_and_annotation(self):
        cases = [
            (unsupported_union_command, r"value.*int.*str"),
            (fixed_tuple_command, r"coordinates.*tuple.*int.*str"),
            (enum_command, r"choice.*unsupported CLI annotation.*Choice"),
        ]
        for command, message in cases:
            with self.subTest(command=command.__name__):
                sys.argv = ["program"]
                with self.assertRaisesRegex(TypeError, message):
                    cli(command)

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


if __name__ == "__main__":
    unittest.main()
