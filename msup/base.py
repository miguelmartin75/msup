import os
import json
import inspect
import importlib
from dataclasses import dataclass, asdict, is_dataclass, fields, MISSING, field
from collections.abc import Callable as Callable2
from types import UnionType
from typing import Optional, List, Dict, Union, TypeVar, get_origin, get_args, Callable, get_type_hints, Any

T = TypeVar('T')

def from_dict(clazz: type, x: dict) -> T: ...
def to_dict(x: T) -> dict: ...
def from_json(clazz: type, s: str | None = None, file_like=None, path: str | None = None) -> T:
    if path:
        assert os.path.exists(path), f"{path} does not exist"
        with open(path) as in_f:
            return from_dict(clazz, json.load(in_f))
    elif file_like:
        return from_dict(clazz, json.load(file_like))
    else:
        return from_dict(clazz, json.loads(s))

def to_json(x: T, file_like=None, indent: int | None = 2) -> str | None:
    if file_like:
        if isinstance(file_like, str):
            assert file_like.endswith(".json"), f"file should end with json, got: {file_like}"
            os.makedirs(os.path.dirname(file_like), exist_ok=True)
            with open(file_like, "w") as out_f:
                json.dump(to_dict(x), out_f, indent=indent)
        else:
            json.dump(to_dict(x), file_like, indent=indent)
    else:
        return json.dumps(to_dict(x), indent=indent)


def has_default_value(f):
    return f.default is not MISSING or f.default_factory is not MISSING

def load_callable(name: str):
    idx = name.rfind('.')
    assert idx != -1, "expected <module_name>.<name>"
    module_name = name[0:idx]
    fn_name = name[idx+1:]
    mod = importlib.import_module(module_name)
    return getattr(mod, fn_name)

def _to_dict_value(x: T, field_type: type):
    t = type(x)
    if is_optional(field_type):
        if x is None:
            return x
        return _to_dict_value(x, get_args(field_type)[0])
    elif t in (dict,):
        return {_to_dict_value(k, get_args(field_type)[0] or type(k)): _to_dict_value(v, get_args(field_type)[1] or type(v)) for k, v in x.items()}
    elif t in (list, List):
        return [_to_dict_value(xx, get_args(field_type)[0] or type(xx)) for xx in x]
    elif is_dataclass(t):
        return to_dict(x)
    elif get_origin(field_type) is Callable2:
        if callable(x):
            return x.__name__
        else:
            assert isinstance(x, str), f"{x.__class__=}"
            return x
    elif get_origin(field_type) in (Union, UnionType):
        for arg in get_args(field_type):
            pass
        breakpoint()
    elif field_type:
        try:
            return field_type(x)
        except:
            breakpoint()
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
        elif xx1 is Callable2:
            return callable(xx2) or isinstance(xx2, str), xx1
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
                    value = from_dict(field_type, json_value)
                    return value
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
    elif origin is Callable2:
        if isinstance(x, str):
            return load_callable(x)
        return x
    else:
        raise AssertionError(f"unexpected type: {field_type} (origin={origin}, concrete_type={concrete_type}, args={args}, x={x})")

def from_dict(clazz: type, x: dict) -> T:
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
