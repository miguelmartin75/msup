import argparse
import inspect
import os
import sys
from collections.abc import Callable as Callable2
from dataclasses import MISSING, dataclass, field, is_dataclass
from typing import Annotated, Any, Callable, cast, get_args, get_origin

from msup.base import (
    FieldSpec,
    effective_type,
    fields_or_init_kwargs,
    from_dict_value,
    get_collection_args,
    has_default_value,
    is_optional,
    is_structured_model,
    to_json,
)


def cli(cmd_or_cmds: Callable[..., Any] | dict[Callable[..., Any], str], **argsparse_kwargs): ...


@dataclass(frozen=True)
class CliArg:
    help: str = ""
    short: str | None = ""
    env: str | None = None
    pos: bool = False
    opt: bool = True
    secret: bool = False


def cliarg_from_annotations(annotations: list[Any]) -> CliArg | None:
    cli_args = [value for value in annotations if isinstance(value, CliArg)]
    if len(cli_args) > 1:
        raise TypeError("an annotation can contain at most one CliArg")
    return cli_args[0] if cli_args else None


def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ("y", "yes", "on", "1", "true", "t"):
        result = True
    elif value in ("n", "no", "off", "0", "false", "f"):
        result = False
    else:
        raise ValueError(f"Invalid truth value {value!r}")
    return result


def error_exit(msg: str, code: int = 1):
    print(f"[ERROR]: {msg}", file=sys.stderr)
    sys.exit(code)


def argument_type(annotation: type, field_name: str) -> type:
    annotation = effective_type(annotation, field_name)
    origin = get_origin(annotation) or annotation
    if annotation is Any or is_structured_model(annotation) or origin in (dict, Callable2):
        result = str
    elif origin is list:
        result = argument_type(get_collection_args(annotation)[0], field_name)
    elif origin is tuple:
        args = get_args(annotation)
        if len(args) != 2 or args[1] is not Ellipsis:
            raise TypeError(
                f"{field_name}: only variable-length tuple annotations are supported by the CLI: {annotation}"
            )
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
    assert is_structured_model(cmd_type), f"{cmd_type} is not a structured model"
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

    command_fields = fields_or_init_kwargs(cmd_type)
    for field_index, f in enumerate(command_fields):
        field_name = f.name
        name = f"{prefix}.{field_name}" if prefix else field_name
        annotation = f.annotation
        cli_arg = cliarg_from_annotations(f.annotations)
        cli_arg = cli_arg or CliArg()
        secret = cli_arg.secret
        default_help = ""
        if not secret and f.default is not MISSING and (not force_no_default or annotation is bool):
            default_help = f"Default: {f.default}"
        env_name = cli_arg.env
        env_value = os.getenv(env_name) if env_name else None
        if env_value is not None and not secret:
            default_value = from_dict_value(env_value, annotation, str, name)
            default_help = f"Default (using env: ${{{env_name}}}): {default_value}"
        help_text = cli_arg.help
        if default_help:
            help_text = f"{help_text}. {default_help}" if help_text else default_help

        positional = cli_arg.pos
        optional = cli_arg.opt
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
            option_names = [f"--{name}"]
            if cli_arg.short:
                if cli_arg.short.startswith("--"):
                    raise TypeError(f"{name}: short options must not start with --")
                option_names.insert(
                    0,
                    f"-{short_prefix or prefix}.{cli_arg.short.removeprefix('-')}"
                    if short_prefix or prefix
                    else f"-{cli_arg.short.removeprefix('-')}",
                )
            _add_argument(parser, option_names, {"dest": name}, annotation, name, help_text, positional=False)

        field_type = effective_type(annotation, name)
        if is_structured_model(field_type):
            _add_args(parser, field_type, prefix=name, short_prefix=cli_arg.short, force_no_default=True)


