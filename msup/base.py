import inspect
import json
import os
import pkgutil
from collections.abc import Callable as Callable2, Mapping
from copy import deepcopy
from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from types import UnionType
from typing import Annotated, Any, Callable, TypeAliasType, TypeVar, Union, cast, get_args, get_origin, get_type_hints

T = TypeVar("T")
type Kwargs = dict[str, Any]


# fmt: off
def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]: ...
def from_dict(clazz: type[T], x: dict[Any, Any]) -> T: ...
def kwargs_from_dict(target: type | Callable[..., Any], values: Mapping[str, Any], *, field_name: str = "kwargs") -> dict[str, Any]: ...
def from_kwargs(owner: type | Callable[..., Any], values: Mapping[str, Any]) -> dict[str, Any]: ...
def to_dict(x: Any, type_class: type | Callable[..., Any] | None = None) -> dict[str, Any]: ...
def to_json(
    x: Any,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
) -> str | None: ...
def is_pydantic_model(candidate: type | object) -> bool: ...
def is_structured_model(candidate: type | object) -> bool: ...
def metadata_from_annotations(annotations: list[Any], field_name: str = "") -> "Metadata | None": ...
def selected_target_fields(target: type | Callable[..., Any]) -> "list[FieldSpec]": ...
def load_callable(name: str) -> Any: ...
def dump_callable(value: Any) -> str: ...
# fmt: on


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


@dataclass(frozen=True, kw_only=True)
class Metadata:
    """Shared field metadata; kwargs_for links dependent kwargs to its selector."""

    kwargs_for: str | None = None


@dataclass
class FieldSpec:
    """A reflected field whose kwargs_relation links only to its preceding selector."""

    name: str
    annotation: Any
    annotations: list[Any]
    default: Any = MISSING
    default_factory: Any = MISSING
    kwargs_relation: "FieldSpec | None" = None


def unwrap_annotated(annotation: Any) -> tuple[Any, list[Any]]:
    if get_origin(annotation) is Annotated:
        annotation, *annotations = get_args(annotation)
    else:
        annotations = []
    return annotation, annotations


def normalize_annotation(annotation: Any) -> Any:
    annotation, _ = unwrap_annotated(annotation)
    return annotation.__value__ if isinstance(annotation, TypeAliasType) else annotation


def metadata_from_annotations(annotations: list[Any], field_name: str = "") -> Metadata | None:
    """Returns the sole Metadata annotation and rejects duplicates."""

    metadata = [value for value in annotations if isinstance(value, Metadata)]
    if len(metadata) > 1:
        prefix = f"{field_name}: " if field_name else ""
        raise TypeError(f"{prefix}an annotation can contain at most one CliArg or Metadata")
    result = metadata[0] if metadata else None
    return result


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
    return is_dataclass(candidate) or is_pydantic_model(candidate)


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
    result = []
    if is_dataclass(target):
        hints = get_type_hints(target, include_extras=True)
        result = [
            FieldSpec(
                field.name, *unwrap_annotated(hints.get(field.name, field.type)), field.default, field.default_factory
            )
            for field in fields(target)
        ]
    elif is_pydantic_model(target):
        hints = get_type_hints(target, include_extras=True)
        for name, model_field in cast(Any, target).model_fields.items():
            default = (
                MISSING if model_field.is_required() or model_field.default_factory is not None else model_field.default
            )
            default_factory = model_field.default_factory if model_field.default_factory is not None else MISSING
            annotation, annotations = unwrap_annotated(hints.get(name, model_field.annotation))
            result.append(FieldSpec(name, annotation, annotations, default, default_factory))
    else:
        inspected_target = target.__init__ if inspect.isclass(target) else target
        hints = get_type_hints(inspected_target, include_extras=True)
        for name, parameter in inspect.signature(inspected_target).parameters.items():
            if name in ("self", "cls"):
                continue
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
                continue
            default = MISSING if parameter.default is inspect._empty else parameter.default
            annotation, annotations = unwrap_annotated(hints.get(name, parameter.annotation))
            if annotation is inspect._empty:
                annotation = None
            result.append(FieldSpec(name, annotation, annotations, default, MISSING))

    owner_name = target.__qualname__
    linked_selectors: set[str] = set()
    indexed_fields = {field.name: (index, field) for index, field in enumerate(result)}
    for field_index, field in enumerate(result):
        field_name = f"{owner_name}.{field.name}"
        metadata = metadata_from_annotations(field.annotations, field_name)
        if metadata is None or metadata.kwargs_for is None:
            continue
        relation_name = metadata.kwargs_for
        relation_annotation = normalize_annotation(field.annotation)
        if get_origin(relation_annotation) is not dict or get_args(relation_annotation) != (str, Any):
            raise TypeError(f"{field_name}: kwargs_for fields must be annotated as dict[str, Any] or Kwargs")
        if field.name == relation_name:
            raise TypeError(f"{field_name}: kwargs_for must name a different selector field")
        if relation_name not in indexed_fields:
            raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} does not exist")
        selector_index, selector = indexed_fields[relation_name]
        if selector_index >= field_index:
            raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} must precede the kwargs field")
        selector_metadata = metadata_from_annotations(selector.annotations, f"{owner_name}.{selector.name}")
        if selector_metadata is not None and selector_metadata.kwargs_for is not None:
            raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} cannot be a kwargs field")
        if annotation_origin(selector.annotation) is not Callable2:
            raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} must be annotated as Callable")
        if relation_name in linked_selectors:
            raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} already has a kwargs field")
        field.kwargs_relation = selector
        linked_selectors.add(relation_name)
    if is_pydantic_model(target):
        for field in result:
            if field.kwargs_relation is not None or field.name in linked_selectors:
                alias = cast(Any, target).model_fields[field.name].validation_alias
                if alias is not None and not isinstance(alias, str):
                    raise TypeError(f"{owner_name}.{field.name}: kwargs_for only supports string validation aliases")
    return result


