import argparse
import inspect
import os
import sys
from collections.abc import Callable as Callable2
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from typing import Any, Callable, TypeVar, get_args, get_origin, get_type_hints

from msup.base import (
    effective_type,
    from_dict_value,
    get_collection_args,
    has_default_value,
    is_optional,
    to_json,
)

T = TypeVar("T")


def cli(cmd_or_cmds: Callable[[T], Any] | dict[Callable[[T], Any], str], **argsparse_kwargs): ...
def cliarg(
    help: str = "",
    short: str | list[str] | None = None,
    env: str | None = None,
    pos: bool = False,
    opt: bool = True,
    secret: bool = False,
    **kwargs,
): ...


def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ("y", "yes", "on", "1", "true", "t"):
        result = True
    elif value in ("n", "no", "off", "0", "false", "f"):
        result = False
    else:
        raise ValueError(f"Invalid truth value {value!r}")
    return result


def cliarg(
    help: str = "",
    short: str | list[str] | None = None,
    env: str | None = None,
    pos: bool = False,
    opt: bool = True,
    secret: bool = False,
    **kwargs,
):
    return field(
        metadata={
            "help": help,
            "short": short if isinstance(short, list) else [short],
            "env": env,
            "pos": pos,
            "opt": opt,
            "secret": secret,
        },
        **kwargs,
    )


def error_exit(msg: str, code: int = 1):
    print(f"[ERROR]: {msg}", file=sys.stderr)
    sys.exit(code)


def _get_first_arg(func):
    hints = get_type_hints(func)
    result = None
    for name in inspect.signature(func).parameters:
        if name not in ("self", "cls"):
            result = hints.get(name)
            break
    if not is_dataclass(result):
        raise TypeError(f"First argument for {getattr(func, '__name__', func)} is not a dataclass: {result}")
    return result


def argument_type(annotation: type, field_name: str) -> type:
    annotation = effective_type(annotation, field_name)
    origin = get_origin(annotation) or annotation
    if annotation is Any or is_dataclass(annotation) or origin in (dict, Callable2):
        result = str
    elif origin is list:
        result = argument_type(get_collection_args(annotation)[0], field_name)
    elif origin is tuple:
        args = get_args(annotation)
        if len(args) != 2 or args[1] is not Ellipsis:
            raise TypeError(f"{field_name}: only variable-length tuple annotations are supported by the CLI: {annotation}")
        result = argument_type(args[0], field_name)
    elif annotation in (str, int, float):
        result = annotation
    elif annotation is bool:
        result = strtobool
    else:
        raise TypeError(f"{field_name}: unsupported CLI annotation: {annotation}")
    return result


def _add_argument(parser, args, kwargs, annotation, field_name, help_text, positional):
    field_type = effective_type(annotation, field_name)
    origin = get_origin(field_type) or field_type
    kwargs = dict(kwargs)
    kwargs["default"] = argparse.SUPPRESS
    kwargs["help"] = help_text

    if origin in (list, tuple):
        kwargs["nargs"] = argparse.REMAINDER if kwargs.get("nargs") == argparse.REMAINDER else "*"
        kwargs["type"] = argument_type(field_type, field_name)
    elif field_type is bool:
        if not positional:
            kwargs["nargs"] = "?"
            kwargs["const"] = True
        kwargs["type"] = strtobool
        kwargs["metavar"] = "{0|1,true|false,yes|no}"
    else:
        kwargs["type"] = argument_type(field_type, field_name)
    parser.add_argument(*args, **kwargs)


def _add_args(
    parser,
    cmd_type: type,
    prefix: str = "",
    short_prefix: str | None = None,
    pos_arg_config: bool = False,
    force_no_default: bool = False,
):
    assert is_dataclass(cmd_type), f"{cmd_type} is not a dataclass"
    if not prefix:
        if pos_arg_config:
            parser.add_argument(
                "args",
                nargs="?",
                type=argument_type(cmd_type, "args"),
                default=argparse.SUPPRESS,
                help=f"configuration for {cmd_type.__name__}",
            )
        parser.add_argument(
            "--Args",
            f"--{cmd_type.__name__}",
            dest="args",
            type=argument_type(cmd_type, "args"),
            default=argparse.SUPPRESS,
            help=f"configuration for {cmd_type.__name__}",
        )

    hints = get_type_hints(cmd_type)
    command_fields = fields(cmd_type)
    for field_index, f in enumerate(command_fields):
        field_name = f.name
        name = f"{prefix}.{field_name}" if prefix else field_name
        annotation = hints[field_name]
        secret = f.metadata.get("secret", False)
        default_help = ""
        if not secret and f.default is not MISSING and (not force_no_default or annotation is bool):
            default_help = f"Default: {f.default}"
        env_name = f.metadata.get("env")
        env_value = os.getenv(env_name) if env_name else None
        if env_value is not None and not secret:
            default_value = from_dict_value(env_value, annotation, str, name)
            default_help = f"Default (using env: ${{{env_name}}}): {default_value}"
        help_text = f.metadata.get("help", "")
        if default_help:
            help_text = f"{help_text}. {default_help}" if help_text else default_help

        positional = f.metadata.get("pos", False)
        optional = f.metadata.get("opt", True)
        collection_origin = get_origin(effective_type(annotation, name))
        if positional and collection_origin in (list, tuple) and field_index != len(command_fields) - 1:
            raise TypeError(f"{name}: positional collection arguments must be declared last")
        if positional:
            remainder = collection_origin in (list, tuple) and not optional
            _add_argument(
                parser,
                [f"{name}_pos"],
                {"nargs": argparse.REMAINDER if remainder else "?"},
                annotation,
                name,
                help_text,
                positional=True,
            )
            if remainder:
                parser.set_defaults(_remainder_dest=f"{name}_pos")
        if optional or not positional:
            option_names = []
            for short_name in f.metadata.get("short", []):
                if short_name is not None:
                    if short_name.startswith("--"):
                        raise TypeError(f"{name}: short options must not start with --")
                    short_name = short_name if short_name.startswith("-") else f"-{short_name}"
                    prefix_to_use = short_prefix if short_prefix is not None else prefix
                    option_names.append(f"-{prefix_to_use}.{short_name[1:]}" if prefix_to_use else short_name)
            option_names.append(f"--{name}")
            _add_argument(parser, option_names, {"dest": name}, annotation, name, help_text, positional=False)

        field_type = effective_type(annotation, name)
        if is_dataclass(field_type):
            child_short = f.metadata.get("short", [None])[0]
            _add_args(parser, field_type, prefix=name, short_prefix=child_short, force_no_default=True)


