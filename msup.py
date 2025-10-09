import os
import argparse
import json
import inspect
from dataclasses import dataclass, asdict, is_dataclass, fields, MISSING, field
from types import UnionType
from typing import Optional, List, Dict, Union, TypeVar, get_origin, get_args, Callable, get_type_hints, Any

T = TypeVar('T')

def cliarg(help: str, short: str | list[str] | None = None, **kwargs):
    return field(metadata={"help": help, "short": short if isinstance(short, list) else [short]}, **kwargs)

def _to_dict_value(x: T, field_type: type):
    t = type(x)
    if t in (dict,):
        return {_to_dict_value(k, get_args(field_type)[0] or type(k)): _to_dict_value(v, get_args(field_type)[1] or type(v)) for k, v in x.items()}
    elif t in (list, List):
        return [_to_dict_value(xx, get_args(field_type)[0] or type(xx)) for xx in x]
    elif is_dataclass(t):
        return to_dict(x)
    elif field_type:
        return field_type(x)
    else:
        return x

def to_dict(x: T) -> dict:
    result = {}
    for f in fields(x):
        result[f.name] = _to_dict_value(x.__dict__[f.name], f.type)
    return result

def is_optional(x: type) -> bool:
    origin = get_origin(x)
    args = get_args(x)
    return origin is Optional or (origin in (Union, UnionType) and len(args) == 2 and type(None) in args)

def _is_compat(x1: type, x2: type) -> tuple[bool, type | None]:
    if is_dataclass(x1):
        convertible = is_dataclass(x2) or (get_origin(x2) or x2) in (dict,) or (get_origin(x2) or x2) in (str,)
        return convertible, x1
    else:
        xx1 = get_origin(x1) or x1
        xx2 = get_origin(x2) or x2
        assert xx2 not in (Union, UnionType), "pass a union as first parameter"

        if is_optional(x1):
            x1_args = get_args(x1)
            is_c, compat_type = _is_compat(x1_args[0], x2)
            return xx2 is type(None) or is_c, compat_type
        elif xx1 in (Union, UnionType):
            x1_args = get_args(x1)
            compat_types = []
            for arg in x1_args:
                if _is_compat(arg, concrete_type):
                    compat_types.append(arg)
            if len(compat_types) != 1:
                raise AssertionError(f"multiple matching types for {field_name}: {compat_types}")
            else:
                return True, compat_types[0]
        elif xx1 in (dict,):
            return xx2 in (dict,), xx1
        elif xx1 in (int, float, bool) and xx2 in (int, float, bool):
            return True, xx1
        else:
            return xx1 == xx2, xx1

def _from_value(
    x: T,
    field_type: type,
    concrete_type: type,
    field_name: str,
):
    is_compat, compat_type = _is_compat(field_type, concrete_type)
    if not is_compat:
        raise AssertionError(f"{field_name}: {field_type} cannot be converted to {concrete_type}")

    is_dc = is_dataclass(field_type)
    origin = get_origin(field_type) or field_type
    args = get_args(field_type)

    if is_dc:
        if concrete_type == field_type:
            return x
        elif concrete_type == str:
            assert isinstance(x, str)
            if x.startswith("{"):
                json_value = json.loads(x)
                return from_dict(field_type, json_value)
            elif x.endswith(".json"):
                assert os.path.exists(x), f"{x} does not exist"
                with open(x) as in_f:
                    json_value = json.load(in_f)
                    return from_dict(field_type, json_value)
            # TODO: support YAML
            # elif x.endswith(".yaml"):
            else:
                return eval(value)
        else:
            assert not isinstance(x, str)
            return from_dict(field_type, x)
    if x is None or origin in (int, float, str, bool):
        return x
    elif is_optional(field_type):
        return _from_value(x, args[0], type(x), field_name=field_name)
    elif origin in (Union, UnionType):
        return _from_value(x, compat_type, concrete_type, field_name=field_name)
    elif origin in (dict,):
        return {
            _from_value(
                k,
                type(k),
                type(k),
                field_name=f"{field_name}.key",
            ): _from_value(v, type(v), type(v), field_name=f"{field_name}.value")
            for k, v in x.items()
        }
    elif origin in (list, List,):
        return [
            _from_value(xx, type(xx), type(xx), field_name=f"{field_type}[{i}]")
            for i, xx in enumerate(x)
        ]
    else:
        raise AssertionError(f"unexpected type: {field_type} (origin={origin}, concrete_type={concrete_type}, args={args}, x={x})")

def from_dict(clazz: type, x: dict):
    assert is_dataclass(clazz), f"{cmd_type} is not a dataclass"
    construct_args = {}
    for f in fields(clazz):
        if f.name in x:
            construct_args[f.name] = _from_value(
                x[f.name],
                f.type,
                type(x[f.name]),
                field_name=f.name,
            )
        elif is_optional(f.type):
            construct_args[f.name] = None
    return clazz(**construct_args)

def identity_rename(x: str) -> str:
    return x

