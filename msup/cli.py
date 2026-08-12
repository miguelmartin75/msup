import argparse
import inspect
import os
import sys
from collections.abc import Callable as Callable2, Mapping
from copy import deepcopy
from dataclasses import MISSING, dataclass, is_dataclass
from typing import Any, Callable, cast, get_args, get_origin

from msup.base import (
    FieldSpec,
    Metadata,
    enum_type,
    effective_type,
    fields_or_init_kwargs,
    from_dict_value,
    get_collection_args,
    has_default_value,
    is_pydantic_model,
    is_structured_model,
    metadata_from_annotations,
    selected_target_fields,
    str_to_bool,
    to_kwargs,
)


def cli(cmd_or_cmds: Callable[..., Any] | dict[Callable[..., Any], str], **argsparse_kwargs): ...


@dataclass(frozen=True)
class CliArg(Metadata):
    help: str = ""
    short: str | None = ""
    env: str | None = None
    pos: bool = False
    opt: bool = True
    secret: bool = False


def cliarg_from_annotations(annotations: list[Any]) -> CliArg | None:
    metadata = metadata_from_annotations(annotations)
    result = metadata if isinstance(metadata, CliArg) else None
    return result


def _contains_relation(owner: type | Callable[..., Any]) -> bool:
    return any(field.kwargs_relation is not None for field in fields_or_init_kwargs(owner))


def error_exit(msg: str, code: int = 1):
    print(f"[ERROR]: {msg}", file=sys.stderr)
    sys.exit(code)


def enum_argument_type(annotation: Any, field_name: str) -> Callable[[str], Any]:
    enum_class = enum_type(annotation)
    assert enum_class is not None
    values_by_text: dict[str, Any] = {}
    for member in enum_class:
        text = str(member.value)
        if text in values_by_text:
            raise TypeError(f"{field_name}: {enum_class.__name__} has ambiguous CLI value {text!r}")
        values_by_text[text] = member.value

    def convert(value: str) -> Any:
        if value not in values_by_text:
            raise argparse.ArgumentTypeError(
                f"{field_name}: invalid {enum_class.__name__} value {value!r}; expected one of {list(values_by_text)}"
            )
        return from_dict_value(values_by_text[value], enum_class, type(values_by_text[value]), field_name)

    return convert


def mapping_argument_type(field_name: str) -> Callable[[str], dict[str, Any]]:
    def convert(value: str) -> dict[str, Any]:
        try:
            return from_dict_value(value, dict[str, Any], str, field_name)
        except (AssertionError, AttributeError, OSError, ValueError) as error:
            raise argparse.ArgumentTypeError(f"{field_name}: {error}") from error

    return convert


def argument_type(annotation: Any, field_name: str) -> type | Callable[[str], Any]:
    annotation = effective_type(annotation, field_name)
    origin = get_origin(annotation) or annotation
    if annotation is Any or origin is Callable2:
        result = str
    elif is_structured_model(annotation) or origin is dict:
        result = mapping_argument_type(field_name)
    elif (
        inspect.isclass(annotation)
        and annotation.__module__ not in ("builtins", "collections.abc")
        and enum_type(annotation) is None
        and _contains_relation(annotation)
    ):
        result = mapping_argument_type(field_name)
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
        result = str_to_bool
    elif enum_type(annotation) is not None:
        result = enum_argument_type(annotation, field_name)
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
        kwargs["type"] = str_to_bool
        kwargs["metavar"] = "{0|1,true|false,yes|no}"
    elif (enum_class := enum_type(field_type)) is not None:
        kwargs["type"] = enum_argument_type(field_type, field_name)
        kwargs["metavar"] = "{" + ",".join(str(member.value) for member in enum_class) + "}"
    else:
        kwargs["type"] = argument_type(field_type, field_name)
    parser.add_argument(*args, **kwargs)


