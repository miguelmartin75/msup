import importlib
import inspect
import json
import os
from collections.abc import Callable as Callable2, Mapping
from dataclasses import MISSING, dataclass, fields, is_dataclass
from types import UnionType
from typing import Annotated, Any, Callable, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]:
    raise NotImplementedError


def from_dict(clazz: type[T], x: dict[Any, Any]) -> T:
    raise NotImplementedError


def to_dict(x: Any, type_class: type | Callable[..., Any] | None = None) -> dict[str, Any]:
    raise NotImplementedError


def to_json(
    x: Any,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
) -> str | None:
    raise NotImplementedError


def is_pydantic_model(candidate: type | object) -> bool:
    raise NotImplementedError


def is_structured_model(candidate: type | object) -> bool:
    raise NotImplementedError


PydanticBaseModel: type | None = None
PydanticV1BaseModel: type | None = None

try:
    from pydantic import BaseModel as pydantic_base_model
except ImportError:
    pass
else:
    PydanticBaseModel = pydantic_base_model
    try:
        from pydantic.v1 import BaseModel as pydantic_v1_base_model
    except ImportError:
        PydanticV1BaseModel = PydanticBaseModel
    else:
        PydanticV1BaseModel = pydantic_v1_base_model


@dataclass
class FieldSpec:
    name: str
    annotation: Any
    annotations: list[Any]
    default: Any = MISSING
    default_factory: Any = MISSING


def unwrap_annotated(annotation: Any) -> tuple[Any, list[Any]]:
    if get_origin(annotation) is Annotated:
        annotation, *annotations = get_args(annotation)
    else:
        annotations = []
    return annotation, annotations


def is_pydantic_model(candidate: type | object) -> bool:
    clazz = candidate if inspect.isclass(candidate) else type(candidate)
    if PydanticBaseModel is None:
        result = False
    elif PydanticV1BaseModel is not None and issubclass(clazz, PydanticV1BaseModel):
        raise TypeError(f"Pydantic v1 models are not supported: {clazz}")
    elif issubclass(clazz, PydanticBaseModel):
        if not hasattr(clazz, "model_fields"):
            raise TypeError(f"Pydantic v1 models are not supported: {clazz}")
        result = True
    else:
        result = False
    return result


def is_structured_model(candidate: type | object) -> bool:
    result = is_dataclass(candidate) or is_pydantic_model(candidate)
    return result


def from_json(clazz: type[T], s: str | None = None, file_like=None, path: str | None = None) -> T:
    if path:
        assert os.path.exists(path), f"{path} does not exist"
        with open(path) as in_f:
            result = from_dict(clazz, json.load(in_f))
    elif file_like:
        result = from_dict(clazz, json.load(file_like))
    else:
        assert s is not None, "s must be provided when file_like and path are absent"
        result = from_dict(clazz, json.loads(s))
    return result


def to_json(
    x: T,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
) -> str | None:
    if file_like:
        if isinstance(file_like, str):
            assert file_like.endswith(".json"), f"file should end with json, got: {file_like}"
            parent = os.path.dirname(file_like)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(file_like, "w") as out_f:
                json.dump(to_dict(x, type_class), out_f, indent=indent)
        else:
            json.dump(to_dict(x, type_class), file_like, indent=indent)
        result = None
    else:
        result = json.dumps(to_dict(x, type_class), indent=indent)
    return result


def has_default_value(f: FieldSpec) -> bool:
    return f.default is not MISSING or f.default_factory is not MISSING


def fields_or_init_kwargs(target: type | Callable[..., Any]) -> list[FieldSpec]:
    is_function_or_method = inspect.isfunction(target) or inspect.ismethod(target)
    assert inspect.isclass(target) or is_function_or_method, f"{target} is not a class, function, or method"

    if is_dataclass(target):
        hints = get_type_hints(target, include_extras=True)
        result = []
        for field in fields(target):
            annotation, annotations = unwrap_annotated(hints.get(field.name, field.type))
            result.append(
                FieldSpec(
                    field.name,
                    annotation,
                    annotations,
                    field.default,
                    field.default_factory,
                )
            )
    elif is_pydantic_model(target):
        hints = get_type_hints(target, include_extras=True)
        result = []
        pydantic_target: Any = target
        for name, model_field in pydantic_target.model_fields.items():
            default = MISSING if model_field.is_required() else model_field.default
            default_factory = model_field.default_factory if model_field.default_factory is not None else MISSING
            annotation, annotations = unwrap_annotated(hints.get(name, model_field.annotation))
            result.append(FieldSpec(name, annotation, annotations, default, default_factory))
    else:
        inspected_target = target.__init__ if inspect.isclass(target) else target
        signature = inspect.signature(inspected_target)
        hints = get_type_hints(inspected_target, include_extras=True)
        result = []
        for name, parameter in signature.parameters.items():
            if name in ("self", "cls"):
                continue
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
                continue
            default = MISSING if parameter.default is inspect._empty else parameter.default
            annotation, annotations = unwrap_annotated(hints.get(name, parameter.annotation))
            if annotation is inspect._empty:
                annotation = None
            result.append(FieldSpec(name, annotation, annotations, default, MISSING))
    return result


