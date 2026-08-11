import argparse
import inspect
import os
import sys
from collections.abc import Callable as Callable2, Mapping
from copy import deepcopy
from dataclasses import MISSING, dataclass, is_dataclass
from typing import Any, Callable, cast, get_args

from msup.base import (
    FieldSpec,
    Metadata,
    _construct_owner,
    _kwargs_from_fields,
    annotation_origin,
    enum_type,
    effective_type,
    fields_or_init_kwargs,
    from_dict_value,
    get_collection_args,
    has_default_value,
    is_structured_model,
    metadata_from_annotations,
    selected_target_fields,
    to_kwargs,
)


_RAW_MATERIALIZED = "\0materialized"


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


def _contains_relation(owner: type | Callable[..., Any]) -> bool:
    if (
        owner is Any
        or (not inspect.isclass(owner) and not (inspect.isfunction(owner) or inspect.ismethod(owner)))
        or owner.__module__ in ("builtins", "collections.abc")
        or enum_type(owner) is not None
    ):
        return False
    for field in fields_or_init_kwargs(owner):
        field_type = effective_type(field.annotation, field.name)
        if field.kwargs_relation is not None or (inspect.isclass(field_type) and _contains_relation(field_type)):
            return True
    return False


def _is_dynamic_owner(owner) -> bool:
    return inspect.isclass(owner) and (is_structured_model(owner) or _contains_relation(owner))


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


def argument_type(annotation: Any, field_name: str) -> type | Callable[[str], Any]:
    annotation = effective_type(annotation, field_name)
    origin = annotation_origin(annotation)
    if annotation is Any or _is_dynamic_owner(annotation) or origin in (dict, Callable2):
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
    elif enum_type(annotation) is not None:
        result = enum_argument_type(annotation, field_name)
    else:
        raise TypeError(f"{field_name}: unsupported CLI annotation: {annotation}")
    return result


def _add_argument(parser, args, kwargs, annotation, field_name, help_text, positional):
    field_type = effective_type(annotation, field_name)
    origin = annotation_origin(field_type)
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
    elif (enum_class := enum_type(field_type)) is not None:
        kwargs["type"] = enum_argument_type(field_type, field_name)
        kwargs["metavar"] = "{" + ",".join(str(member.value) for member in enum_class) + "}"
    else:
        kwargs["type"] = argument_type(field_type, field_name)
    parser.add_argument(*args, **kwargs)


def _field_help(field, name: str, force_no_default: bool = False) -> tuple[CliArg, str]:
    cli_arg = cliarg_from_annotations(field.annotations) or CliArg()
    help_text = cli_arg.help
    default_help = ""
    if not cli_arg.secret and field.default is not MISSING and (not force_no_default or field.annotation is bool):
        default_help = f"Default: {field.default}"
    env_value = os.getenv(cli_arg.env) if cli_arg.env else None
    if env_value is not None and not cli_arg.secret:
        field_type = effective_type(field.annotation, name)
        default_value = (
            env_value
            if annotation_origin(field_type) is Callable2
            or (inspect.isclass(field_type) and _contains_relation(field_type))
            else from_dict_value(env_value, field.annotation, str, name)
        )
        default_help = f"Default (using env: ${{{cli_arg.env}}}): {default_value}"
    if default_help:
        help_text = f"{help_text}. {default_help}" if help_text else default_help
    return cli_arg, help_text


def _add_fields(
    parser, command_fields, prefix: str = "", short_prefix: str | None = None, force_no_default: bool = False
):
    for field_index, f in enumerate(command_fields):
        field_name = f.name
        name = f"{prefix}.{field_name}" if prefix else field_name
        annotation = f.annotation
        cli_arg, help_text = _field_help(f, name, force_no_default)

        positional = cli_arg.pos
        optional = cli_arg.opt
        collection_origin = annotation_origin(effective_type(annotation, name))
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
                short = cli_arg.short.removeprefix("-")
                option_names.insert(0, f"-{short_prefix or prefix}.{short}" if prefix else f"-{short}")
            _add_argument(parser, option_names, {"dest": name}, annotation, name, help_text, positional=False)

        field_type = effective_type(annotation, name)
        if _is_dynamic_owner(field_type):
            _add_args(parser, field_type, prefix=name, short_prefix=cli_arg.short, force_no_default=True)


def _add_args(
    parser,
    cmd_type: type,
    prefix: str = "",
    short_prefix: str | None = None,
    pos_arg_config: bool = False,
    force_no_default: bool = False,
):
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
    _add_fields(parser, fields_or_init_kwargs(cmd_type), prefix, short_prefix, force_no_default)


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

    _add_fields(parser, command_args)


