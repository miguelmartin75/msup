from argparse import Namespace
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
from typing import Any, Callable, Optional

from msup.cli import _from_cli_args, argument_type, cli, cliarg, strtobool


received = []


def callback(value: int) -> int:
    return value + 1


@dataclass
class OptionalListArgs:
    values: list[int] | None = None


@dataclass
class ReversedOptionalListArgs:
    values: None | list[int] = None


@dataclass
class TypingOptionalListArgs:
    values: Optional[list[int]] = None


@dataclass
class PrimitiveArgs:
    count: int = 1
    ratio: float = 1.5
    name: str = "default"
    enabled: bool = False


@dataclass
class ChildArgs:
    count: int = 1


@dataclass
class CollectionArgs:
    numbers: list[int] = field(default_factory=list)
    labels: list = field(default_factory=list)
    coordinates: tuple[int, ...] = ()


@dataclass
class StructuredArgs:
    values: dict[str, int] = field(default_factory=dict)
    child: ChildArgs = field(default_factory=ChildArgs)
    transform: Callable[[int], int] = callback


@dataclass
class AnyArgs:
    value: Any = None


@dataclass
class ParserVariantsArgs:
    name: str = cliarg(pos=True, short="n")
    values: list[int] = cliarg(default_factory=list, short="v")
    enabled: bool = cliarg(default=False, short="f")


@dataclass
class RemainderArgs:
    extra: list[str] = cliarg(pos=True, opt=False, default_factory=list)


@dataclass
class PrefixRemainderArgs:
    prefix: str = cliarg(pos=True, default="")
    extra: list[str] = cliarg(pos=True, opt=False, default_factory=list)


@dataclass
class RequiredArgs:
    name: str
    count: int = 3


@dataclass
class SourceArgs:
    selected: int = cliarg(env="MSUP_TEST_SELECTED", default=1)
    from_config: int = 2
    default_only: str = "default"


@dataclass
class HelpArgs:
    visible: str = "visible default"
    secret: str = cliarg(secret=True, default="secret default")
    environment: str = cliarg(env="MSUP_TEST_HELP_VISIBLE", default="environment default")
    secret_environment: str = cliarg(env="MSUP_TEST_HELP_SECRET", secret=True, default="secret environment default")


@dataclass
class EnvironmentBoolArgs:
    enabled: bool = cliarg(env="MSUP_TEST_ENABLED", default=False)


@dataclass
class NestedArgs:
    child: ChildArgs = field(default_factory=ChildArgs)


@dataclass
class EnvironmentNestedArgs:
    child: ChildArgs = cliarg(env="MSUP_TEST_CHILD", default_factory=ChildArgs)


@dataclass
class NonfinalPositionalCollectionArgs:
    values: list[str] = cliarg(pos=True, default_factory=list)
    name: str = "default"


@dataclass
class InvalidShortOptionArgs:
    name: str = cliarg(short="--name", default="default")


@dataclass
class UnsupportedUnionArgs:
    value: int | str = 1


@dataclass
class FixedTupleArgs:
    coordinates: tuple[int, str] = (0, "")


class Choice(Enum):
    FIRST = "first"


@dataclass
class EnumArgs:
    choice: Choice = Choice.FIRST


@dataclass
class SubcommandArgs:
    value: int = 0


def optional_list_command(args: OptionalListArgs):
    received.append(args)


def reversed_optional_list_command(args: ReversedOptionalListArgs):
    received.append(args)


def typing_optional_list_command(args: TypingOptionalListArgs):
    received.append(args)


def primitive_command(args: PrimitiveArgs):
    received.append(args)


def collection_command(args: CollectionArgs):
    received.append(args)


def structured_command(args: StructuredArgs):
    received.append(args)


def any_command(args: AnyArgs):
    received.append(args)


def parser_variants_command(args: ParserVariantsArgs):
    received.append(args)


def remainder_command(args: RemainderArgs):
    received.append(args)


def prefix_remainder_command(args: PrefixRemainderArgs):
    received.append(args)


def required_command(args: RequiredArgs):
    received.append(args)


def source_command(args: SourceArgs):
    received.append(args)


def help_command(args: HelpArgs):
    received.append(args)


def environment_bool_command(args: EnvironmentBoolArgs):
    received.append(args)


def nested_command(args: NestedArgs):
    received.append(args)


def environment_nested_command(args: EnvironmentNestedArgs):
    received.append(args)


def nonfinal_positional_collection_command(args: NonfinalPositionalCollectionArgs):
    received.append(args)


def invalid_short_option_command(args: InvalidShortOptionArgs):
    received.append(args)


def unsupported_union_command(args: UnsupportedUnionArgs):
    received.append(args)


def fixed_tuple_command(args: FixedTupleArgs):
    received.append(args)


def enum_command(args: EnumArgs):
    received.append(args)


