from argparse import Namespace
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError, dataclass, field
from enum import Enum
from io import StringIO
from typing import Annotated, Any, Callable, Optional, cast

from msup.cli import CliArg, _from_cli_args, argument_type, cli, strtobool


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
    name: Annotated[str, CliArg(pos=True, short="n")]
    values: Annotated[list[int], CliArg(short="v")] = field(default_factory=list)
    enabled: Annotated[bool, CliArg(short="f")] = False


@dataclass
class RemainderArgs:
    extra: Annotated[list[str], CliArg(pos=True, opt=False)] = field(default_factory=list)


@dataclass
class PrefixRemainderArgs:
    prefix: Annotated[str, CliArg(pos=True)] = ""
    extra: Annotated[list[str], CliArg(pos=True, opt=False)] = field(default_factory=list)


@dataclass
class RequiredArgs:
    name: str
    count: int = 3


@dataclass
class SourceArgs:
    selected: Annotated[int, CliArg(env="MSUP_TEST_SELECTED")] = 1
    from_config: int = 2
    default_only: str = "default"


@dataclass
class HelpArgs:
    visible: str = "visible default"
    secret: Annotated[str, CliArg(secret=True)] = "secret default"
    environment: Annotated[str, CliArg(env="MSUP_TEST_HELP_VISIBLE")] = "environment default"
    secret_environment: Annotated[str, CliArg(env="MSUP_TEST_HELP_SECRET", secret=True)] = "secret environment default"


@dataclass
class EnvironmentBoolArgs:
    enabled: Annotated[bool, CliArg(env="MSUP_TEST_ENABLED")] = False


@dataclass
class NestedArgs:
    child: ChildArgs = field(default_factory=ChildArgs)


@dataclass
class DefaultNestedArgs:
    child: ChildArgs = field(default_factory=lambda: ChildArgs(count=2))


@dataclass
class EnvironmentNestedArgs:
    child: Annotated[ChildArgs, CliArg(env="MSUP_TEST_CHILD")] = field(default_factory=ChildArgs)


@dataclass
class NonfinalPositionalCollectionArgs:
    values: Annotated[list[str], CliArg(pos=True)] = field(default_factory=list)
    name: str = "default"


@dataclass
class InvalidShortOptionArgs:
    name: Annotated[str, CliArg(short="--name")] = "default"


@dataclass
class EmptyShortOptionArgs:
    value: Annotated[int, CliArg(short="")] = 1


@dataclass
class UnrelatedMetadataArgs:
    value: Annotated[int, "unrelated", CliArg(short="v")] = 1


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


@dataclass
class CommandMetadataArgs:
    func: str
    command_type: str
    command_fields: str
    _msup_command: str


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


def default_nested_command(args: DefaultNestedArgs):
    received.append(args)


def environment_nested_command(args: EnvironmentNestedArgs):
    received.append(args)


def nonfinal_positional_collection_command(args: NonfinalPositionalCollectionArgs):
    received.append(args)


def invalid_short_option_command(args: InvalidShortOptionArgs):
    received.append(args)


def empty_short_option_command(args: EmptyShortOptionArgs):
    received.append(args)


def unrelated_metadata_command(args: UnrelatedMetadataArgs):
    received.append(args)


def unsupported_union_command(args: UnsupportedUnionArgs):
    received.append(args)


def fixed_tuple_command(args: FixedTupleArgs):
    received.append(args)


def enum_command(args: EnumArgs):
    received.append(args)


def subcommand(args: SubcommandArgs):
    received.append(args)


def command_metadata_command(args: CommandMetadataArgs):
    received.append(args)


def direct_command_metadata(func: str, command_type: str, command_fields: str, _msup_command: str):
    received.append((func, command_type, command_fields, _msup_command))


def direct_command(
    count: Annotated[int, CliArg(help="item count", short="c", env="MSUP_TEST_DIRECT_COUNT")],
    ratio: Annotated[float, CliArg(help="ratio")] = 1.5,
    name: str = "default",
    enabled: bool = False,
    optional: int | None = None,
    values: list[int] | None = None,
    transform: Callable[[int], int] = callback,
    mapping: dict[str, int] | None = None,
    child: ChildArgs | None = None,
):
    received.append(
        {
            "count": count,
            "ratio": ratio,
            "name": name,
            "enabled": enabled,
            "optional": optional,
            "values": values,
            "transform": transform,
            "mapping": mapping,
            "child": child,
        }
    )