def _config_values(args) -> dict:
    raw = getattr(args, "args", None)
    if raw is None:
        result = {}
    else:
        result = from_dict_value(raw, dict[str, Any], str, "args")
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


def _field_sources(field: FieldSpec, args, config: Mapping[str, Any], name: str) -> list[Any]:
    result = []
    if field.name in config:
        result.append(config[field.name])
    cli_arg = cliarg_from_annotations(field.annotations)
    env_value = os.getenv(cli_arg.env) if cli_arg and cli_arg.env else None
    if env_value is not None:
        result.append(env_value)
    cli_value = getattr(args, name, getattr(args, f"{name}_pos", MISSING))
    if cli_value is not MISSING:
        result.append(cli_value)
    return result


def _has_descendant_source(owner, args, config, path) -> bool:
    return any(
        _field_sources(field, args, config, ".".join((*path, field.name)))
        or (
            inspect.isclass(field_type := effective_type(field.annotation, ".".join((*path, field.name))))
            and _contains_relation(field_type)
            and _has_descendant_source(field_type, args, {}, (*path, field.name))
        )
        for field in fields_or_init_kwargs(owner)
    )


def has_nested_source(clazz: type, args, config: dict, prefix: str) -> bool:
    """Whether config, environment, or CLI supplies a value below ``prefix``."""
    return _has_descendant_source(clazz, args, config, tuple(prefix.split(".")) if prefix else ())


def _from_cli_args(clazz: type, args, config: dict | None = None, prefix: str = ""):
    config = {} if config is None else config
    construct_args = {}
    for f in fields_or_init_kwargs(clazz):
        name = f"{prefix}.{f.name}" if prefix else f.name
        field_type = effective_type(f.annotation, name)
        sources = _field_sources(f, args, config, name)
        value = sources[-1] if sources else MISSING

        if is_structured_model(field_type):
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
            if value is MISSING and is_dataclass(clazz) and not has_default_value(f):
                error_exit(f"--{name} not provided (default value DNE)", 3)
            construct_args[f.name] = _from_cli_args(field_type, args, nested_config, name)
        else:
            if value is not MISSING:
                construct_args[f.name] = from_dict_value(value, f.annotation, type(value), name)
            elif is_dataclass(clazz) and not has_default_value(f):
                error_exit(f"--{name} not provided (default value DNE)", 3)
    return clazz(**construct_args)


def from_direct_cli_args(command_args: list[FieldSpec], args, config: dict | None = None) -> dict:
    config = {} if config is None else config
    result = {}
    for command_arg in command_args:
        name = command_arg.name
        sources = _field_sources(command_arg, args, config, name)
        value = sources[-1] if sources else MISSING

        if value is not MISSING:
            result[name] = from_dict_value(value, command_arg.annotation, type(value), name)
        elif command_arg.default is MISSING:
            error_exit(f"--{name} not provided (default value DNE)", 3)
    return result


def _mapping_value(value: Any, name: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        result = dict(value)
    elif _is_dynamic_owner(type(value)):
        result = to_kwargs(type(value), value)
    else:
        result = from_dict_value(value, dict[str, Any], type(value), name)
    return result


def _merge_mappings(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), Mapping) and isinstance(value, Mapping):
            result[key] = _merge_mappings(cast(Mapping[str, Any], result[key]), value)
        else:
            result[key] = value
    return result