def _add_fields(parser, command_fields, prefix="", short_prefix=None, force_no_default=False):
    parser._msup_fields[tuple(prefix.split(".")) if prefix else ()] = command_fields
    for field_index, f in enumerate(command_fields):
        name = f"{prefix}.{f.name}" if prefix else f.name
        annotation = dict[str, Any] if f.kwargs_relation is not None else f.annotation
        cli_arg = cliarg_from_annotations(f.annotations) or CliArg()
        default_help = ""
        if not cli_arg.secret and f.default is not MISSING and (not force_no_default or annotation is bool):
            if not callable(f.default):
                default_help = f"Default: {f.default}"
        env_value = os.getenv(cli_arg.env) if cli_arg.env else None
        if env_value is not None and not cli_arg.secret:
            default_help = f"Default (using env: ${{{cli_arg.env}}}): {env_value}"
        help_text = cli_arg.help
        if default_help:
            help_text = f"{help_text}. {default_help}" if help_text else default_help
        collection_origin = get_origin(effective_type(annotation, name))
        if cli_arg.pos and collection_origin in (list, tuple) and field_index != len(command_fields) - 1:
            raise TypeError(f"{name}: positional collection arguments must be declared last")
        if cli_arg.pos:
            remainder = collection_origin in (list, tuple) and not cli_arg.opt
            _add_argument(
                parser,
                [f"{name}_pos"],
                {"nargs": argparse.REMAINDER if remainder else "?"},
                annotation,
                name,
                help_text,
                True,
            )
            if remainder:
                parser.set_defaults(_remainder_dest=f"{name}_pos")
        if cli_arg.opt or not cli_arg.pos:
            option_names = [f"--{name}"]
            if cli_arg.short:
                if cli_arg.short.startswith("--"):
                    raise TypeError(f"{name}: short options must not start with --")
                short = cli_arg.short.removeprefix("-")
                option_names.insert(0, f"-{short_prefix or prefix}.{short}" if prefix else f"-{short}")
            _add_argument(parser, option_names, {"dest": name}, annotation, name, help_text, False)

        field_type = effective_type(annotation, name)
        if is_structured_model(field_type):
            _add_args(parser, field_type, prefix=name, short_prefix=cli_arg.short, force_no_default=True)
        elif (
            inspect.isclass(field_type)
            and field_type.__module__ not in ("builtins", "collections.abc")
            and enum_type(field_type) is None
            and _contains_relation(field_type)
        ):
            _add_fields(parser, fields_or_init_kwargs(field_type), name, cli_arg.short, True)


def _add_args(
    parser, cmd_type, prefix="", short_prefix=None, pos_arg_config=False, force_no_default=False, fields=None
):
    if not prefix:
        if pos_arg_config:
            parser.add_argument("args", nargs="?", type=argument_type(cmd_type, "args"), default=argparse.SUPPRESS)
        parser.add_argument(
            "--Args",
            f"--{cmd_type.__name__}",
            dest="args",
            type=argument_type(cmd_type, "args"),
            default=argparse.SUPPRESS,
            help=f"configuration for {cmd_type.__name__}",
        )
    _add_fields(parser, fields or fields_or_init_kwargs(cmd_type), prefix, short_prefix, force_no_default)


def add_direct_args(parser, command_args: list[FieldSpec], pos_arg_config: bool = False):
    if pos_arg_config:
        parser.add_argument("args", nargs="?", type=argument_type(dict[str, Any], "args"), default=argparse.SUPPRESS)
    parser.add_argument(
        "--Args",
        dest="args",
        type=argument_type(dict[str, Any], "args"),
        default=argparse.SUPPRESS,
        help="configuration for command",
    )
    _add_fields(parser, command_args)


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
        config_value = config.get(f.name, MISSING)
        if config_value is not MISSING or (cli_arg and cli_arg.env and os.getenv(cli_arg.env) is not None):
            return True
        if hasattr(args, name) or hasattr(args, f"{name}_pos"):
            return True
        if is_structured_model(effective_type(annotation, name)) and has_nested_source(
            effective_type(annotation, name), args, config_value if isinstance(config_value, dict) else {}, name
        ):
            return True
    return False