def load_callable(name: str) -> Any:
    idx = name.rfind(".")
    assert idx != -1, f"expected <module_name>.<name>, got {name}"
    module_name = name[0:idx]
    fn_name = name[idx + 1 :]
    mod = importlib.import_module(module_name)
    return getattr(mod, fn_name)


def maybe_idx(xs: tuple[Any, ...] | list[Any], idx: int, default: Any = None) -> Any:
    return xs[idx] if idx < len(xs) else default


def get_optional_type(annotation: Any) -> Any | None:
    annotation, _ = unwrap_annotated(annotation)
    args = get_args(annotation)
    if get_origin(annotation) in (Union, UnionType) and len(args) == 2 and type(None) in args:
        result = next(arg for arg in args if arg is not type(None))
    else:
        result = None
    return result


def get_collection_args(annotation: Any, count: int = 0) -> tuple[Any, ...]:
    annotation, _ = unwrap_annotated(annotation)
    origin = annotation_origin(annotation)
    args = get_args(annotation)
    if origin is dict:
        result = (maybe_idx(args, 0, Any), maybe_idx(args, 1, Any))
    elif origin is list:
        item_type = maybe_idx(args, 0, Any)
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


def is_optional(annotation: Any) -> bool:
    return get_optional_type(annotation) is not None


def annotation_origin(annotation: Any) -> Any:
    annotation, _ = unwrap_annotated(annotation)
    return get_origin(annotation) or annotation


def effective_type(annotation: Any, field_name: str) -> Any:
    annotation, _ = unwrap_annotated(annotation)
    optional_type = get_optional_type(annotation)
    if optional_type is not None:
        result = optional_type
    elif annotation_origin(annotation) in (Union, UnionType):
        raise TypeError(f"{field_name}: non-optional union annotations are not supported by the CLI: {annotation}")
    else:
        result = annotation
    return result


def union_member(annotation: Any, concrete_type: type, field_name: str = "value") -> Any:
    candidates = []
    for member in get_args(annotation):
        if member is type(None):
            continue
        compatible, _ = is_compat(member, concrete_type)
        if compatible:
            candidates.append(member)

    exact = [member for member in candidates if annotation_origin(member) is concrete_type]
    if len(exact) == 1:
        result = exact[0]
    elif len(candidates) == 1:
        result = candidates[0]
    elif not candidates:
        raise TypeError(f"{field_name}: {annotation} cannot be converted from {concrete_type}")
    else:
        raise TypeError(f"{field_name}: ambiguous conversion from {concrete_type} to {annotation}: {candidates}")
    return result


def is_compat(field_type: Any, concrete_type: type) -> tuple[bool, Any | None]:
    optional_type = get_optional_type(field_type)
    if concrete_type is type(None):
        return optional_type is not None, type(None) if optional_type is not None else None
    elif optional_type is not None:
        return is_compat(optional_type, concrete_type)
    else:
        origin = annotation_origin(field_type)
        concrete_origin = annotation_origin(concrete_type)
        if origin in (Union, UnionType):
            try:
                result = union_member(field_type, concrete_type)
            except TypeError:
                return False, None
            return True, result
        elif field_type is Any:
            return True, Any
        elif is_structured_model(field_type):
            result = concrete_origin in (field_type, dict, str)
            return result, field_type if result else None
        elif origin is dict:
            result = concrete_origin in (dict, str)
            return result, dict if result else None
        elif origin in (list, tuple):
            result = concrete_origin in (list, tuple)
            return result, origin if result else None
        elif origin is Callable2:
            result = concrete_origin is str
            return result, Callable2 if result else None
        elif origin in (int, float, bool, str) and concrete_origin in (int, float, bool, str):
            return True, origin
        else:
            return origin is concrete_origin, origin if origin is concrete_origin else None


def dict_from_str(x: str) -> dict[Any, Any]:
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


