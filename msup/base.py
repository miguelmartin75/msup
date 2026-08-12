import inspect
import json
import os
import pkgutil
from collections.abc import Callable as Callable2, Mapping, Sequence
from copy import deepcopy
from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from types import UnionType
from typing import Annotated, Any, Callable, TypeAliasType, TypeVar, Union, cast, get_args, get_origin, get_type_hints

T = TypeVar("T")
type Kwargs = dict[str, Any]


# fmt: off
def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]: ...
def from_dict(clazz: type[T], x: dict[Any, Any], *, field_name: str | None = None) -> T: ...
def kwargs_from_dict(target: type | Callable[..., Any], values: Mapping[str, Any], *, field_name: str = "kwargs") -> dict[str, Any]: ...
def from_kwargs(
    owner: type | Callable[..., Any], values: Mapping[str, Any], *, field_name: str | None = None
) -> dict[str, Any]: ...
def to_dict(
    x: Any, type_class: type | Callable[..., Any] | None = None, *, field_name: str | None = None
) -> dict[str, Any]: ...
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
def str_to_bool(value: str) -> bool: ...
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
    prior_fields: dict[str, FieldSpec] = {}
    for field in result:
        field_name = f"{owner_name}.{field.name}"
        metadata = metadata_from_annotations(field.annotations, field_name)
        if metadata is not None and metadata.kwargs_for is not None:
            relation_name = metadata.kwargs_for
            relation_annotation = normalize_annotation(field.annotation)
            if get_origin(relation_annotation) is not dict or get_args(relation_annotation) != (str, Any):
                raise TypeError(f"{field_name}: kwargs_for fields must be annotated as dict[str, Any] or Kwargs")
            selector = prior_fields.get(relation_name)
            if selector is None:
                raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} is not a preceding field")
            if annotation_origin(selector.annotation) is not Callable2:
                raise TypeError(f"{field_name}: kwargs_for selector {relation_name!r} must be annotated as Callable")
            field.kwargs_relation = selector
        prior_fields[field.name] = field
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


def str_to_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in ("y", "yes", "on", "1", "true", "t"):
        result = True
    elif normalized in ("n", "no", "off", "0", "false", "f"):
        result = False
    else:
        raise TypeError(f"invalid boolean value {value!r}; expected true/false, 1/0, yes/no, on/off, y/n, or t/f")
    return result


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


def enum_type(annotation: Any) -> type[Enum] | None:
    origin = annotation_origin(annotation)
    if inspect.isclass(origin) and issubclass(origin, Enum):
        result = origin
    else:
        result = None
    return result


def validate_enum_values(enum_type: type[Enum], field_name: str) -> None:
    supported_types = (str, int, float, bool)
    if any(type(member.value) not in supported_types for member in enum_type):
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

    if not (inspect.isclass(target) or inspect.isfunction(target) or inspect.ismethod(target)):
        raise TypeError(f"{target}: selected targets must be classes, functions, or methods")

    inspected_target = target.__init__ if inspect.isclass(target) else target
    try:
        hints = get_type_hints(inspected_target, include_extras=True)
    except (AttributeError, NameError, SyntaxError, TypeError) as error:
        raise TypeError(f"selected target annotations cannot be resolved: {error}") from error
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
        annotation = normalize_annotation(annotation)
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
            member = union_member(field_type, concrete_type, field_name)
            result = from_dict_value(x, member, concrete_type, field_name)
        else:
            enum_class = enum_type(field_type)
            if enum_class is not None:
                validate_enum_values(enum_class, field_name)
                if isinstance(x, enum_class):
                    result = x
                else:
                    try:
                        result = enum_class(x)
                    except ValueError as error:
                        values = [member.value for member in enum_class]
                        raise TypeError(
                            f"{field_name}: invalid {enum_class.__name__} value {x!r}; expected one of {values}"
                        ) from error
            elif origin is Callable2:
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
            if enum_class is not None or origin is Callable2:
                pass
            elif field_type is Any:
                result = x
            elif is_structured_model(field_type):
                if concrete_type is field_type:
                    result = x
                elif isinstance(x, str):
                    result = from_dict(field_type, dict_from_str(x), field_name=field_name)
                else:
                    result = from_dict(field_type, x, field_name=field_name)
            else:
                if origin is bool and isinstance(x, str):
                    result = str_to_bool(x)
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