def _merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        result[key] = (
            _merge(cast(Mapping[str, Any], result[key]), value)
            if isinstance(result.get(key), Mapping) and isinstance(value, Mapping)
            else value
        )
    return result


def _target_options(parser, targets, path, args=None):
    result = {}
    for field in targets[path]:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        field_type = effective_type(field.annotation, name)
        if args is None:
            cli_arg = cliarg_from_annotations(field.annotations) or CliArg()
            if cli_arg.short or cli_arg.pos:
                raise TypeError(f"{name}: selected target parameters cannot define short or positional options")
            _add_argument(parser, [f"--{name}"], {"dest": name}, field.annotation, name, cli_arg.help, False)
            if is_structured_model(field_type):
                if _contains_relation(field_type):
                    raise TypeError(f"{name}: selected target parameters cannot contain kwargs_for relations")
                targets[field_path] = fields_or_init_kwargs(field_type)
                _target_options(parser, targets, field_path)
        else:
            cli_arg = cliarg_from_annotations(field.annotations)
            env_value = os.getenv(cli_arg.env) if cli_arg and cli_arg.env else None
            value = getattr(args, name, env_value if env_value is not None else MISSING)
            if is_structured_model(field_type):
                nested = _target_options(parser, targets, field_path, args)
                if nested:
                    result[field.name] = nested
            elif value is not MISSING:
                result[field.name] = value
    return result


def _bootstrap(args, config, path, fields_by_path, active_paths, cache, targets, help_requested):
    fields = fields_by_path[path]
    positional = next(
        (field.name for field in fields if (cliarg_from_annotations(field.annotations) or CliArg()).pos), None
    )
    if path in active_paths and positional is not None:
        raise TypeError(
            f"{'.'.join((*path, positional))}: positional arguments are not supported with kwargs_for relations"
        )
    dependents = {field.kwargs_relation.name: [] for field in fields if field.kwargs_relation is not None}
    for field in fields:
        if field.kwargs_relation is not None:
            dependents[field.kwargs_relation.name].append(field)
    for field in fields:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        cli_arg = cliarg_from_annotations(field.annotations)
        value = config.get(field.name, MISSING)
        env_value = os.getenv(cli_arg.env) if cli_arg and cli_arg.env else None
        value = getattr(args, name, env_value if env_value is not None else value)
        if field.name in dependents:
            if value is MISSING:
                if field.default is MISSING and field.default_factory is MISSING:
                    if help_requested:
                        continue
                    raise TypeError(
                        f"{'.'.join((*path, dependents[field.name][0].name))}: missing selector {field.name!r}"
                    )
                value = deepcopy(field.default) if field.default is not MISSING else field.default_factory()
            try:
                target = from_dict_value(value, field.annotation, type(value), name)
            except (AttributeError, ImportError, ValueError) as error:
                raise TypeError(f"{name}: {error}") from error
            try:
                selected = selected_target_fields(target)
            except TypeError as error:
                raise TypeError(f"{'.'.join((*path, dependents[field.name][0].name))}: {error}") from error
            cache[field_path] = target
            for dependent in dependents[field.name]:
                targets[(*path, dependent.name)] = selected
        elif field_path in active_paths:
            field_type = effective_type(field.annotation, name)
            nested = dict(value) if isinstance(value, Mapping) else {}
            child_fields = fields_by_path[field_path]
            complete = all(
                child.name in nested or hasattr(args, ".".join((*field_path, child.name))) for child in child_fields
            )
            if not complete and (field.default is not MISSING or field.default_factory is not MISSING):
                default = deepcopy(field.default) if field.default is not MISSING else field.default_factory()
                cache[field_path] = default
                projected = to_kwargs(field_type, default)
                nested = _merge(projected, nested)
                for child in child_fields:
                    if child.name in projected:
                        cache[(*field_path, child.name)] = deepcopy(projected[child.name])
            _bootstrap(args, nested, field_path, fields_by_path, active_paths, cache, targets, help_requested)


