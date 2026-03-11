import argparse
import contextlib
import io
import json
import os
import sys
from dataclasses import dataclass
from typing import Callable

from msup.cli import _add_args, _from_cli_args, _get_first_arg, cli, cliarg, ex_default_callable, to_bool


@dataclass
class ModelConfig:
    n_layers: int = cliarg(default=10)
    checkpoint_path: str | None = cliarg(default=None)


@dataclass
class TrainArgs:
    model_config: ModelConfig = cliarg(default_factory=ModelConfig)
    lr: float = 0.01
    name: str = cliarg(default="example")
    lr_step_fn: Callable[[int, float], float] = cliarg(default=None)
    num_workers: int = -1


@dataclass
class RequiredArgs:
    name: str
    count: int = 3


@dataclass
class NestedBoolConfig:
    enabled: bool = cliarg(help="nested bool", default=False)
    keep: bool = cliarg(help="nested bool default true", default=True)


@dataclass
class NestedBoolArgs:
    nested: NestedBoolConfig = cliarg(help="nested config", default_factory=NestedBoolConfig)


@dataclass
class OptionalCallableArgs:
    x: Callable | None = None


@dataclass
class EnvArgs:
    name: str = cliarg(env="MSUP_TEST_NAME")


@dataclass
class DictArgs:
    mapping: dict[str, int]


@dataclass
class CliRunArgs:
    name: str
    count: int = 0


@dataclass
class ParserVariantsArgs:
    name: str = cliarg(pos=True, short="n")
    values: list[int] = cliarg(default_factory=list, short="v")
    flag: bool = cliarg(default=False, short="f")


def _parse_args(clazz: type, argv: list[str]):
    parser = argparse.ArgumentParser()
    _add_args(parser, clazz)
    return _from_cli_args(clazz, parser.parse_args(argv))


def test_args_config_overrides_dataclass_defaults():
    config = json.dumps({
        "model_config": {"n_layers": 3},
        "lr": 0.1,
        "name": "identity",
        "lr_step_fn": "msup.cli.ex_other_callable",
        "num_workers": 42,
    })

    args = _parse_args(TrainArgs, ["--Args", config])

    assert args.model_config.n_layers == 3
    assert args.lr == 0.1
    assert args.name == "identity"
    assert args.lr_step_fn is not None
    assert args.num_workers == 42


def test_explicit_cli_values_override_config():
    config = json.dumps({
        "model_config": {"n_layers": 3},
        "lr": 0.1,
        "name": "identity",
        "num_workers": 42,
    })

    args = _parse_args(TrainArgs, ["--Args", config, "--lr", "0.2", "--model_config.n_layers", "7"])

    assert args.model_config.n_layers == 7
    assert args.lr == 0.2
    assert args.name == "identity"
    assert args.num_workers == 42


def test_required_fields_can_come_from_config():
    args = _parse_args(RequiredArgs, ["--Args", '{"name":"cfg-name"}'])

    assert args.name == "cfg-name"
    assert args.count == 3


def test_missing_required_field_still_errors():
    parser = argparse.ArgumentParser()
    _add_args(parser, RequiredArgs)
    namespace = parser.parse_args([])

    try:
        with contextlib.redirect_stderr(io.StringIO()):
            _from_cli_args(RequiredArgs, namespace)
    except SystemExit:
        return

    assert False, "expected missing required field to raise SystemExit"


def test_nested_bool_defaults_are_preserved():
    args = _parse_args(NestedBoolArgs, [])

    assert args.nested.enabled is False
    assert args.nested.keep is True


def test_nested_bool_cli_values_are_parsed():
    args = _parse_args(NestedBoolArgs, ["--nested.enabled", "true", "--nested.keep", "false"])

    assert args.nested.enabled is True
    assert args.nested.keep is False


def test_optional_callable_cli_value_is_loaded():
    args = _parse_args(OptionalCallableArgs, ["--x", "msup.cli.ex_default_callable"])

    assert args.x is ex_default_callable


