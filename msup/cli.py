import sys
import inspect
import argparse
from dataclasses import dataclass, field, is_dataclass, fields, MISSING
from collections.abc import Callable as Callable2

from msup.base import has_default_value, is_optional, _from_value, to_json
from typing import Optional, List, Dict, Union, TypeVar, get_origin, get_args, Callable, get_type_hints, Any

T = TypeVar('T')

def cli(cmd_or_cmds: Callable[[T], Any] | dict[Callable[[T], Any], str], **argsparse_kwargs): ...
def cliarg(help: str = "", short: str | list[str] | None = None, **kwargs): ...

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
        raise TypeError(f"First argument for {getattr(fn, '__name__', fn)} is not a dataclass: {dtype}")
    return result

def _from_cli_args(clazz: type, args, prefix: str = ""):
    assert is_dataclass(clazz), f"{cmd_type} is not a dataclass"

    construct_args = {}
    for f in fields(clazz):
        arg_name = prefix + "." + f.name if prefix else f.name
        value = getattr(args, arg_name)
        if is_dataclass(f.type):
            if value is not None:
                if not isinstance(value, str):
                    error_exit(f"expected string for --{arg_name}, got {type(value)} ({value=})", 2)

                sub = _from_value(
                    value,
                    f.type,
                    str,
                    f.name,
                )
                # NOTE: merge additional values
                for subf in fields(f.type):
                    subv = getattr(args, arg_name + "." + subf.name)
                    if subv:
                        v = _from_value(
                            subv,
                            subf.type,
                            type(subv),
                            field_name=f.name,
                        )
                        setattr(sub, subf.name, subv)
            else:
                sub = _from_cli_args(f.type, args, prefix=f.name)

            construct_args[f.name] = sub
        elif f.type is dict:
            if not isinstance(value, str):
                error_exit(f"expected string for --{arg_name}, got {type(value)} ({value=})", 2)
            sub = _from_value(
                value,
                f.type,
                str,
                f.name,
            )
        elif f.type is bool:
            if isinstance(value, bool):
                construct_args[f.name] = value
            else:
                if not isinstance(value, str):
                    error_exit(f"expected string for --{arg_name}, got {type(value)} ({value=})", 2)

                if value.lower() not in ("0", "false", "1", "true"):
                    error_exit(f"expected one of: {0, False, 1, True} as a bool value for --{arg_name}, got: {value}")

                construct_args[f.name] = value.lower() in ("1", "true")
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
                error_exit(f"--{arg_name} not provided (default value DNE)", 3)

    return clazz(**construct_args)

def _get_cli_arg_type(x: type) -> type:
    if is_dataclass(x):
        return str
    elif is_optional(x):
        return get_args(x)[0]
    elif get_origin(x) is list:
        return get_args(x)[0]
    elif get_origin(x) is dict:
        return str
    return x

def _add_args(parser, cmd_type: type, prefix: str = "", force_no_default: bool = False):
    assert is_dataclass(cmd_type), f"{cmd_type} is not a dataclass"
    if prefix == "":
        parser.add_argument(
            "args",
            nargs="?",
            type=_get_cli_arg_type(cmd_type),
            help=f"configuration for {cmd_type.__name__}",
        )
        parser.add_argument(
            "--Args",
            f"--{cmd_type.__name__}",
            dest="args",
            type=_get_cli_arg_type(cmd_type),
            help=f"configuration for {cmd_type.__name__}",
            required=False,
        )

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
        elif get_origin(f.type) in (list,):
            parser.add_argument(
                *args,
                type=_get_cli_arg_type(f.type),
                help=help,
                nargs='+',
                required=False,
                default=default_value,
            )
        elif o_or_field_type in (dict,):
            parser.add_argument(
                *args,
                type=str,
                help=help,
                required=req,
                default=default_value,
            )
        elif f.type in (bool,):
            parser.add_argument(
                *args,
                type=str,
                help=help,
                required=req,
                default=default_value,
            )
        elif get_origin(f.type) is Callable2:
            parser.add_argument(
                *args,
                type=str,
                help=help,
                required=req,
                default=default_value,
            )
        else:
            parser.add_argument(
                *args,
                type=_get_cli_arg_type(f.type),
                help=help,
                required=req,
                default=default_value,
            )

def cliarg(help: str = "", short: str | list[str] | None = None, **kwargs):
    return field(metadata={"help": help, "short": short if isinstance(short, list) else [short]}, **kwargs)

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
            args.func(_from_cli_args(args.cmd_type, args))
        else:
            parser.print_help()
    else:
        _add_args(parser, _get_first_arg(cmd_or_cmds))
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
