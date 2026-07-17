import importlib
import json
import os
from collections.abc import Callable as Callable2
from dataclasses import MISSING, fields, is_dataclass
from types import UnionType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_kwargs(x: T) -> dict: ...
def from_dict(clazz: type, x: dict) -> T: ...
def to_dict(x: T) -> dict: ...


def from_json(clazz: type, s: str | None = None, file_like=None, path: str | None = None) -> T:
    if path:
        assert os.path.exists(path), f"{path} does not exist"
        with open(path) as in_f:
            result = from_dict(clazz, json.load(in_f))
    elif file_like:
        result = from_dict(clazz, json.load(file_like))
    else:
        result = from_dict(clazz, json.loads(s))
    return result


def to_json(x: T, file_like=None, indent: int | None = 2) -> str | None:
    if file_like:
        if isinstance(file_like, str):
            assert file_like.endswith(".json"), f"file should end with json, got: {file_like}"
            parent = os.path.dirname(file_like)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(file_like, "w") as out_f:
                json.dump(to_dict(x), out_f, indent=indent)
        else:
            json.dump(to_dict(x), file_like, indent=indent)
        result = None
    else:
        result = json.dumps(to_dict(x), indent=indent)
    return result


def has_default_value(f):
    return f.default is not MISSING or f.default_factory is not MISSING


def load_callable(name: str):
    parts = name.split(".")
    for index in range(len(parts) - 1, 0, -1):
        try:
            result = importlib.import_module(".".join(parts[:index]))
        except ModuleNotFoundError:
            continue
        for part in parts[index:]:
            result = getattr(result, part)
        return result
    raise ValueError(f"expected an importable callable reference, got: {name}")


def get_optional_type(annotation: type) -> type | None:
    """Return an optional union's non-None member, independent of member order."""
    args = get_args(annotation)
    if get_origin(annotation) in (Union, UnionType) and len(args) == 2 and type(None) in args:
        result = next(arg for arg in args if arg is not type(None))
    else:
        result = None
    return result


def get_collection_args(annotation: type, count: int = 0) -> tuple[type, ...]:
    """Return collection member annotations, substituting Any for omitted members."""
    origin = _annotation_origin(annotation)
    args = get_args(annotation)
    if origin is dict:
        result = args if len(args) == 2 else (Any, Any)
    elif origin is list:
        item_type = args[0] if len(args) == 1 else Any
        result = (item_type,) * count if count else (item_type,)
    elif origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            result = (args[0],) * count
        elif args:
            result = args
        else:
            result = (Any,) * count
    else:
        result = ()
    return result


def is_optional(annotation: type) -> bool:
    return get_optional_type(annotation) is not None


def _annotation_origin(annotation: type) -> type:
    return get_origin(annotation) or annotation


def _union_member(annotation: type, concrete_type: type, field_name: str = "value") -> type:
    candidates = []
    for member in get_args(annotation):
        if member is type(None):
            continue
        compatible, _ = _is_compat(member, concrete_type)
        if compatible:
            candidates.append(member)

    exact = [member for member in candidates if _annotation_origin(member) is concrete_type]
    if len(exact) == 1:
        result = exact[0]
    elif len(candidates) == 1:
        result = candidates[0]
    elif not candidates:
        raise TypeError(f"{field_name}: {annotation} cannot be converted from {concrete_type}")
    else:
        raise TypeError(f"{field_name}: ambiguous conversion from {concrete_type} to {annotation}: {candidates}")
    return result


def _is_compat(field_type: type, concrete_type: type) -> tuple[bool, type | None]:
    """Report whether a runtime type can be converted to an annotation."""
    optional_type = get_optional_type(field_type)
    if concrete_type is type(None):
        return optional_type is not None, type(None) if optional_type is not None else None
    if optional_type is not None:
        return _is_compat(optional_type, concrete_type)

    origin = _annotation_origin(field_type)
    concrete_origin = _annotation_origin(concrete_type)
    if origin in (Union, UnionType):
        try:
            result = _union_member(field_type, concrete_type)
        except TypeError:
            return False, None
        return True, result
    if field_type is Any:
        return True, Any
    if is_dataclass(field_type):
        result = concrete_origin in (field_type, dict, str)
        return result, field_type if result else None
    if origin is dict:
        result = concrete_origin in (dict, str)
        return result, dict if result else None
    if origin in (list, tuple):
        result = concrete_origin in (list, tuple)
        return result, origin if result else None
    if origin is Callable2:
        result = concrete_origin is str
        return result, Callable2 if result else None
    if origin in (int, float, bool, str) and concrete_origin in (int, float, bool, str):
        return True, origin
    return origin is concrete_origin, origin if origin is concrete_origin else None


def dict_from_str(x: str) -> dict:
    assert isinstance(x, str)
    if x.startswith("{"):
        result = json.loads(x)
    elif x.endswith(".json"):
        assert os.path.exists(x), f"{x} does not exist"
        with open(x) as in_f:
            result = json.load(in_f)
    else:
        raise AssertionError(f"unexpected str: {x}")
    return result