def load_callable(name: str) -> Any:
    """Loads a trusted callable from a canonical module.qualname reference."""
    return pkgutil.resolve_name(name)


def dump_callable(value: Any) -> str:
    """Returns a canonical reference only when it reloads to the same callable."""

    if not (inspect.isclass(value) or inspect.isfunction(value) or inspect.ismethod(value)):
        raise TypeError(f"expected an importable class, function, or method, got {type(value)}")
    module_name = getattr(value, "__module__", None)
    qualname = getattr(value, "__qualname__", None)
    if not module_name or not qualname or "<locals>" in qualname or "<lambda>" in qualname:
        raise TypeError(f"{value}: cannot be represented by an importable module.qualname")
    result = f"{module_name}.{qualname}"
    if load_callable(result) is not value:
        raise TypeError(f"{value}: module.qualname {result!r} does not resolve to the same object")
    return result


def get_optional_type(annotation: Any) -> Any | None:
    annotation = normalize_annotation(annotation)
    args = get_args(annotation)
    if get_origin(annotation) in (Union, UnionType) and len(args) == 2 and type(None) in args:
        result = next(arg for arg in args if arg is not type(None))
    else:
        result = None
    return result


def get_collection_args(annotation: Any, count: int = 0) -> tuple[Any, ...]:
    annotation = normalize_annotation(annotation)
    origin = annotation_origin(annotation)
    args = get_args(annotation)
    if origin is dict:
        result = (args + (Any, Any))[:2]
    elif origin is list:
        item_type = args[0] if args else Any
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
    annotation = normalize_annotation(annotation)
    result = get_origin(annotation) or annotation
    return result


def effective_type(annotation: Any, field_name: str) -> Any:
    annotation = normalize_annotation(annotation)
    optional_type = get_optional_type(annotation)
    if optional_type is not None:
        return optional_type
    if annotation_origin(annotation) in (Union, UnionType):
        raise TypeError(f"{field_name}: non-optional union annotations are not supported by the CLI: {annotation}")
    return annotation


def union_member(annotation: Any, concrete_type: type, field_name: str = "value") -> Any:
    candidates = [
        member for member in get_args(annotation) if member is not type(None) and is_compat(member, concrete_type)[0]
    ]
    exact = [member for member in candidates if annotation_origin(member) is concrete_type]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise TypeError(f"{field_name}: {annotation} cannot be converted from {concrete_type}")
    raise TypeError(f"{field_name}: ambiguous conversion from {concrete_type} to {annotation}: {candidates}")


def enum_type(annotation: Any) -> type[Enum] | None:
    origin = annotation_origin(annotation)
    if inspect.isclass(origin) and issubclass(origin, Enum):
        result = origin
    else:
        result = None
    return result