def from_dict_value(x: Any, field_type: Any, concrete_type: type, field_name: str) -> Any:
    origin = annotation_origin(field_type)
    if x is None:
        if is_optional(field_type) or field_type is Any:
            result = None
        else:
            raise TypeError(f"{field_name}: {field_type} cannot be converted from None")
    else:
        optional_type = get_optional_type(field_type)
        if optional_type is not None:
            result = from_dict_value(x, optional_type, concrete_type, field_name)
        elif origin in (Union, UnionType):
            member = union_member(field_type, concrete_type, field_name)
            result = from_dict_value(x, member, concrete_type, field_name)
        else:
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
                compatible, _ = is_compat(field_type, concrete_type)
                if not compatible:
                    raise TypeError(f"{field_name}: {field_type} cannot be converted from {concrete_type}")
            if field_type is Any:
                result = x
            elif is_structured_model(field_type):
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
                        from_dict_value(key, key_type, type(key), f"{field_name}.key"): from_dict_value(
                            value, value_type, type(value), f"{field_name}.value"
                        )
                        for key, value in raw.items()
                    }
                elif origin in (list, tuple):
                    item_types = get_collection_args(field_type, len(x))
                    if (
                        origin is tuple
                        and len(get_args(field_type)) > 1
                        and get_args(field_type)[1] is not Ellipsis
                        and len(x) != len(item_types)
                    ):
                        raise TypeError(f"{field_name}: expected {len(item_types)} tuple values, got {len(x)}")
                    result = origin(
                        from_dict_value(
                            item,
                            item_types[index] if index < len(item_types) else Any,
                            type(item),
                            f"{field_name}[{index}]",
                        )
                        for index, item in enumerate(x)
                    )
                elif origin is Callable2:
                    pass
                else:
                    raise TypeError(f"unexpected type: {field_type} (origin={origin})")
    return result


def to_dict_value(x: Any, field_type: Any) -> Any:
    origin = annotation_origin(field_type)
    optional_type = get_optional_type(field_type)
    if x is None:
        return None
    elif optional_type is not None:
        return to_dict_value(x, optional_type)
    elif origin in (Union, UnionType):
        member = union_member(field_type, type(x))
        return to_dict_value(x, member)
    elif field_type is Any:
        return x
    elif is_structured_model(x):
        return to_dict(x)
    elif origin is dict:
        key_type, value_type = get_collection_args(field_type)
        return {to_dict_value(key, key_type): to_dict_value(value, value_type) for key, value in x.items()}
    elif origin in (list, tuple):
        item_types = get_collection_args(field_type, len(x))
        values = [
            to_dict_value(item, item_types[index] if index < len(item_types) else Any) for index, item in enumerate(x)
        ]
        return tuple(values) if isinstance(x, tuple) else values
    elif origin is Callable2:
        if not callable(x):
            raise TypeError(f"expected callable value for {field_type}, got {type(x)}")
        return f"{x.__module__}.{x.__name__}"
    elif origin in (int, float, str, bool):
        return origin(x)
    else:
        return x


def to_dict(x: Any, type_class: type | Callable[..., Any] | None = None) -> dict[str, Any]:
    if type_class is None and is_pydantic_model(x):
        pydantic_model: Any = x
        result = pydantic_model.model_dump()
    else:
        result: dict[str, Any] = {}
        field_source = type(x) if type_class is None else type_class
        for f in fields_or_init_kwargs(field_source):
            if isinstance(x, Mapping) and f.name in x:
                mapping: Mapping[Any, Any] = x
                value = mapping[f.name]
                result[f.name] = to_dict_value(value, f.annotation or type(value))
            elif not isinstance(x, Mapping) and hasattr(x, f.name):
                value = getattr(x, f.name)
                result[f.name] = to_dict_value(value, f.annotation or type(value))
    return result


def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for f in fields_or_init_kwargs(clazz):
        if isinstance(x, dict):
            if f.name in x:
                result[f.name] = x[f.name]
        elif hasattr(x, f.name):
            result[f.name] = getattr(x, f.name)
    return result


def from_dict(clazz: type[T], x: dict[Any, Any]) -> T:
    if is_pydantic_model(clazz):
        pydantic_model: Any = clazz
        result = pydantic_model.model_validate(x)
    else:
        construct_args: dict[str, Any] = {}
        for f in fields_or_init_kwargs(clazz):
            if f.name in x:
                field_type = f.annotation or type(x[f.name])
                construct_args[f.name] = from_dict_value(x[f.name], field_type, type(x[f.name]), f.name)
        result = clazz(**construct_args)
    return result