def to_dict(
    x: Any, type_class: type | Callable[..., Any] | None = None, *, field_name: str | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    mapping = x if isinstance(x, Mapping) else None
    owner = type(x) if type_class is None else type_class
    owner_name = field_name or cast(Any, owner).__qualname__
    for f in fields_or_init_kwargs(owner):
        value = mapping[f.name] if mapping is not None and f.name in mapping else getattr(x, f.name, MISSING)
        if value is MISSING:
            continue
        if f.kwargs_relation is None:
            annotation = get_optional_type(f.annotation) or normalize_annotation(f.annotation) or type(value)
            field_name = f"{owner_name}.{f.name}"
            if annotation_origin(annotation) in (Union, UnionType):
                annotation = union_member(annotation, type(value), field_name)
            relation_owner = (
                inspect.isclass(annotation)
                and annotation.__module__ not in ("builtins", "collections.abc")
                and any(field.kwargs_relation is not None for field in fields_or_init_kwargs(annotation))
            )
            if value is not None and (is_structured_model(annotation) or relation_owner):
                result[f.name] = to_dict(value, annotation, field_name=field_name)
            else:
                result[f.name] = to_dict_value(value, annotation)
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
            serialized_values = {}
            for parameter in selected_target_fields(target):
                if parameter.name not in typed_values:
                    continue
                parameter_value = typed_values[parameter.name]
                annotation = get_optional_type(parameter.annotation) or normalize_annotation(parameter.annotation)
                parameter_name = f"{field_name}.{parameter.name}"
                if annotation_origin(annotation) in (Union, UnionType):
                    annotation = union_member(annotation, type(parameter_value), parameter_name)
                if parameter_value is not None and is_structured_model(annotation):
                    serialized_values[parameter.name] = to_dict(parameter_value, annotation, field_name=parameter_name)
                else:
                    serialized_values[parameter.name] = to_dict_value(parameter_value, annotation)
            result[f.name] = serialized_values
    return result


def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for f in fields_or_init_kwargs(clazz):
        if isinstance(x, Mapping):
            if f.name in x:
                result[f.name] = x[f.name]
        elif hasattr(x, f.name):
            result[f.name] = getattr(x, f.name)
    return result


def kwargs_from_dict(
    target: type | Callable[..., Any], values: Mapping[str, Any], *, field_name: str = "kwargs"
) -> dict[str, Any]:
    """Converts a selected target's explicit kwargs without invoking the target."""

    try:
        parameters = selected_target_fields(target)
    except TypeError as error:
        raise TypeError(f"{field_name}: {error}") from error
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name}: expected a mapping, got {type(values)}")
    parameter_names = {parameter.name for parameter in parameters}
    unknown = next((name for name in values if name not in parameter_names), None)
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