def add_direct_args(parser, command_args: list[FieldSpec], pos_arg_config: bool = False):
    if pos_arg_config:
        parser.add_argument(
            "args",
            nargs="?",
            type=argument_type(dict[str, Any], "args"),
            default=argparse.SUPPRESS,
            help="configuration for command",
        )
    parser.add_argument(
        "--Args",
        dest="args",
        type=argument_type(dict[str, Any], "args"),
        default=argparse.SUPPRESS,
        help="configuration for command",
    )

    for field_index, command_arg in enumerate(command_args):
        name = command_arg.name
        annotation = command_arg.annotation
        cli_arg = cliarg_from_annotations(command_arg.annotations) or CliArg()
        default_help = ""
        if not cli_arg.secret and command_arg.default is not MISSING:
            default_help = f"Default: {command_arg.default}"
        env_value = os.getenv(cli_arg.env) if cli_arg.env else None
        if env_value is not None and not cli_arg.secret:
            default_value = from_dict_value(env_value, annotation, str, name)
            default_help = f"Default (using env: ${{{cli_arg.env}}}): {default_value}"
        help_text = cli_arg.help
        if default_help:
            help_text = f"{help_text}. {default_help}" if help_text else default_help

        positional = cli_arg.pos
        optional = cli_arg.opt
        collection_origin = get_origin(effective_type(annotation, name))
        if positional and collection_origin in (list, tuple) and field_index != len(command_args) - 1:
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
            option_names = [f"--{name}"]
            if cli_arg.short:
                if cli_arg.short.startswith("--"):
                    raise TypeError(f"{name}: short options must not start with --")
                option_names.insert(0, f"-{cli_arg.short.removeprefix('-')}")
            _add_argument(parser, option_names, {"dest": name}, annotation, name, help_text, positional=False)


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


def has_nested_source(clazz: type, args, config: dict, prefix: str) -> bool:
    """Whether config, environment, or CLI supplies a value below ``prefix``."""
    for f in fields_or_init_kwargs(clazz):
        name = f"{prefix}.{f.name}" if prefix else f.name
        annotation = f.annotation
        cli_arg = cliarg_from_annotations(f.annotations)
        if f.name in config or (cli_arg and cli_arg.env and os.getenv(cli_arg.env) is not None):
            return True
        if hasattr(args, name) or hasattr(args, f"{name}_pos"):
            return True
        if is_structured_model(effective_type(annotation, name)) and has_nested_source(
            effective_type(annotation, name), args, config.get(f.name, {}), name
        ):
            return True
    return False


def _from_cli_args(clazz: type, args, config: dict | None = None, prefix: str = ""):
    assert is_structured_model(clazz), f"{clazz} is not a structured model"
    config = {} if config is None else config
    construct_args = {}
    for f in fields_or_init_kwargs(clazz):
        name = f"{prefix}.{f.name}" if prefix else f.name
        annotation = f.annotation
        cli_arg = cliarg_from_annotations(f.annotations)
        field_type = effective_type(annotation, name)
        config_value = config.get(f.name, MISSING)
        env_value = os.getenv(cli_arg.env) if cli_arg and cli_arg.env else None
        if hasattr(args, name):
            cli_value = getattr(args, name)
        elif hasattr(args, f"{name}_pos"):
            cli_value = getattr(args, f"{name}_pos")
        else:
            cli_value = MISSING

        if is_structured_model(field_type):
            value = config_value
            if env_value is not None:
                value = env_value
            if cli_value is not MISSING:
                value = cli_value
            if value is MISSING or value is None:
                nested_config = {}
            elif isinstance(value, dict):
                nested_config = value
            elif is_structured_model(value):
                nested_config = {child.name: getattr(value, child.name) for child in fields_or_init_kwargs(type(value))}
            else:
                converted = from_dict_value(value, field_type, type(value), name)
                nested_config = {
                    child.name: getattr(converted, child.name) for child in fields_or_init_kwargs(type(converted))
                }
            if (
                value is MISSING
                and not has_nested_source(field_type, args, nested_config, name)
                and (not is_dataclass(clazz) or has_default_value(f))
            ):
                continue
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
            elif is_dataclass(clazz) and not has_default_value(f) and not is_optional(annotation):
                error_exit(f"--{name} not provided (default value DNE)", 3)
    return clazz(**construct_args)