def subcommand(args: SubcommandArgs):
    received.append(args)


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.old_argv = sys.argv
        self.old_selected = os.environ.pop("MSUP_TEST_SELECTED", None)
        self.old_enabled = os.environ.pop("MSUP_TEST_ENABLED", None)
        self.old_help_visible = os.environ.pop("MSUP_TEST_HELP_VISIBLE", None)
        self.old_help_secret = os.environ.pop("MSUP_TEST_HELP_SECRET", None)
        self.old_child = os.environ.pop("MSUP_TEST_CHILD", None)
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
        if self.old_help_visible is None:
            os.environ.pop("MSUP_TEST_HELP_VISIBLE", None)
        else:
            os.environ["MSUP_TEST_HELP_VISIBLE"] = self.old_help_visible
        if self.old_help_secret is None:
            os.environ.pop("MSUP_TEST_HELP_SECRET", None)
        else:
            os.environ["MSUP_TEST_HELP_SECRET"] = self.old_help_secret
        if self.old_child is None:
            os.environ.pop("MSUP_TEST_CHILD", None)
        else:
            os.environ["MSUP_TEST_CHILD"] = self.old_child
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

    def test_argument_type_is_public_and_uses_strtobool(self):
        self.assertIs(argument_type(bool, "enabled"), strtobool)
        self.assertTrue(argument_type(bool, "enabled")("yes"))

    def test_invalid_direct_boolean_is_rejected(self):
        output = StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as error:
            self.invoke(primitive_command, ["--enabled", "not-a-boolean"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("--enabled", output.getvalue())
        self.assertIn("not-a-boolean", output.getvalue())

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
        self.assertEqual(self.invoke(remainder_command, ["--a", "test"]), RemainderArgs(extra=["--a", "test"]))
        self.assertEqual(
            self.invoke(prefix_remainder_command, ["first", "--a", "test"]),
            PrefixRemainderArgs(prefix="first", extra=["--a", "test"]),
        )
        self.assertEqual(
            self.invoke(prefix_remainder_command, ["--a", "test"]),
            PrefixRemainderArgs(prefix="", extra=["--a", "test"]),
        )
        self.assertEqual(
            self.invoke(prefix_remainder_command, ["--prefix", "first", "--a", "test"]),
            PrefixRemainderArgs(prefix="first", extra=["--a", "test"]),
        )

    def test_unknown_options_without_a_positional_remainder_are_rejected(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke(primitive_command, ["--a", "test"])
        self.assertEqual(error.exception.code, 2)

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

    def test_help_shows_normal_defaults_but_hides_secret_values(self):
        os.environ["MSUP_TEST_HELP_VISIBLE"] = "visible environment value"
        os.environ["MSUP_TEST_HELP_SECRET"] = "secret environment value"
        sys.argv = ["program", "--help"]
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            cli(help_command)
        self.assertEqual(error.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("Default: visible default", help_text)
        self.assertIn("visible environment value", help_text)
        self.assertNotIn("secret default", help_text)
        self.assertNotIn("secret environment default", help_text)
        self.assertNotIn("secret environment value", help_text)

    def test_dotted_nested_option_overrides_nested_configuration(self):
        result = self.invoke(nested_command, ["--Args", '{"child": {"count": 2}}', "--child.count", "4"])
        self.assertEqual(result, NestedArgs(child=ChildArgs(count=4)))

    def test_nested_dataclass_accepts_json_string_options_and_environment_values(self):
        self.assertEqual(self.invoke(nested_command, ["--child", '{"count": 4}']), NestedArgs(child=ChildArgs(count=4)))
        os.environ["MSUP_TEST_CHILD"] = '{"count": 7}'
        self.assertEqual(self.invoke(environment_nested_command, []), EnvironmentNestedArgs(child=ChildArgs(count=7)))

    def test_nested_dataclass_accepts_dataclass_configuration_values(self):
        result = _from_cli_args(NestedArgs, Namespace(), {"child": ChildArgs(count=6)})
        self.assertEqual(result, NestedArgs(child=ChildArgs(count=6)))

    def test_nonfinal_positional_collections_are_rejected(self):
        with self.assertRaisesRegex(TypeError, "values: positional collection arguments must be declared last"):
            cli(nonfinal_positional_collection_command)

    def test_short_options_must_not_use_long_option_syntax(self):
        with self.assertRaisesRegex(TypeError, "name: short options must not start with --"):
            cli(invalid_short_option_command)

    def test_command_handlers_require_a_dataclass_first_argument(self):
        def invalid_command(value: int):
            pass

        with self.assertRaisesRegex(TypeError, "First argument.*not a dataclass.*int"):
            cli(invalid_command)

    def test_duplicate_subcommand_names_are_rejected(self):
        def duplicate(args: SubcommandArgs):
            received.append(args)

        first_duplicate = duplicate

        def duplicate(args: SubcommandArgs):
            received.append(args)

        with self.assertRaisesRegex(TypeError, "duplicate command occurs more than once"):
            cli({first_duplicate: "first", duplicate: "second"})

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
