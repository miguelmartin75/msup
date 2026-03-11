import os
import sys
import inspect
import argparse
from dataclasses import dataclass, field, is_dataclass, fields, MISSING
from collections.abc import Callable as Callable2

from msup.base import has_default_value, is_optional, _from_value, to_json, to_kwargs
from typing import Optional, List, Dict, Union, TypeVar, get_origin, get_args, Callable, get_type_hints, Any

T = TypeVar('T')
_UNSET = object()

def cli(cmd_or_cmds: Callable[[T], Any] | dict[Callable[[T], Any], str], **argsparse_kwargs): ...
def cliarg(help: str = "", short: str | list[str] | None = None, env: str | None = None, pos: bool = False, opt: bool = True, **kwargs): ...

def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ('y', 'yes', 'on', '1', 'true', 't'):
        return True
    elif value in ('n', 'no', 'off', '0', 'false', 'f'):
        return False
    else:
        raise ValueError("Invalid truth value %r" % value)

def error_exit(msg: str, code: int = 1):
    print(f"[ERROR]: {msg}", file=sys.stderr)
    sys.exit(code)

def _get_first_arg(func):
    hints = get_type_hints(func)
    result = None
    for name, p in inspect.signature(func).parameters.items():
        if name in ("self", "cls"):
            continue
        result = hints.get(name)
        break
    if not is_dataclass(result):
        raise TypeError(f"First argument for {getattr(func, '__name__', func)} is not a dataclass: {result}")
    return result

def _get_env_default_value(f):
    env_name = f.metadata.get("env")
    env_value = os.getenv(env_name) if env_name else None
    if env_value:
        return _from_value(env_value, f.type, str, f.name)
    return _UNSET

def _get_cli_value(args, arg_name: str):
    value = getattr(args, arg_name, _UNSET)
    if value is _UNSET and hasattr(args, arg_name + "_pos"):
        pos_value = getattr(args, arg_name + "_pos")
        if pos_value is not _UNSET:
            return pos_value
    return value

def _from_cli_args(clazz: type, args, prefix: str = "", args_value: Any = _UNSET):
    assert is_dataclass(clazz), f"{clazz} is not a dataclass"

    if args_value is _UNSET:
        root_args_value = getattr(args, "args", _UNSET)
        args_value = _from_value(root_args_value, clazz, str, "") if prefix == "" and root_args_value is not _UNSET else None

    construct_args = to_kwargs(clazz, args_value) if args_value is not None else {}
    for f in fields(clazz):
        arg_name = prefix + "." + f.name if prefix else f.name
        value = _get_cli_value(args, arg_name)
        env_default = _get_env_default_value(f)
        if is_dataclass(f.type):
            if value is not _UNSET:
                if not isinstance(value, str):
                    error_exit(f"expected string for --{arg_name}, got {type(value)} ({value=})", 2)

                sub_args_value = _from_value(
                    value,
                    f.type,
                    str,
                    f.name,
                )
            else:
                sub_args_value = construct_args.get(f.name, env_default)

            sub = _from_cli_args(f.type, args, prefix=arg_name, args_value=sub_args_value)
            construct_args[f.name] = sub
        elif get_origin(f.type) is dict or f.type is dict:
            if value is not _UNSET:
                if not isinstance(value, str):
                    error_exit(f"expected string for --{arg_name}, got {type(value)} ({value=})", 2)
                sub = _from_value(
                    value,
                    f.type,
                    str,
                    f.name,
                )
                construct_args[f.name] = sub
            elif f.name in construct_args:
                continue
            elif env_default is not _UNSET:
                construct_args[f.name] = env_default
            elif has_default_value(f):
                continue
            else:
                error_exit(f"--{arg_name} not provided (default value DNE)", 3)
        elif f.type is bool:
            if value is not _UNSET:
                if isinstance(value, bool):
                    construct_args[f.name] = value
                else:
                    if not isinstance(value, str):
                        error_exit(f"expected string for --{arg_name}, got {type(value)} ({value=})", 2)

                    if value.lower() not in ("0", "false", "1", "true"):
                        error_exit(f"expected one of: {0, False, 1, True} as a bool value for --{arg_name}, got: {value}")

                    construct_args[f.name] = value.lower() in ("1", "true")
            elif f.name in construct_args:
                continue
            elif env_default is not _UNSET:
                construct_args[f.name] = env_default
            elif has_default_value(f):
                continue
            elif is_optional(f.type):
                construct_args[f.name] = None
            else:
                error_exit(f"--{arg_name} not provided (default value DNE)", 3)
        else:
            if value is not _UNSET:
                construct_args[f.name] = _from_value(
                    value,
                    f.type,
                    type(value),
                    field_name=f.name,
                )
            elif f.name in construct_args:
                continue
            elif env_default is not _UNSET:
                construct_args[f.name] = env_default
            elif has_default_value(f):
                continue
            elif is_optional(f.type):
                construct_args[f.name] = None
            else:
                error_exit(f"--{arg_name} not provided (default value DNE)", 3)

    return clazz(**construct_args)