def direct_positional_command(
    name: Annotated[str, CliArg(pos=True)],
    extra: Annotated[list[str] | None, CliArg(pos=True, opt=False)] = None,
):
    received.append((name, extra))


def direct_subcommand(count: int, name: str = "default"):
    received.append((count, name))


def zero_parameter_command():
    received.append("zero parameter command")


def zero_parameter_subcommand():
    received.append("zero parameter subcommand")


def direct_command_with_reserved_names(self: int, cls: str, count: int):
    received.append((self, cls, count))


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.old_argv = sys.argv
        self.old_selected = os.environ.pop("MSUP_TEST_SELECTED", None)
        self.old_enabled = os.environ.pop("MSUP_TEST_ENABLED", None)
        self.old_help_visible = os.environ.pop("MSUP_TEST_HELP_VISIBLE", None)
        self.old_help_secret = os.environ.pop("MSUP_TEST_HELP_SECRET", None)
        self.old_child = os.environ.pop("MSUP_TEST_CHILD", None)
        self.old_direct_count = os.environ.pop("MSUP_TEST_DIRECT_COUNT", None)
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
        if self.old_direct_count is None:
            os.environ.pop("MSUP_TEST_DIRECT_COUNT", None)
        else:
            os.environ["MSUP_TEST_DIRECT_COUNT"] = self.old_direct_count
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
                result = self.invoke(
                    primitive_command, ["--count", "4", "--ratio", "2.5", "--name", "updated", "--enabled", value]
                )
                self.assertEqual(result, PrimitiveArgs(count=4, ratio=2.5, name="updated", enabled=expected))

    def test_argument_type_is_public_and_uses_strtobool(self):
        self.assertIs(argument_type(bool, "enabled"), strtobool)
        self.assertTrue(argument_type(bool, "enabled")("yes"))

    def test_cliarg_accepts_no_short_option_and_is_immutable(self):
        self.assertEqual(CliArg().short, "")
        self.assertEqual(CliArg(short="").short, "")
        self.assertIsNone(CliArg(short=None).short)
        self.assertEqual(CliArg(short="v").short, "v")

        cli_arg = CliArg(short="v")
        with self.assertRaises(FrozenInstanceError):
            cast(Any, cli_arg).short = "x"

    def test_unrelated_annotated_metadata_is_ignored(self):
        self.assertEqual(
            self.invoke(unrelated_metadata_command, ["-v", "4"]),
            UnrelatedMetadataArgs(value=4),
        )

    def test_invalid_direct_boolean_is_rejected(self):
        output = StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as error:
            self.invoke(primitive_command, ["--enabled", "not-a-boolean"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("--enabled", output.getvalue())
        self.assertIn("not-a-boolean", output.getvalue())

    def test_collections_convert_elements_and_accept_multiple_values(self):
        result = self.invoke(
            collection_command, ["--numbers", "1", "2", "--labels", "one", "two", "--coordinates", "3", "4"]
        )
        self.assertEqual(result, CollectionArgs(numbers=[1, 2], labels=["one", "two"], coordinates=(3, 4)))

    def test_structured_values_parse_from_json_and_callable_paths(self):
        result = self.invoke(
            structured_command,
            ["--values", '{"one": 1}', "--child", '{"count": 4}', "--transform", f"{__name__}.callback"],
        )
        self.assertEqual(result.values, {"one": 1})
        self.assertEqual(result.child, ChildArgs(count=4))
        self.assertIs(result.transform, callback)

    def test_any_is_parsed_as_a_string(self):
        self.assertEqual(self.invoke(any_command, ["--value", "41"]), AnyArgs(value="41"))

    def test_short_options_positional_and_list_arguments_are_parsed(self):
        result = self.invoke(parser_variants_command, ["positional-name", "-v", "1", "2", "3", "-f"])
        self.assertEqual(result, ParserVariantsArgs(name="positional-name", values=[1, 2, 3], enabled=True))

    def test_empty_short_option_registers_only_the_long_option(self):
        self.assertEqual(
            self.invoke(empty_short_option_command, ["--value", "4"]),
            EmptyShortOptionArgs(value=4),
        )
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke(empty_short_option_command, ["-", "4"])
        self.assertEqual(error.exception.code, 2)

    def test_positional_remainder_captures_all_arguments(self):
        self.assertEqual(
            self.invoke(remainder_command, ["one", "two", "three"]), RemainderArgs(extra=["one", "two", "three"])
        )
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
        self.assertEqual(
            self.invoke(required_command, ["--Args", '{"name": "cfg-name"}']), RequiredArgs(name="cfg-name")
        )
        with self.assertRaises(SystemExit) as error:
            self.invoke(required_command, [])
        self.assertEqual(error.exception.code, 3)

    def test_configuration_environment_and_cli_follow_source_precedence(self):
        config = '{"selected": 3, "from_config": 4}'
        self.assertEqual(
            self.invoke(source_command, ["--Args", config]),
            SourceArgs(selected=3, from_config=4, default_only="default"),
        )
        os.environ["MSUP_TEST_SELECTED"] = "7"
        self.assertEqual(
            self.invoke(source_command, ["--Args", config]),
            SourceArgs(selected=7, from_config=4, default_only="default"),
        )
        self.assertEqual(
            self.invoke(source_command, ["--Args", config, "--selected", "9"]),
            SourceArgs(selected=9, from_config=4, default_only="default"),
        )

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

    def test_nested_dataclass_preserves_declared_default_without_sources(self):
        self.assertEqual(self.invoke(default_nested_command, []), DefaultNestedArgs(child=ChildArgs(count=2)))

    def test_nested_dataclass_accepts_dataclass_configuration_values(self):
        result = _from_cli_args(NestedArgs, Namespace(), {"child": ChildArgs(count=6)})
        self.assertEqual(result, NestedArgs(child=ChildArgs(count=6)))

    def test_nonfinal_positional_collections_are_rejected(self):
        with self.assertRaisesRegex(TypeError, "values: positional collection arguments must be declared last"):
            cli(nonfinal_positional_collection_command)

    def test_short_options_must_not_use_long_option_syntax(self):
        with self.assertRaisesRegex(TypeError, "name: short options must not start with --"):
            cli(invalid_short_option_command)

    def test_duplicate_cliarg_metadata_is_rejected(self):
        @dataclass
        class DuplicateCliArgArgs:
            value: Annotated[int, CliArg(help="first"), CliArg(help="second")] = 1

        def duplicate_cliarg_command(args: DuplicateCliArgArgs):
            received.append(args)

        with self.assertRaisesRegex(TypeError, "at most one CliArg"):
            cli(duplicate_cliarg_command)

    def test_direct_parameters_convert_values_and_keep_python_defaults(self):
        result = self.invoke(
            direct_command,
            [
                "-c",
                "4",
                "--ratio",
                "2.5",
                "--name",
                "updated",
                "--enabled",
                "true",
                "--optional",
                "3",
                "--values",
                "1",
                "2",
                "--transform",
                f"{__name__}.callback",
                "--mapping",
                '{"one": 1}',
                "--child",
                '{"count": 6}',
            ],
        )
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["ratio"], 2.5)
        self.assertEqual(result["name"], "updated")
        self.assertTrue(result["enabled"])
        self.assertEqual(result["optional"], 3)
        self.assertEqual(result["values"], [1, 2])
        self.assertIs(result["transform"], callback)
        self.assertEqual(result["mapping"], {"one": 1})
        self.assertEqual(result["child"], ChildArgs(count=6))

        defaults = self.invoke(direct_command, ["--Args", '{"count": 5}'])
        self.assertEqual(
            defaults,
            {
                "count": 5,
                "ratio": 1.5,
                "name": "default",
                "enabled": False,
                "optional": None,
                "values": None,
                "transform": callback,
                "mapping": None,
                "child": None,
            },
        )

    def test_direct_parameters_exclude_reserved_self_and_cls_names(self):
        sys.argv = ["program", "--help"]
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            cli(direct_command_with_reserved_names)
        self.assertEqual(error.exception.code, 0)
        self.assertIn("--count", output.getvalue())
        self.assertNotIn("--self", output.getvalue())
        self.assertNotIn("--cls", output.getvalue())

    def test_command_metadata_does_not_collide_with_root_fields(self):
        argv = [
            "--func",
            "function",
            "--command_type",
            "type",
            "--command_fields",
            "fields",
            "--_msup_command",
            "private",
        ]
        expected = ("function", "type", "fields", "private")
        self.assertEqual(self.invoke(direct_command_metadata, argv), expected)
        self.assertEqual(self.invoke(command_metadata_command, argv), CommandMetadataArgs(*expected))

    def test_direct_parameters_support_help_args_environment_and_cli_precedence(self):
        sys.argv = ["program", "--help"]
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            cli(direct_command)
        self.assertEqual(error.exception.code, 0)
        self.assertIn("item count", output.getvalue())
        self.assertIn("Default: 1.5", output.getvalue())

        config = '{"count": 3, "ratio": 4.5}'
        self.assertEqual(self.invoke(direct_command, ["--Args", config])["count"], 3)
        os.environ["MSUP_TEST_DIRECT_COUNT"] = "7"
        self.assertEqual(self.invoke(direct_command, ["--Args", config])["count"], 7)
        self.assertEqual(self.invoke(direct_command, ["--Args", config, "--count", "9"])["count"], 9)

    def test_direct_parameters_accept_configuration_and_structured_json_paths(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as config_file:
            config_file.write('{"count": 6, "name": "from-path"}')
            config_path = config_file.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as child_file:
            child_file.write('{"count": 8}')
            child_path = child_file.name
        try:
            result = self.invoke(direct_command, ["--Args", config_path, "--child", child_path])
        finally:
            os.unlink(config_path)
            os.unlink(child_path)
        self.assertEqual(result["count"], 6)
        self.assertEqual(result["name"], "from-path")
        self.assertEqual(result["child"], ChildArgs(count=8))

    def test_direct_positional_parameters_allow_a_final_remainder(self):
        self.assertEqual(
            self.invoke(direct_positional_command, ["first", "--unknown", "value"]),
            ("first", ["--unknown", "value"]),
        )

    def test_direct_parameters_work_in_subcommand_mappings(self):
        sys.argv = ["program", "direct_subcommand", "--count", "4", "--name", "selected"]
        cli({direct_subcommand: "run the direct subcommand"})
        self.assertEqual(received.pop(), (4, "selected"))

    def test_zero_parameter_command_is_invoked(self):
        self.assertEqual(self.invoke(zero_parameter_command, []), "zero parameter command")

    def test_zero_parameter_subcommand_is_invoked(self):
        sys.argv = ["program", "zero_parameter_subcommand"]
        cli({zero_parameter_subcommand: "run the zero-parameter subcommand"})
        self.assertEqual(received.pop(), "zero parameter subcommand")

    def test_invalid_direct_handler_signatures_are_rejected_before_parsing(self):
        def unannotated_command(value):
            pass

        def positional_only_command(value: int, /):
            pass

        def variadic_positional_command(*values: int):
            pass

        def variadic_keyword_command(**values: int):
            pass

        def structured_positional_only(args: PrimitiveArgs, /):
            pass

        def structured_variadic(*args: PrimitiveArgs):
            pass

        cases = [
            (unannotated_command, "value.*annotation"),
            (positional_only_command, "value.*positional"),
            (variadic_positional_command, "values.*variadic"),
            (variadic_keyword_command, "values.*variadic"),
            (structured_positional_only, "args.*positional"),
            (structured_variadic, "args.*variadic"),
        ]
        for command, message in cases:
            with self.subTest(command=command.__name__):
                with self.assertRaisesRegex(TypeError, message):
                    cli(command)

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
        ]
        for command, message in cases:
            with self.subTest(command=command.__name__):
                sys.argv = ["program"]
                with self.assertRaisesRegex(TypeError, message):
                    cli(command)

    def test_enum_arguments_accept_member_values_and_reject_invalid_values(self):
        self.assertEqual(self.invoke(enum_command, ["--choice", "first"]), EnumArgs(Choice.FIRST))
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            self.invoke(enum_command, ["--choice", "missing"])
        self.assertEqual(error.exception.code, 2)

    def test_subcommand_uses_the_selected_command_parser(self):
        sys.argv = ["program", "subcommand", "--value", "4"]
        cli({subcommand: "run the subcommand"})
        self.assertEqual(received.pop(), SubcommandArgs(value=4))

    def test_subcommands_without_a_selection_print_help_without_invoking_a_handler(self):
        sys.argv = ["program"]
        output = StringIO()
        with redirect_stdout(output):
            cli(
                {
                    subcommand: "run the subcommand",
                    zero_parameter_subcommand: "run the zero-parameter subcommand",
                }
            )
        self.assertIn("subcommand", output.getvalue())
        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