def _from_cli_args(clazz, args, config=None, prefix="", cache=None, targets=None, fields_by_path=None):
    config = {} if config is None else config
    cache = {} if cache is None else cache
    targets = {} if targets is None else targets
    construct_args = {}
    pydantic_owner = is_pydantic_model(clazz)
    path = tuple(prefix.split(".")) if prefix else ()
    fields = fields_by_path[path] if fields_by_path is not None else fields_or_init_kwargs(clazz)
    for f in fields:
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

        field_path = (*path, f.name)
        if field_path in targets:
            values = {}
            for source in (config_value, env_value, cli_value):
                if source is not MISSING and source is not None:
                    values = _merge(values, from_dict_value(source, dict[str, Any], type(source), name))
            values = _merge(values, _target_options(None, targets, field_path, args))
            if any(parameter.name not in values for parameter in targets[field_path]):
                if field_path not in cache:
                    cache[field_path] = (
                        deepcopy(f.default)
                        if f.default is not MISSING
                        else f.default_factory()
                        if f.default_factory is not MISSING
                        else {}
                    )
                values = {**cache[field_path], **values}
            parameter_names = {parameter.name for parameter in targets[field_path]}
            unknown = next((key for key in values if key not in parameter_names), None)
            if unknown is not None:
                raise TypeError(f"{name}.{unknown}: unknown target parameter")
            converted = {}
            for parameter in targets[field_path]:
                if parameter.name in values:
                    value = values[parameter.name]
                    converted[parameter.name] = from_dict_value(
                        value, parameter.annotation or type(value), type(value), f"{name}.{parameter.name}"
                    )
                elif parameter.default is MISSING:
                    raise TypeError(f"{name}.{parameter.name}: missing required target parameter")
            construct_args[f.name] = converted
        elif is_structured_model(field_type):
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
            if field_path in cache and cache[field_path] is not None:
                nested_config = _merge(to_kwargs(field_type, cache[field_path]), nested_config)
            if (
                value is MISSING
                and not has_nested_source(field_type, args, nested_config, name)
                and not any(target_path[: len(field_path)] == field_path for target_path in targets)
                and (not is_dataclass(clazz) or has_default_value(f))
            ):
                continue
            if value is MISSING and is_dataclass(clazz) and not has_default_value(f):
                error_exit(f"--{name} not provided (default value DNE)", 3)
            construct_args[f.name] = _from_cli_args(
                field_type, args, nested_config, name, cache, targets, fields_by_path
            )
        else:
            value = config_value
            if env_value is not None:
                value = env_value
            if cli_value is not MISSING:
                value = cli_value
            if field_path in cache and any(item.kwargs_relation is f for item in fields):
                construct_args[f.name] = cache[field_path]
            elif value is not MISSING:
                construct_args[f.name] = (
                    value if pydantic_owner else from_dict_value(value, annotation, type(value), name)
                )
            elif (is_dataclass(clazz) or not is_structured_model(clazz)) and not has_default_value(f):
                error_exit(f"--{name} not provided (default value DNE)", 3)
    if pydantic_owner:
        values = deepcopy(config)
        values.update(construct_args)
        construct_args = values
    return (
        clazz.model_validate(construct_args)
        if pydantic_owner
        else clazz(**construct_args)
        if inspect.isclass(clazz)
        else construct_args
    )