def _from_value(x: T, field_type: type, concrete_type: type, field_name: str):
    if x is None:
        if is_optional(field_type) or field_type is Any:
            result = None
        else:
            raise TypeError(f"{field_name}: {field_type} cannot be converted from None")
    else:
        optional_type = get_optional_type(field_type)
        if optional_type is not None:
            result = _from_value(x, optional_type, concrete_type, field_name)
        elif _annotation_origin(field_type) in (Union, UnionType):
            member = _union_member(field_type, concrete_type, field_name)
            result = _from_value(x, member, concrete_type, field_name)
        else:
            origin = _annotation_origin(field_type)
            if origin is Callable2:
                if isinstance(x, str):
                    result = load_callable(x)
                    if not callable(result):
                        raise TypeError(f"{field_name}: {x} does not resolve to a callable")
                elif callable(x):
                    result = x
                else:
                    raise TypeError(f"{field_name}: expected a callable or importable callable reference")
            else:
                compatible, _ = _is_compat(field_type, concrete_type)
                if not compatible:
                    raise TypeError(f"{field_name}: {field_type} cannot be converted from {concrete_type}")
            if field_type is Any:
                result = x
            elif is_dataclass(field_type):
                if concrete_type is field_type:
                    result = x
                elif isinstance(x, str):
                    result = from_dict(field_type, dict_from_str(x))
                else:
                    result = from_dict(field_type, x)
            else:
                if origin is bool and isinstance(x, str):
                    normalized = x.lower()
                    if normalized in ("y", "yes", "on", "1", "true", "t"):
                        result = True
                    elif normalized in ("n", "no", "off", "0", "false", "f"):
                        result = False
                    else:
                        raise TypeError(
                            f"{field_name}: invalid boolean value {x!r}; "
                            "expected true/false, 1/0, yes/no, on/off, y/n, or t/f"
                        )
                elif origin in (int, float, str, bool):
                    result = field_type(x)
                elif origin is dict:
                    raw = dict_from_str(x) if isinstance(x, str) else x
                    key_type, value_type = get_collection_args(field_type)
                    result = {
                        _from_value(key, key_type, type(key), f"{field_name}.key"):
                        _from_value(value, value_type, type(value), f"{field_name}.value")
                        for key, value in raw.items()
                    }
                elif origin in (list, tuple):
                    item_types = get_collection_args(field_type, len(x))
                    if origin is tuple and len(get_args(field_type)) > 1 and get_args(field_type)[1] is not Ellipsis and len(x) != len(item_types):
                        raise TypeError(f"{field_name}: expected {len(item_types)} tuple values, got {len(x)}")
                    result = origin(
                        _from_value(item, item_types[index] if index < len(item_types) else Any, type(item), f"{field_name}[{index}]")
                        for index, item in enumerate(x)
                    )
                elif origin is Callable2:
                    pass
                else:
                    raise TypeError(f"unexpected type: {field_type} (origin={origin})")
    return result


def _to_dict_value(x: T, field_type: type):
    if x is None:
        return None
    optional_type = get_optional_type(field_type)
    if optional_type is not None:
        return _to_dict_value(x, optional_type)
    if _annotation_origin(field_type) in (Union, UnionType):
        member = _union_member(field_type, type(x))
        return _to_dict_value(x, member)
    if field_type is Any:
        return x
    if is_dataclass(x):
        return to_dict(x)

    origin = _annotation_origin(field_type)
    if origin is dict:
        key_type, value_type = get_collection_args(field_type)
        return {
            _to_dict_value(key, key_type): _to_dict_value(value, value_type)
            for key, value in x.items()
        }
    if origin in (list, tuple):
        item_types = get_collection_args(field_type, len(x))
        values = [_to_dict_value(item, item_types[index] if index < len(item_types) else Any) for index, item in enumerate(x)]
        return tuple(values) if isinstance(x, tuple) else values
    if origin is Callable2:
        if not callable(x):
            raise TypeError(f"expected callable value for {field_type}, got {type(x)}")
        return f"{x.__module__}.{x.__qualname__}"
    if origin in (int, float, str, bool):
        return origin(x)
    return x


def _dataclass_hints(clazz: type) -> dict[str, type]:
    return get_type_hints(clazz)


def to_dict(x: T) -> dict:
    assert is_dataclass(x), f"{x!r} is not a dataclass instance"
    hints = _dataclass_hints(type(x))
    result = {}
    for f in fields(x):
        result[f.name] = _to_dict_value(getattr(x, f.name), hints[f.name])
    return result


def to_kwargs(x: T) -> dict:
    assert is_dataclass(x), f"{x!r} is not a dataclass instance"
    return {f.name: getattr(x, f.name) for f in fields(x)}


def from_dict(clazz: type, x: dict) -> T:
    assert is_dataclass(clazz), f"{clazz} is not a dataclass"
    hints = _dataclass_hints(clazz)
    construct_args = {}
    for f in fields(clazz):
        field_type = hints[f.name]
        if f.name in x:
            construct_args[f.name] = _from_value(x[f.name], field_type, type(x[f.name]), f.name)
    return clazz(**construct_args)