def validate_enum_values(enum_type: type[Enum], field_name: str) -> None:
    if any(type(member.value) not in (str, int, float, bool) for member in enum_type):
        raise TypeError(f"{field_name}: {enum_type.__name__} values must be str, int, float, or bool")


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
        elif (enum_class := enum_type(field_type)) is not None:
            validate_enum_values(enum_class, "value")
            result = concrete_origin is enum_class or any(
                type(member.value) is concrete_origin for member in enum_class
            )
            return result, enum_class if result else None
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


def _conversion_annotation_supported(annotation: Any) -> bool:
    annotation = normalize_annotation(annotation)
    origin = annotation_origin(annotation)
    if annotation in (Any, type(None)):
        result = True
    elif origin in (Union, UnionType):
        result = all(_conversion_annotation_supported(member) for member in get_args(annotation))
    elif origin is dict:
        key_type, value_type = get_collection_args(annotation)
        result = _conversion_annotation_supported(key_type) and _conversion_annotation_supported(value_type)
    elif origin in (list, tuple):
        result = all(_conversion_annotation_supported(item) for item in get_collection_args(annotation))
    elif origin in (int, float, str, bool, Callable2):
        result = True
    elif enum_type(annotation) is not None:
        result = True
    else:
        result = is_structured_model(annotation)
    return result