def _config_values(args) -> dict:
    raw = getattr(args, "args", None)
    if raw is None:
        result = {}
    else:
        result = from_dict_value(raw, dict[str, Any], str, "args")
        if not isinstance(result, dict):
            raise TypeError(f"args: configuration must be a JSON object, got {type(result)}")
    return result


def _parse_args(parser):
    raw_args = sys.argv[1:]
    args, unknown = parser.parse_known_args(raw_args)
    remainder_dest = getattr(args, "_remainder_dest", None)
    if unknown and remainder_dest is not None:
        boundary = raw_args.index(unknown[0])
        args = parser.parse_args(raw_args[:boundary])
        setattr(args, remainder_dest, raw_args[boundary:])
    elif unknown:
        args = parser.parse_args(raw_args)
    return args


def _from_cli_args(clazz: type, args, config: dict | None = None, prefix: str = ""):
    assert is_dataclass(clazz), f"{clazz} is not a dataclass"
    config = {} if config is None else config
    hints = get_type_hints(clazz)
    construct_args = {}
    for f in fields(clazz):
        name = f"{prefix}.{f.name}" if prefix else f.name
        annotation = hints[f.name]
        field_type = effective_type(annotation, name)
        config_value = config.get(f.name, MISSING)
        env_value = os.getenv(f.metadata.get("env")) if f.metadata.get("env") else None
        if hasattr(args, name):
            cli_value = getattr(args, name)
        elif hasattr(args, f"{name}_pos"):
            cli_value = getattr(args, f"{name}_pos")
        else:
            cli_value = MISSING

        if is_dataclass(field_type):
            value = config_value
            if env_value is not None:
                value = env_value
            if cli_value is not MISSING:
                value = cli_value
            if value is MISSING or value is None:
                nested_config = {}
            elif isinstance(value, dict):
                nested_config = value
            elif is_dataclass(value):
                nested_config = {child.name: getattr(value, child.name) for child in fields(value)}
            else:
                converted = from_dict_value(value, field_type, type(value), name)
                nested_config = {child.name: getattr(converted, child.name) for child in fields(converted)}
            construct_args[f.name] = _from_cli_args(field_type, args, nested_config, name)
        else:
            value = config_value
            concrete_type = type(value) if value is not MISSING else None
            if env_value is not None:
                value = env_value
                concrete_type = str
            if cli_value is not MISSING:
                value = cli_value
                concrete_type = type(value)
            if value is not MISSING:
                construct_args[f.name] = from_dict_value(value, annotation, concrete_type, name)
            elif not has_default_value(f) and not is_optional(annotation):
                error_exit(f"--{name} not provided (default value DNE)", 3)
    return clazz(**construct_args)


def cli(cmd_or_cmds: Callable[[T], Any] | dict[Callable[[T], Any], str], pos_arg_config: bool = False, **argsparse_kwargs):
    argsparse_kwargs.setdefault("argument_default", argparse.SUPPRESS)
    parser = argparse.ArgumentParser(**argsparse_kwargs)
    if isinstance(cmd_or_cmds, dict):
        seen = set()
        subparsers = parser.add_subparsers(help="subcommand help")
        for cmd_fn, desc in cmd_or_cmds.items():
            cmd_name = cmd_fn.__name__
            if cmd_name in seen:
                raise TypeError(f"{cmd_name} command occurs more than once")
            seen.add(cmd_name)
            cmd_type = _get_first_arg(cmd_fn)
            p = subparsers.add_parser(cmd_name, help=desc, argument_default=argparse.SUPPRESS)
            p.set_defaults(func=cmd_fn, cmd_type=cmd_type)
            _add_args(p, cmd_type, pos_arg_config=pos_arg_config)
        args = _parse_args(parser)
        if hasattr(args, "func"):
            args.func(_from_cli_args(args.cmd_type, args, _config_values(args)))
        else:
            parser.print_help()
    else:
        _add_args(parser, _get_first_arg(cmd_or_cmds), pos_arg_config=pos_arg_config)
        args = _parse_args(parser)
        cmd_or_cmds(_from_cli_args(_get_first_arg(cmd_or_cmds), args, _config_values(args)))


def ex_default_callable(x: int):
    print("ex_default_callable", x)


def ex_other_callable(x: int):
    print("ex_other_callable", x)


@dataclass
class ExampleArgs:
    name: str
    x: int = 3
    y: float = 10
    zs: list[float] = cliarg(help="a list of zs", default_factory=lambda: [])
    some_callable: Callable[[int], None] = ex_default_callable
    debug: bool = False


def example(args: ExampleArgs):
    print(to_json(args, indent=2))
    args.some_callable(3)


if __name__ == "__main__":
    cli(example)