def from_kwargs(
    owner: type | Callable[..., Any], values: Mapping[str, Any], *, field_name: str | None = None
) -> dict[str, Any]:
    """Converts an owner's linked fields without invoking a function owner."""

    owner_name = field_name or cast(Any, owner).__qualname__
    if not isinstance(values, Mapping):
        raise TypeError(f"{owner_name}: expected a mapping, got {type(values)}")
    field_info = fields_or_init_kwargs(owner)
    pydantic_owner = is_pydantic_model(owner)
    result = dict(values) if pydantic_owner else {}
    converted_fields: dict[str, Any] = {}
    for f in field_info:
        dependent = next((field for field in field_info if field.kwargs_relation is f), None)
        current_field_name = f"{owner_name}.{f.name}"
        paths: list[list[str | int]] = []
        if pydantic_owner:
            alias = cast(Any, owner).model_fields[f.name].validation_alias
            if cast(Any, owner).model_config.get("validate_by_alias", True):
                if isinstance(alias, str):
                    paths = [[alias]]
                elif alias is not None:
                    aliases = alias.convert_to_aliases()
                    paths = aliases if aliases and isinstance(aliases[0], list) else [aliases]
            if alias is None or cast(Any, owner).model_config.get("validate_by_name", False):
                paths.append([f.name])
        else:
            paths = [[f.name]]
        value = MISSING
        winning_path: list[str | int] | None = None
        for path in paths:
            candidate: Any = values
            for key in path:
                if isinstance(candidate, str):
                    candidate = MISSING
                    break
                try:
                    candidate = candidate[key]
                except (KeyError, IndexError, TypeError):
                    candidate = MISSING
                    break
            if candidate is not MISSING:
                value = candidate
                winning_path = path
                break
        if f.kwargs_relation is not None:
            supplied = {} if value is MISSING else value
            if not isinstance(supplied, Mapping):
                raise TypeError(f"{current_field_name}: expected a mapping, got {type(supplied)}")
            target = converted_fields[f.kwargs_relation.name]
            try:
                parameters = selected_target_fields(target)
            except TypeError as error:
                raise TypeError(f"{current_field_name}: {error}") from error
            if any(parameter.name not in supplied for parameter in parameters):
                if f.default is not MISSING:
                    default = deepcopy(f.default)
                else:
                    default = f.default_factory() if f.default_factory is not MISSING else {}
            else:
                default = {}
            if not isinstance(default, Mapping):
                raise TypeError(f"{current_field_name}: expected a mapping default, got {type(default)}")
            merged = {**default, **supplied}
            parameter_names = {parameter.name for parameter in parameters}
            unknown = next((name for name in merged if name not in parameter_names), None)
            if unknown is not None:
                raise TypeError(f"{current_field_name}.{unknown}: unknown target parameter")
            converted = {}
            for parameter in parameters:
                if parameter.name in merged:
                    parameter_value = merged[parameter.name]
                    converted[parameter.name] = from_dict_value(
                        parameter_value,
                        parameter.annotation or type(parameter_value),
                        type(parameter_value),
                        f"{current_field_name}.{parameter.name}",
                    )
                elif parameter.default is MISSING:
                    raise TypeError(f"{current_field_name}.{parameter.name}: missing required target parameter")
            converted_fields[f.name] = converted
        elif dependent is not None:
            if value is not MISSING:
                converted = from_dict_value(value, f.annotation or type(value), type(value), current_field_name)
            elif f.default is not MISSING:
                default = deepcopy(f.default)
                converted = from_dict_value(default, f.annotation, type(default), current_field_name)
            elif f.default_factory is not MISSING:
                value = f.default_factory()
                converted = from_dict_value(value, f.annotation, type(value), current_field_name)
            else:
                raise TypeError(f"{current_field_name}: missing selector for {dependent.name!r}")
            converted_fields[f.name] = converted
        elif value is not MISSING:
            field_type = get_optional_type(f.annotation) or normalize_annotation(f.annotation) or type(value)
            if inspect.isclass(field_type) and any(
                field.kwargs_relation is not None for field in fields_or_init_kwargs(field_type)
            ):
                if isinstance(value, field_type):
                    converted = value
                else:
                    raw = dict_from_str(value) if isinstance(value, str) else value
                    converted = from_dict(field_type, raw, field_name=current_field_name)
            elif not pydantic_owner:
                converted = from_dict_value(value, f.annotation or field_type, type(value), current_field_name)
            else:
                continue
            converted_fields[f.name] = converted
        else:
            continue

        if pydantic_owner:
            path = winning_path or paths[0]
            destination: Any = result
            for index, key in enumerate(path):
                if isinstance(destination, list):
                    index_key = cast(int, key)
                    while len(destination) < (index_key + 1 if index_key >= 0 else -index_key):
                        destination.append(None)
                    destination_key: Any = index_key
                else:
                    destination_key = key
                container = cast(Any, destination)
                if index == len(path) - 1:
                    container[destination_key] = converted
                    continue
                child = (
                    container.get(destination_key) if isinstance(destination, Mapping) else container[destination_key]
                )
                if isinstance(child, Mapping):
                    child = dict(child)
                elif (
                    isinstance(path[index + 1], int)
                    and isinstance(child, Sequence)
                    and not isinstance(child, (str, bytes, bytearray))
                ):
                    child = list(child)
                else:
                    child = [] if isinstance(path[index + 1], int) else {}
                container[destination_key] = child
                destination = child
        else:
            result[f.name] = converted
    return result


def from_dict(clazz: type[T], x: dict[Any, Any], *, field_name: str | None = None) -> T:
    owner_name = field_name or clazz.__qualname__
    if any(field.kwargs_relation is not None for field in fields_or_init_kwargs(clazz)):
        values = from_kwargs(clazz, x, field_name=owner_name)
        if is_pydantic_model(clazz):
            result = cast(Any, clazz).model_validate(values)
        else:
            result = clazz(**values)
    elif is_pydantic_model(clazz):
        fields_or_init_kwargs(clazz)
        result = cast(Any, clazz).model_validate(x)
    else:
        result = clazz(
            **{
                f.name: from_dict_value(
                    x[f.name], f.annotation or type(x[f.name]), type(x[f.name]), f"{owner_name}.{f.name}"
                )
                for f in fields_or_init_kwargs(clazz)
                if f.name in x
            }
        )
    return result