def from_direct_cli_args(command_args: list[FieldSpec], args, config: dict | None = None) -> dict:
    config = {} if config is None else config
    result = {}
    for command_arg in command_args:
        name = command_arg.name
        annotation = command_arg.annotation
        cli_arg = cliarg_from_annotations(command_arg.annotations)
        value = config.get(name, MISSING)
        concrete_type = type(value) if value is not MISSING else None
        env_value = os.getenv(cli_arg.env) if cli_arg and cli_arg.env else None
        if env_value is not None:
            value = env_value
            concrete_type = str
        if hasattr(args, name):
            value = getattr(args, name)
            concrete_type = type(value)
        elif hasattr(args, f"{name}_pos"):
            value = getattr(args, f"{name}_pos")
            concrete_type = type(value)

        if value is not MISSING:
            result[name] = from_dict_value(value, annotation, concrete_type, name)
        elif command_arg.default is MISSING:
            error_exit(f"--{name} not provided (default value DNE)", 3)
    return result


def cli(
    cmd_or_cmds: Callable[..., Any] | dict[Callable[..., Any], str], pos_arg_config: bool = False, **argsparse_kwargs
):
    argsparse_kwargs.setdefault("argument_default", argparse.SUPPRESS)
    parser = argparse.ArgumentParser(**argsparse_kwargs)
    commands: list[tuple[Callable[..., Any], str | None]]
    if isinstance(cmd_or_cmds, dict):
        seen = set()
        subparsers = parser.add_subparsers(help="subcommand help")
        commands = list(cast(dict[Callable[..., Any], str], cmd_or_cmds).items())
    else:
        subparsers = None
        commands = [(cmd_or_cmds, None)]

    metadata_marker = object()
    for cmd_fn, desc in commands:
        if subparsers is not None:
            cmd_name = getattr(cmd_fn, "__name__")
            if cmd_name in seen:
                raise TypeError(f"{cmd_name} command occurs more than once")
            seen.add(cmd_name)
            command_parser = subparsers.add_parser(cmd_name, help=desc, argument_default=argparse.SUPPRESS)
        else:
            command_parser = parser

        parameters = [
            parameter
            for parameter in inspect.signature(cmd_fn).parameters.values()
            if parameter.name not in ("self", "cls")
        ]
        for parameter in parameters:
            if parameter.kind is parameter.POSITIONAL_ONLY:
                raise TypeError(f"{parameter.name}: positional-only command parameters are not supported")
            elif parameter.kind is parameter.VAR_POSITIONAL:
                raise TypeError(f"{parameter.name}: variadic *args command parameters are not supported")
            elif parameter.kind is parameter.VAR_KEYWORD:
                raise TypeError(f"{parameter.name}: variadic **kwargs command parameters are not supported")
            elif parameter.annotation is inspect.Parameter.empty:
                raise TypeError(f"{parameter.name}: command parameters must have an annotation")

        command_fields = fields_or_init_kwargs(cmd_fn)
        command_type = command_fields[0].annotation if len(parameters) == 1 else None
        if not is_structured_model(command_type):
            command_type = None
        metadata_dest = "_msup_command"
        metadata_fields = fields_or_init_kwargs(command_type) if command_type is not None else command_fields
        while metadata_dest in {field.name for field in metadata_fields}:
            metadata_dest = f"_{metadata_dest}"
        command_parser.set_defaults(**{metadata_dest: (metadata_marker, cmd_fn, command_type, command_fields)})
        if command_type is not None:
            _add_args(command_parser, command_type, pos_arg_config=pos_arg_config)
        elif command_fields:
            add_direct_args(command_parser, command_fields, pos_arg_config=pos_arg_config)

    args = _parse_args(parser)
    command = None
    for value in vars(args).values():
        if isinstance(value, tuple) and value and value[0] is metadata_marker:
            command = value
            break
    if command is not None:
        _, cmd_fn, command_type, command_fields = command
        config = _config_values(args)
        if command_type is not None:
            cmd_fn(_from_cli_args(command_type, args, config))
        else:
            cmd_fn(**from_direct_cli_args(command_fields, args, config))
    else:
        parser.print_help()