def test_env_default_is_used_when_cli_arg_is_missing():
    old_value = os.environ.get("MSUP_TEST_NAME")
    os.environ["MSUP_TEST_NAME"] = "from-env"

    try:
        args = _parse_args(EnvArgs, [])
    finally:
        if old_value is None:
            del os.environ["MSUP_TEST_NAME"]
        else:
            os.environ["MSUP_TEST_NAME"] = old_value

    assert args.name == "from-env"


def test_dict_cli_value_is_loaded_from_json():
    args = _parse_args(DictArgs, ["--mapping", '{"a": 1, "b": 2}'])

    assert args.mapping == {"a": 1, "b": 2}


def test_nested_dataclass_cli_value_can_be_passed_as_json():
    args = _parse_args(NestedBoolArgs, ["--nested", '{"enabled": true, "keep": false}'])

    assert args.nested.enabled is True
    assert args.nested.keep is False


def test_positional_short_and_list_args_are_parsed():
    args = _parse_args(ParserVariantsArgs, ["positional-name", "-v", "1", "2", "3", "-f"])

    assert args.name == "positional-name"
    assert args.values == [1, 2, 3]
    assert args.flag is True


def test_cli_runs_single_command_with_positional_config():
    seen = []

    def run(args: CliRunArgs):
        seen.append(args)

    old_argv = sys.argv
    sys.argv = ["prog", '{"name": "positional", "count": 2}']

    try:
        cli(run, pos_arg_config=True)
    finally:
        sys.argv = old_argv

    assert seen == [CliRunArgs(name="positional", count=2)]


def test_cli_runs_subcommand():
    seen = []

    def train(args: CliRunArgs):
        seen.append(args)

    old_argv = sys.argv
    sys.argv = ["prog", "train", "--name", "sub", "--count", "4"]

    try:
        cli({train: "training command"})
    finally:
        sys.argv = old_argv

    assert seen == [CliRunArgs(name="sub", count=4)]


def test_cli_prints_help_when_no_subcommand_is_selected():
    def train(args: CliRunArgs):
        raise AssertionError("train should not be called when no subcommand is selected")

    stdout = io.StringIO()
    old_argv = sys.argv
    sys.argv = ["prog"]

    try:
        with contextlib.redirect_stdout(stdout):
            cli({train: "training command"})
    finally:
        sys.argv = old_argv

    assert "subcommand help" in stdout.getvalue()


def test_get_first_arg_rejects_non_dataclass_annotations():
    def bad(x: int):
        return x

    try:
        _get_first_arg(bad)
    except TypeError as exc:
        assert "First argument for bad is not a dataclass" in str(exc)
        return

    assert False, "expected _get_first_arg to reject non-dataclass first arguments"


def test_to_bool_rejects_invalid_values():
    try:
        to_bool("maybe")
    except ValueError as exc:
        assert "Invalid truth value" in str(exc)
        return

    assert False, "expected to_bool to reject invalid input"


if __name__ == "__main__":
    test_args_config_overrides_dataclass_defaults()
    test_explicit_cli_values_override_config()
    test_required_fields_can_come_from_config()
    test_missing_required_field_still_errors()
    test_nested_bool_defaults_are_preserved()
    test_nested_bool_cli_values_are_parsed()
    test_optional_callable_cli_value_is_loaded()
    test_env_default_is_used_when_cli_arg_is_missing()
    test_dict_cli_value_is_loaded_from_json()
    test_nested_dataclass_cli_value_can_be_passed_as_json()
    test_positional_short_and_list_args_are_parsed()
    test_cli_runs_single_command_with_positional_config()
    test_cli_runs_subcommand()
    test_cli_prints_help_when_no_subcommand_is_selected()
    test_get_first_arg_rejects_non_dataclass_annotations()
    test_to_bool_rejects_invalid_values()