def _source_values(sources, name: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source in sources:
        if source is None:
            result = {}
        else:
            value = _mapping_value(source, name)
            result = value if _is_dynamic_owner(type(source)) else _merge_mappings(result, value)
    return result


def _source_tree(owner, args, config, path):
    fields = fields_or_init_kwargs(owner)
    if is_structured_model(owner) and not is_dataclass(owner):
        for field in fields:
            if field.kwargs_relation is not None or any(item.kwargs_relation is field for item in fields):
                alias = cast(Any, owner).model_fields[field.name].validation_alias
                if isinstance(alias, str) and field.name not in config and alias in config:
                    config[field.name] = config[alias]
    result = dict(config)
    complete = True
    for field in fields:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        sources = _field_sources(field, args, config, name)
        field_type = effective_type(field.annotation, name)
        if _is_dynamic_owner(field_type):
            values = _source_values(sources, name)
            nested, nested_complete = _source_tree(field_type, args, values, field_path)
            if sources or nested:
                result[field.name] = nested
            complete = complete and nested_complete
        elif sources:
            result[field.name] = sources[-1]
        complete = complete and field.name in result
    return result, complete


def _default_value(field: FieldSpec):
    result = MISSING
    if field.default is not MISSING:
        result = deepcopy(field.default)
    elif field.default_factory is not MISSING:
        result = field.default_factory()
    return result


def _bootstrap_owner(owner, args, config, path, raw_trees, targets, target_fields):
    fields = fields_or_init_kwargs(owner)
    pydantic_owner = is_structured_model(owner) and not is_dataclass(owner)
    result = {key: value for key, value in config.items() if key != _RAW_MATERIALIZED} if pydantic_owner else {}
    if materialized := config.get(_RAW_MATERIALIZED):
        result[_RAW_MATERIALIZED] = materialized
    if pydantic_owner:
        config = dict(config)
        for field in fields:
            if field.kwargs_relation is not None or any(item.kwargs_relation is field for item in fields):
                alias = cast(Any, owner).model_fields[field.name].validation_alias
                if isinstance(alias, str) and field.name not in config and alias in config:
                    config[field.name] = config[alias]
    if _contains_relation(owner):
        raw_trees[path] = result
    for field in fields:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        field_type = effective_type(field.annotation, name)
        sources = _field_sources(field, args, config, name)
        dependent = next((item for item in fields if item.kwargs_relation is field), None)
        if field.kwargs_relation is not None:
            values: dict[str, Any] = {}
            for source in sources:
                values = _merge_mappings(values, _mapping_value(source, name))
            if sources:
                result[field.name] = values
        elif dependent is not None:
            value = sources[-1] if sources else _default_value(field)
            if value is not MISSING:
                target = from_dict_value(value, field.annotation, type(value), name)
                targets[field_path] = target
                try:
                    target_fields[(*path, dependent.name)] = selected_target_fields(target)
                except TypeError as error:
                    raise TypeError(f"{'.'.join((*path, dependent.name))}: {error}") from error
                result[field.name] = value
        elif _is_dynamic_owner(field_type):
            nested_config: dict[str, Any] = {}
            contains_relation = _contains_relation(field_type)
            authoritative = any(_is_dynamic_owner(type(source)) for source in sources)
            source_values, complete = _source_tree(field_type, args, _source_values(sources, name), field_path)
            default = _default_value(field) if contains_relation and not authoritative and not complete else MISSING
            source_present = bool(sources) or (default is not MISSING and default is not None)
            explicit_none = bool(sources) and sources[-1] is None
            if default is not MISSING and default is not None:
                nested_config = _mapping_value(default, name)
                nested_config[_RAW_MATERIALIZED] = {child.name for child in fields_or_init_kwargs(field_type)}
            for source in sources:
                if source is None:
                    nested_config = {}
                elif _is_dynamic_owner(type(source)):
                    nested_config = _mapping_value(source, name)
                    nested_config[_RAW_MATERIALIZED] = {child.name for child in fields_or_init_kwargs(field_type)}
                else:
                    nested_config = _merge_mappings(nested_config, _mapping_value(source, name))
            has_descendant = _has_descendant_source(field_type, args, nested_config, field_path)
            if explicit_none or (default is None and not source_present and not has_descendant):
                result[field.name] = None
            elif source_present or has_descendant:
                result[field.name] = _bootstrap_owner(
                    field_type, args, nested_config, field_path, raw_trees, targets, target_fields
                )
        elif sources:
            result[field.name] = sources[-1]
    return result


def _add_target_args(parser, fields, path) -> None:
    for field in fields:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        cli_arg = cliarg_from_annotations(field.annotations) or CliArg()
        if cli_arg.short:
            raise TypeError(f"{name}: selected target parameters cannot define short options")
        if cli_arg.pos:
            raise TypeError(f"{name}: selected target parameters cannot be positional")
        _, help_text = _field_help(field, name)
        _add_argument(parser, [f"--{name}"], {"dest": name}, field.annotation, name, help_text, positional=False)
        field_type = effective_type(field.annotation, name)
        if _is_dynamic_owner(field_type):
            if _contains_relation(field_type):
                raise TypeError(f"{name}: selected target parameters cannot contain kwargs_for relations")
            _add_target_args(parser, fields_or_init_kwargs(field_type), field_path)


def _target_values(fields, args, path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        sources = _field_sources(field, args, {}, name)
        if is_structured_model(field_type := effective_type(field.annotation, name)):
            values = _source_values(sources, name)
            nested = _target_values(fields_or_init_kwargs(field_type), args, field_path)
            if values or nested or sources:
                result[field.name] = _merge_mappings(values, nested)
        elif sources:
            result[field.name] = sources[-1]
    return result


def _construct_dynamic_owner(owner, path, raw_trees, targets, target_fields, args):
    raw = raw_trees[path]
    pydantic_owner = is_structured_model(owner) and not is_dataclass(owner)
    result = {key: value for key, value in raw.items() if key != _RAW_MATERIALIZED} if pydantic_owner else {}
    fields = fields_or_init_kwargs(owner)
    for field in fields:
        field_path = (*path, field.name)
        name = ".".join(field_path)
        field_type = effective_type(field.annotation, name)
        dependent = next((item for item in fields if item.kwargs_relation is field), None)
        if field.kwargs_relation is not None:
            if field_path not in target_fields:
                raise TypeError(f"{name}: missing selector {field.kwargs_relation.name!r}")
            parameters = target_fields[field_path]
            supplied = raw.get(field.name, {})
            if not isinstance(supplied, Mapping):
                raise TypeError(f"{name}: expected a mapping, got {type(supplied)}")
            values = _merge_mappings(supplied, _target_values(parameters, args, field_path))
            if field.name not in raw.get(_RAW_MATERIALIZED, ()) and any(
                parameter.name not in values for parameter in parameters
            ):
                default = _default_value(field)
                if default is not MISSING:
                    values = _merge_mappings(_mapping_value(default, name), values)
            result[field.name] = _kwargs_from_fields(parameters, values, name)
        elif dependent is not None:
            if field_path in targets:
                result[field.name] = targets[field_path]
            elif field.name in raw:
                value = raw[field.name]
                result[field.name] = from_dict_value(value, field.annotation, type(value), name)
        elif field_path in raw_trees:
            result[field.name] = _construct_dynamic_owner(
                field_type, field_path, raw_trees, targets, target_fields, args
            )
        elif field.name in raw and not pydantic_owner:
            value = raw[field.name]
            result[field.name] = from_dict_value(value, field.annotation, type(value), name)
        elif not pydantic_owner and not has_default_value(field):
            error_exit(f"--{name} not provided (default value DNE)", 3)
    return _construct_owner(owner, result) if inspect.isclass(owner) else result


def _validate_dynamic_layout(owner, path=()) -> None:
    for field in fields_or_init_kwargs(owner):
        name = ".".join((*path, field.name))
        cli_arg = cliarg_from_annotations(field.annotations)
        if cli_arg and cli_arg.pos:
            raise TypeError(f"{name}: positional arguments are not supported with kwargs_for relations")
        field_type = effective_type(field.annotation, name)
        if _is_dynamic_owner(field_type):
            _validate_dynamic_layout(field_type, (*path, field.name))


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
        if not _is_dynamic_owner(command_type):
            command_type = None
        metadata_dest = "_msup_command"
        metadata_fields = fields_or_init_kwargs(command_type) if command_type is not None else command_fields
        while metadata_dest in {field.name for field in metadata_fields}:
            metadata_dest = f"_{metadata_dest}"
        command_parser.set_defaults(
            **{metadata_dest: (metadata_marker, cmd_fn, command_type, command_fields, command_parser)}
        )
        if command_type is not None:
            _add_args(command_parser, command_type, pos_arg_config=pos_arg_config)
        elif command_fields:
            add_direct_args(command_parser, command_fields, pos_arg_config=pos_arg_config)

    raw_args = sys.argv[1:]
    bootstrap_args, _ = parser.parse_known_args(raw_args)
    command = None
    for value in vars(bootstrap_args).values():
        if isinstance(value, tuple) and value and value[0] is metadata_marker:
            command = value
            break
    dynamic = False
    if command is not None:
        command_type, command_fields = command[2:4]
        dynamic = _contains_relation(command_type if command_type is not None else command[1])
    for command_parser in parsers:
        command_parser.add_argument("-h", "--help", action="help", help="show this help message and exit")
    if dynamic and command is not None:
        command_type, command_fields, command_parser = command[2:]
        owner = command_type if command_type is not None else command[1]
        if pos_arg_config:
            raise TypeError("pos_arg_config is not supported with kwargs_for relations")
        _validate_dynamic_layout(owner)
        config = _config_values(bootstrap_args)
        raw_trees: dict[tuple[str, ...], dict[str, Any]] = {}
        targets: dict[tuple[str, ...], type | Callable[..., Any]] = {}
        target_fields: dict[tuple[str, ...], list[FieldSpec]] = {}
        _bootstrap_owner(owner, bootstrap_args, config, (), raw_trees, targets, target_fields)
        for path, fields in target_fields.items():
            _add_target_args(command_parser, fields, path)
        args = parser.parse_args(raw_args)
        value = _construct_dynamic_owner(owner, (), raw_trees, targets, target_fields, args)
        if command_type is not None:
            command[1](value)
        else:
            command[1](**value)
    if command is not None:
        if not dynamic:
            _, cmd_fn, command_type, command_fields, _ = command
            args = _parse_args(parser)
            config = _config_values(args)
            if command_type is not None:
                cmd_fn(_from_cli_args(command_type, args, config))
            else:
                cmd_fn(**from_direct_cli_args(command_fields, args, config))
    else:
        parser.parse_args(raw_args)
        parser.print_help()