def from_direct_cli_args(command_args: list[FieldSpec], args, config: dict | None = None) -> dict:
    config = {} if config is None else config
    result = {}
    for command_arg in command_args:
        name = command_arg.name
        annotation = command_arg.annotation
        cli_arg = cliarg_from_annotations(command_arg.annotations)
        value = config.get(name, MISSING)
        env_value = os.getenv(cli_arg.env) if cli_arg and cli_arg.env else None
        if env_value is not None:
            value = env_value
        if hasattr(args, name):
            value = getattr(args, name)
        elif hasattr(args, f"{name}_pos"):
            value = getattr(args, f"{name}_pos")

        if value is not MISSING:
            result[name] = from_dict_value(value, annotation, type(value), name)
        elif command_arg.default is MISSING:
            error_exit(f"--{name} not provided (default value DNE)", 3)
    return result


def cli(
    cmd_or_cmds: Callable[..., Any] | dict[Callable[..., Any], str], pos_arg_config: bool = False, **argsparse_kwargs
):
    argsparse_kwargs.setdefault("argument_default", argparse.SUPPRESS)
    argsparse_kwargs["add_help"] = False
    parser = argparse.ArgumentParser(**argsparse_kwargs)
    parsers = [parser]
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
            command_parser = subparsers.add_parser(
                cmd_name,
                help=desc,
                argument_default=argparse.SUPPRESS,
                add_help=False,
                conflict_handler=argsparse_kwargs.get("conflict_handler", "error"),
            )
            parsers.append(command_parser)
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
        if not is_structured_model(command_type) and not (
            inspect.isclass(command_type)
            and command_type.__module__ not in ("builtins", "collections.abc")
            and enum_type(command_type) is None
            and _contains_relation(command_type)
        ):
            command_type = None
        metadata_dest = "_msup_command"
        metadata_fields = fields_or_init_kwargs(command_type) if command_type is not None else command_fields
        while metadata_dest in {field.name for field in metadata_fields}:
            metadata_dest = f"_{metadata_dest}"
        setattr(command_parser, "_msup_fields", {})
        command_parser.set_defaults(
            **{metadata_dest: (metadata_marker, cmd_fn, command_type, command_fields, command_parser)}
        )
        if command_type is not None:
            _add_args(command_parser, command_type, pos_arg_config=pos_arg_config, fields=metadata_fields)
        elif command_fields:
            add_direct_args(command_parser, command_fields, pos_arg_config=pos_arg_config)

    raw_args = sys.argv[1:]
    args, _ = parser.parse_known_args(raw_args)
    command = None
    for value in vars(args).values():
        if isinstance(value, tuple) and value and value[0] is metadata_marker:
            command = value
            break
    cache = {}
    targets = {}
    if command is not None:
        _, cmd_fn, command_type, command_fields, command_parser = command
        config = _config_values(args)
        fields_by_path = getattr(command_parser, "_msup_fields")
        relation_paths = {
            path
            for path, fields in fields_by_path.items()
            if any(field.kwargs_relation is not None for field in fields)
        }
        if relation_paths:
            if pos_arg_config:
                raise TypeError("pos_arg_config is not supported with kwargs_for relations")
            active_paths = relation_paths | {
                relation_path[:index] for relation_path in relation_paths for index in range(1, len(relation_path) + 1)
            }
            _bootstrap(
                args,
                config,
                (),
                fields_by_path,
                active_paths,
                cache,
                targets,
                "--help" in raw_args or "-h" in raw_args,
            )
            for path in list(targets):
                _target_options(command_parser, targets, path)
    for command_parser in parsers:
        command_parser.add_argument("-h", "--help", action="help", help="show this help message and exit")
    args = _parse_args(parser)
    if command is not None:
        if command_type is not None:
            cmd_fn(
                _from_cli_args(command_type, args, config, cache=cache, targets=targets, fields_by_path=fields_by_path)
            )
        elif targets:
            cmd_fn(**_from_cli_args(cmd_fn, args, config, cache=cache, targets=targets, fields_by_path=fields_by_path))
        else:
            cmd_fn(**from_direct_cli_args(command_fields, args, config))
    else:
        parser.print_help()
