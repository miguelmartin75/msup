import argparse
import contextlib
import io
import json
from dataclasses import dataclass
from typing import Callable

from msup.cli import _add_args, _from_cli_args, cliarg


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


if __name__ == "__main__":
    test_args_config_overrides_dataclass_defaults()
    test_explicit_cli_values_override_config()
    test_required_fields_can_come_from_config()
    test_missing_required_field_still_errors()
    test_nested_bool_defaults_are_preserved()
    test_nested_bool_cli_values_are_parsed()