def _get_first_arg(func):
    hints = get_type_hints(func)
    result = None
    for name, p in inspect.signature(func).parameters.items():
        if name in ("self", "cls"):
            continue
        result = hints.get(name)
        break
    if not is_dataclass(result):
        raise TypeError(f"First argument for {getattr(fn, '__name__', fn)} is not a dataclass: {dtype}")
    return result

def from_cli_args(clazz: type, args, prefix: str = ""):
    assert is_dataclass(clazz), f"{cmd_type} is not a dataclass"

    construct_args = {}
    for f in fields(clazz):
        arg_name = prefix + "." + f.name if prefix else f.name
        value = getattr(args, arg_name)
        if is_dataclass(f.type):
            if value is not None:
                assert isinstance(value, str), f"{value.__class__}"
                sub = _from_value(
                    value,
                    f.type,
                    str,
                    f.name,
                )
                breakpoint()
                # NOTE: merge additional values
                for subf in fields(f.type):
                    subv = getattr(args, arg_name + "." + subf.name)
                    if subv:
                        breakpoint()
                        v = _from_value(
                            subv,
                            subf.type,
                            type(subv),
                            field_name=f.name,
                        )
                        setattr(sub, subf.name, subv)
            else:
                sub = from_cli_args(f.type, args, prefix=f.name)

            breakpoint()
            construct_args[f.name] = sub
        elif f.type is dict:
            assert isinstance(value, str), f"{value.__class__}"
            sub = _from_value(
                value,
                f.type,
                str,
                f.name,
            )
        else:
            if value is not None:
                construct_args[f.name] = _from_value(
                    value,
                    f.type,
                    type(value),
                    field_name=f.name,
                )
            elif is_optional(f.type):
                construct_args[f.name] = None
            elif not has_default_value(f):
                raise AssertionError(f"--{arg_name} not provided")

    return clazz(**construct_args)

def _get_cli_arg_type(x: type) -> type:
    if is_dataclass(x):
        return str
    elif is_optional(x):
        return get_args(x)[0]
    return x

#x in (Union, UnionType)
#is_optional(str | None)
#_get_cli_arg_type(str | None)

def has_default_value(f):
    return f.default is not MISSING or f.default_factory is not MISSING

def _add_args(parser, cmd_type: type, prefix: str = "", force_no_default: bool = False):
    assert is_dataclass(cmd_type), f"{cmd_type} is not a dataclass"
    for f in fields(cmd_type):
        field_name = f.name
        name = prefix + "." + field_name if prefix else field_name
        req = prefix == "" and not has_default_value(f)
        args = []
        if f.metadata.get("short"):
            for s in f.metadata["short"]:
                if s is not None:
                    assert not s.startswith("--")
                    args.append("-" + s if not s.startswith("-") else s)
        args.append("--" + name)

        o_or_field_type = get_origin(f.type) or f.type
        default_value = f.default if f.default is not MISSING and not force_no_default else None
        default_help = f"Default: {default_value}" if default_value else ""
        help = f.metadata.get("help") + ". " + default_help if f.metadata.get("help") else default_help

        if is_dataclass(f.type):
            parser.add_argument(
                *args,
                type=_get_cli_arg_type(f.type),
                help=help,
                required=False,
            )
            _add_args(
                parser,
                f.type,
                prefix=field_name,
                force_no_default=True,
            )
        elif f.type in (list,):
            parser.add_argument(
                *args,
                type=_get_cli_arg_type(f.type),
                help=help,
                nargs='+',
                required=False,
                default=f.default if f.default is not MISSING else None,
            )
        elif f.type is bool:
            # TODO
            pass
        elif o_or_field_type in (dict,):
            parser.add_argument(
                *args,
                type=str,
                help=help,
                required=req,
                default=f.default if f.default is not MISSING else None,
            )
        else:
            parser.add_argument(
                *args,
                type=_get_cli_arg_type(f.type),
                help=help,
                required=req,
                default=f.default if f.default is not MISSING else None,
            )

def cli(cmd_or_cmds: Callable[[T], Any] | dict[Callable[[T], Any], str], **argsparse_kwargs):
    parser = argparse.ArgumentParser(**argsparse_kwargs)
    if isinstance(cmd_or_cmds, dict):
        seen = set()

        subparsers = parser.add_subparsers(help='subcommand help')
        for cmd_fn, desc in cmd_or_cmds.items():
            cmd_name = cmd_fn.__name__
            assert cmd_name not in seen, f"{cmd_name} command occurs more than once"
            seen.add(cmd_name)

            cmd_type = _get_first_arg(cmd_fn)

            p = subparsers.add_parser(
                cmd_name,
                help=desc,
            )
            p.set_defaults(func=cmd_fn, cmd_type=cmd_type)
            _add_args(p, cmd_type)

        args = parser.parse_args()
        if hasattr(args, 'func'):
            args.func(from_cli_args(args.cmd_type, args))
        else:
            parser.print_help()
    else:
        _add_args(parser, _get_first_arg(cmd_or_cmds))
        args = parser.parse_args()
        cmd_or_cmds(from_cli_args(_get_first_arg(cmd_or_cmds), args))