def _get_cli_arg_type(x: type) -> type:
    if is_dataclass(x):
        return str
    elif is_optional(x):
        return _get_cli_arg_type(next(arg for arg in get_args(x) if arg is not type(None)))
    elif get_origin(x) is list:
        return _get_cli_arg_type(get_args(x)[0])
    elif get_origin(x) is dict:
        return str
    elif get_origin(x) is Callable2 or x is Callable2:
        return str
    return x

def to_bool(s: str) -> bool:
    return bool(strtobool(s))

def _add_args(parser, cmd_type: type, prefix: str = "", short_prefix: str | None = None, pos_arg_config: bool = False, force_no_default: bool = False):
    assert is_dataclass(cmd_type), f"{cmd_type} is not a dataclass"
    if prefix == "":
        if pos_arg_config:
            parser.add_argument(
                "args",
                nargs="?",
                type=_get_cli_arg_type(cmd_type),
                help=f"configuration for {cmd_type.__name__}",
                default=_UNSET,
            )
        parser.add_argument(
            "--Args",
            f"--{cmd_type.__name__}",
            dest="args",
            type=_get_cli_arg_type(cmd_type),
            help=f"configuration for {cmd_type.__name__}",
            required=False,
            default=_UNSET,
        )

    for f in fields(cmd_type):
        field_name = f.name
        name = prefix + "." + field_name if prefix else field_name
        req = False
        o_or_field_type = get_origin(f.type) or f.type
        default_value = f.default if f.default is not MISSING and (not force_no_default or f.type is bool) else None
        default_help = f"Default: {default_value}" if default_value else ""
        env_default_value = _get_env_default_value(f)
        if env_default_value is not _UNSET:
            default_value = env_default_value
            env_name = f.metadata.get("env")
            default_help = f"Default (using env: ${{{env_name}}}): {default_value}"

        help = f.metadata.get("help") + ". " + default_help if f.metadata.get("help") else default_help
        args_to_add = []

        if f.metadata.get("pos"):
            args_to_add.append(([name + "_pos"], {"nargs": "?"}))

        if f.metadata.get("opt") or len(args_to_add) == 0:
            args = []
            if f.metadata.get("short"):
                for s in f.metadata["short"]:
                    if s is not None:
                        assert not s.startswith("--")
                        arg_name = "-" + s if not s.startswith("-") else s
                        prefix_to_use = short_prefix if short_prefix is not None else prefix
                        arg_name = "-" + prefix_to_use + "." + arg_name[1:] if prefix_to_use else arg_name
                        if arg_name != "-":
                            args.append(arg_name)
            args.append("--" + name)
            args_to_add.append((args, {"required": req if not f.metadata.get("pos") else False, "dest": name}))

        for i, (args, kwargs) in enumerate(args_to_add):
            if is_dataclass(f.type):
                parser.add_argument(
                    *args,
                    **kwargs,
                    type=_get_cli_arg_type(f.type),
                    help=help,
                    default=_UNSET,
                )
                _add_args(
                    parser,
                    f.type,
                    prefix=name,
                    short_prefix=f.metadata.get("short", [None])[0],
                    force_no_default=True,
                )
            elif get_origin(f.type) in (list,):
                kwargs["nargs"] = "*"
                parser.add_argument(
                    *args,
                    **kwargs,
                    type=_get_cli_arg_type(f.type),
                    help=help,
                    default=_UNSET,
                )
            elif o_or_field_type in (dict,):
                parser.add_argument(
                    *args,
                    **kwargs,
                    type=str,
                    help=help,
                    default=_UNSET,
                )
            elif f.type in (bool,):
                if "nargs" not in kwargs:
                    kwargs["nargs"] = "?"
                parser.add_argument(
                    *args,
                    **kwargs,
                    const=not default_value,
                    type=to_bool,
                    metavar="{0|1,true|false,yes|no}",
                    default=_UNSET,
                )
            elif get_origin(f.type) is Callable2:
                parser.add_argument(
                    *args,
                    **kwargs,
                    type=str,
                    help=help,
                    default=_UNSET,
                )
            else:
                parser.add_argument(
                    *args,
                    **kwargs,
                    type=_get_cli_arg_type(f.type),
                    help=help,
                    default=_UNSET,
                )

def cliarg(help: str = "", short: str | list[str] | None = None, env: str | None = None, pos: bool = False, opt: bool = True, **kwargs):
    return field(metadata={"help": help, "short": short if isinstance(short, list) else [short], "env": env, "pos": pos, "opt": opt}, **kwargs)

def cli(cmd_or_cmds: Callable[[T], Any] | dict[Callable[[T], Any], str], pos_arg_config: bool = False, **argsparse_kwargs):
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
            _add_args(p, cmd_type, pos_arg_config=pos_arg_config)

        args = parser.parse_args()
        if hasattr(args, 'func'):
            args.func(_from_cli_args(args.cmd_type, args))
        else:
            parser.print_help()
    else:
        _add_args(parser, _get_first_arg(cmd_or_cmds), pos_arg_config=pos_arg_config)
        args = parser.parse_args()
        cmd_or_cmds(_from_cli_args(_get_first_arg(cmd_or_cmds), args))


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