def selected_target_fields(target: type | Callable[..., Any]) -> list[FieldSpec]:
    """Reflects a selected target's supported explicit signature without invoking it."""

    is_function_or_method = inspect.isfunction(target) or inspect.ismethod(target)
    if not inspect.isclass(target) and not is_function_or_method:
        raise TypeError(f"{target}: selected targets must be classes, functions, or methods")

    inspected_target = target.__init__ if inspect.isclass(target) else target
    hints = get_type_hints(inspected_target, include_extras=True)
    result = []
    for name, parameter in inspect.signature(inspected_target).parameters.items():
        if inspect.isclass(target) and name in ("self", "cls"):
            continue
        if parameter.kind is parameter.POSITIONAL_ONLY:
            raise TypeError(f"{name}: selected target parameters cannot be positional-only")
        if parameter.kind is parameter.VAR_POSITIONAL:
            raise TypeError(f"{name}: selected target parameters cannot use *args")
        if parameter.kind is parameter.VAR_KEYWORD:
            raise TypeError(f"{name}: selected target parameters cannot use **kwargs")
        annotation = hints.get(name, parameter.annotation)
        if annotation is inspect.Parameter.empty:
            raise TypeError(f"{name}: selected target parameters must have an annotation")
        annotation, annotations = unwrap_annotated(annotation)
        if not _conversion_annotation_supported(annotation):
            raise TypeError(f"{name}: unsupported selected target annotation: {annotation}")
        default = MISSING if parameter.default is inspect._empty else parameter.default
        result.append(FieldSpec(name, annotation, annotations, default, MISSING))
    return result


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
            result = from_dict_value(x, union_member(field_type, concrete_type, field_name), concrete_type, field_name)
        elif (enum_class := enum_type(field_type)) is not None:
            validate_enum_values(enum_class, field_name)
            try:
                result = x if isinstance(x, enum_class) else enum_class(x)
            except ValueError as error:
                raise TypeError(
                    f"{field_name}: invalid {enum_class.__name__} value {x!r}; expected one of {[member.value for member in enum_class]}"
                ) from error
        elif origin is Callable2:
            if isinstance(x, str):
                result = load_callable(x)
            else:
                result = x
            if not callable(result):
                if isinstance(x, str):
                    raise TypeError(f"{field_name}: {x} does not resolve to a callable")
                raise TypeError(f"{field_name}: expected a callable or importable callable reference")
        else:
            compatible, _ = is_compat(field_type, concrete_type)
            if not compatible:
                raise TypeError(f"{field_name}: {field_type} cannot be converted from {concrete_type}")
            if field_type is Any:
                result = x
            elif is_structured_model(field_type):
                raw = dict_from_str(x) if isinstance(x, str) else x
                if concrete_type is field_type:
                    result = x
                elif is_dataclass(field_type):
                    result = field_type(**_from_kwargs(field_type, raw, field_name))
                else:
                    result = from_dict(field_type, raw)
            elif origin is bool and isinstance(x, str):
                normalized = x.lower()
                if normalized in ("y", "yes", "on", "1", "true", "t"):
                    result = True
                elif normalized in ("n", "no", "off", "0", "false", "f"):
                    result = False
                else:
                    raise TypeError(
                        f"{field_name}: invalid boolean value {x!r}; expected true/false, 1/0, yes/no, on/off, y/n, or t/f"
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
        return to_dict_value(x, union_member(field_type, type(x)))
    elif field_type is Any:
        return x
    elif (enum_class := enum_type(field_type)) is not None:
        validate_enum_values(enum_class, "value")
        if not isinstance(x, enum_class):
            raise TypeError(f"expected {enum_class.__name__} value, got {type(x)}")
        return x.value
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
        return dump_callable(x)
    elif origin in (int, float, str, bool):
        return origin(x)
    else:
        return x


def _to_dict_value(value: Any, annotation: Any, field_name: str) -> Any:
    if value is None:
        return None
    annotation = get_optional_type(annotation) or normalize_annotation(annotation)
    if annotation_origin(annotation) in (Union, UnionType):
        annotation = union_member(annotation, type(value), field_name)
    if is_structured_model(annotation) or (
        inspect.isclass(annotation)
        and any(field.kwargs_relation is not None for field in fields_or_init_kwargs(annotation))
    ):
        return _to_dict(value, None, field_name)
    return to_dict_value(value, annotation)


def _to_dict(x: Any, type_class: type | Callable[..., Any] | None, owner_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    mapping = x if isinstance(x, Mapping) else None
    for f in fields_or_init_kwargs(type(x) if type_class is None else type_class):
        value = mapping[f.name] if mapping is not None and f.name in mapping else getattr(x, f.name, MISSING)
        if value is MISSING:
            continue
        if f.kwargs_relation is None:
            result[f.name] = _to_dict_value(value, f.annotation or type(value), f"{owner_name}.{f.name}")
        else:
            target = (
                mapping.get(f.kwargs_relation.name, MISSING)
                if mapping is not None
                else getattr(x, f.kwargs_relation.name, MISSING)
            )
            field_name = f"{owner_name}.{f.name}"
            if target is MISSING:
                raise TypeError(f"{field_name}: missing selector {f.kwargs_relation.name!r}")
            typed_values = kwargs_from_dict(target, value, field_name=field_name)
            result[f.name] = {
                parameter.name: _to_dict_value(
                    typed_values[parameter.name], parameter.annotation, f"{field_name}.{parameter.name}"
                )
                for parameter in selected_target_fields(target)
                if parameter.name in typed_values
            }
    return result


def to_dict(x: Any, type_class: type | Callable[..., Any] | None = None) -> dict[str, Any]:
    return _to_dict(x, type_class, cast(Any, type_class or type(x)).__qualname__)


def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for f in fields_or_init_kwargs(clazz):
        if isinstance(x, Mapping):
            if f.name in x:
                result[f.name] = x[f.name]
        elif hasattr(x, f.name):
            result[f.name] = getattr(x, f.name)
    return result


def _kwargs_from_fields(parameters: list[FieldSpec], values: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name}: expected a mapping, got {type(values)}")
    unknown = next((name for name in values if name not in {parameter.name for parameter in parameters}), None)
    if unknown is not None:
        raise TypeError(f"{field_name}.{unknown}: unknown target parameter")
    result = {}
    for parameter in parameters:
        if parameter.name in values:
            value = values[parameter.name]
            result[parameter.name] = from_dict_value(
                value, parameter.annotation or type(value), type(value), f"{field_name}.{parameter.name}"
            )
        elif parameter.default is MISSING:
            raise TypeError(f"{field_name}.{parameter.name}: missing required target parameter")
    return result


def kwargs_from_dict(
    target: type | Callable[..., Any], values: Mapping[str, Any], *, field_name: str = "kwargs"
) -> dict[str, Any]:
    """Converts a selected target's explicit kwargs without invoking the target."""

    try:
        parameters = selected_target_fields(target)
    except TypeError as error:
        raise TypeError(f"{field_name}: {error}") from error
    return _kwargs_from_fields(parameters, values, field_name)


def _construct_owner(owner: type, values: Mapping[str, Any]) -> Any:
    if is_pydantic_model(owner):
        result = dict(values)
        fields = fields_or_init_kwargs(owner)
        for field in fields:
            if field.kwargs_relation is not None or any(item.kwargs_relation is field for item in fields):
                alias = cast(Any, owner).model_fields[field.name].validation_alias
                if isinstance(alias, str) and field.name in result:
                    result[alias] = result.pop(field.name)
        result = cast(Any, owner).model_validate(result)
    else:
        result = owner(**values)
    return result


def _from_kwargs(owner: type | Callable[..., Any], values: Mapping[str, Any], owner_name: str) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{owner.__qualname__}: expected a mapping, got {type(values)}")
    field_info = fields_or_init_kwargs(owner)
    pydantic_owner = is_pydantic_model(owner)
    result = dict(values) if pydantic_owner else {}
    for f in field_info:
        dependent = next((field for field in field_info if field.kwargs_relation is f), None)
        field_name = f"{owner_name}.{f.name}"
        if f.kwargs_relation is not None:
            supplied = values.get(f.name, MISSING)
            if supplied is MISSING and pydantic_owner:
                alias = cast(Any, owner).model_fields[f.name].validation_alias
                supplied = values.get(alias, MISSING) if isinstance(alias, str) else MISSING
            supplied = {} if supplied is MISSING else supplied
            if not isinstance(supplied, Mapping):
                raise TypeError(f"{field_name}: expected a mapping, got {type(supplied)}")
            target = result[f.kwargs_relation.name]
            try:
                parameters = selected_target_fields(target)
            except TypeError as error:
                raise TypeError(f"{field_name}: {error}") from error
            if any(parameter.name not in supplied for parameter in parameters):
                if f.default is not MISSING:
                    default = deepcopy(f.default)
                else:
                    default = f.default_factory() if f.default_factory is not MISSING else {}
            else:
                default = {}
            if not isinstance(default, Mapping):
                raise TypeError(f"{field_name}: expected a mapping default, got {type(default)}")
            result[f.name] = _kwargs_from_fields(parameters, {**default, **supplied}, field_name)
        elif dependent is not None:
            value = values.get(f.name, MISSING)
            if value is MISSING and pydantic_owner:
                alias = cast(Any, owner).model_fields[f.name].validation_alias
                value = values.get(alias, MISSING) if isinstance(alias, str) else MISSING
            if value is not MISSING:
                result[f.name] = from_dict_value(value, f.annotation or type(value), type(value), field_name)
            elif f.default is not MISSING:
                result[f.name] = from_dict_value(deepcopy(f.default), f.annotation, type(f.default), field_name)
            elif f.default_factory is not MISSING:
                value = f.default_factory()
                result[f.name] = from_dict_value(value, f.annotation, type(value), field_name)
            else:
                raise TypeError(f"{field_name}: missing selector for {dependent.name!r}")
        elif (value := values.get(f.name, MISSING)) is not MISSING:
            field_type = get_optional_type(f.annotation) or normalize_annotation(f.annotation) or type(value)
            if inspect.isclass(field_type) and any(
                field.kwargs_relation is not None for field in fields_or_init_kwargs(field_type)
            ):
                raw = dict_from_str(value) if isinstance(value, str) else value
                result[f.name] = _construct_owner(field_type, _from_kwargs(field_type, raw, field_name))
            elif not pydantic_owner:
                result[f.name] = from_dict_value(value, f.annotation or field_type, type(value), field_name)
    return result


def from_kwargs(owner: type | Callable[..., Any], values: Mapping[str, Any]) -> dict[str, Any]:
    """Converts an owner's linked fields without invoking a function owner."""

    return _from_kwargs(owner, values, cast(Any, owner).__qualname__)


def from_dict(clazz: type[T], x: dict[Any, Any]) -> T:
    if any(field.kwargs_relation is not None for field in fields_or_init_kwargs(clazz)):
        result = _construct_owner(clazz, _from_kwargs(clazz, x, clazz.__qualname__))
    elif is_dataclass(clazz):
        result = clazz(**_from_kwargs(clazz, x, clazz.__qualname__))
    elif is_pydantic_model(clazz):
        fields_or_init_kwargs(clazz)
        result = cast(Any, clazz).model_validate(x)
    else:
        result = clazz(
            **{
                f.name: from_dict_value(x[f.name], f.annotation or type(x[f.name]), type(x[f.name]), f.name)
                for f in fields_or_init_kwargs(clazz)
                if f.name in x
            }
        )
    return result
