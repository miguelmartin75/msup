import inspect
import json
import os
import pkgutil
from collections.abc import Callable as Callable2, Mapping
from copy import deepcopy
from dataclasses import MISSING, dataclass, fields, is_dataclass
from enum import Enum
from functools import partial
from types import UnionType
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    TypeAliasType,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

T = TypeVar("T")
type Kwargs = dict[str, Any]
"""Keyword arguments whose effective schema comes from a selected callable."""


# fmt: off
def is_annotation_supported(annotation: Any, *, operation: Literal["type_check", "dict", "json"]) -> bool:
    """Return whether msup completely supports an annotation for one operation."""
    ...


def is_value_of_type(value: Any, annotation: Any) -> bool:
    """Return whether a Python value recursively matches an annotation without conversion."""
    ...


def to_dict(
    x: Any,
    type_class: type | Callable[..., Any] | None = None,
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Recursively encode declared fields into dictionary-form values."""
    ...


def from_dict(
    clazz: type[T],
    x: Mapping[Any, Any],
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> T:
    """Recursively decode dictionary-form values and construct a class instance."""
    ...


def to_json(
    x: Any,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
    strict: bool = False,
) -> str | None:
    """Encode a value as JSON text or write it to a JSON destination."""
    ...


def from_json(
    clazz: type[T],
    s: str | None = None,
    file_like=None,
    path: str | None = None,
    *,
    strict: bool = False,
) -> T:
    """Read JSON input, recursively decode it, and construct a class instance."""
    ...


def to_kwargs(
    target: type | Callable[..., Any],
    x: Any,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Select a target's present top-level keyword-bindable values without conversion."""
    ...


@overload
def from_kwargs(target: type[T], values: Mapping[str, Any], *, strict: bool = False) -> T:
    """Filter keyword values and construct a class exactly once."""
    ...


@overload
def from_kwargs(
    target: Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> partial[T]:
    """Filter keyword values and return a partial without invoking the callable."""
    ...


def from_kwargs(
    target: type[T] | Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> T | partial[T]:
    """Filter keyword values, then construct a class or partially bind a callable."""
    ...


def kwargs_from_dict(
    target: type | Callable[..., Any],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
    field_name: str = "kwargs",
) -> dict[str, Any]:
    """Recursively decode callable arguments without invoking or constructing the target."""
    ...


def load_callable(name: str) -> Any:
    """Load a trusted callable from its canonical module-qualified reference."""
    ...


def dump_callable(value: Any) -> str:
    """Return a canonical reference that reloads to the identical callable."""
    ...


def str_to_bool(value: str) -> bool:
    """Convert a supported textual boolean spelling or raise TypeError."""
    ...


def dict_from_str(value: str) -> dict[Any, Any]:
    """Load a dictionary from inline JSON text or a JSON file path."""
    ...
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
    """Field metadata, including an optional relation to a callable selector."""

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
    """Separate an Annotated base type from its ordered metadata values."""

    if get_origin(annotation) is Annotated:
        annotation, *annotations = get_args(annotation)
    else:
        annotations = []
    return annotation, annotations


def normalize_annotation(annotation: Any) -> Any:
    """Remove Annotated metadata and unwrap one runtime type alias."""

    annotation, _ = unwrap_annotated(annotation)
    return annotation.__value__ if isinstance(annotation, TypeAliasType) else annotation


def metadata_from_annotations(annotations: list[Any], field_name: str = "") -> Metadata | None:
    """Return the sole Metadata annotation and reject duplicates."""

    metadata = [value for value in annotations if isinstance(value, Metadata)]
    if len(metadata) > 1:
        prefix = f"{field_name}: " if field_name else ""
        raise TypeError(f"{prefix}an annotation can contain at most one CliArg or Metadata")
    result = metadata[0] if metadata else None
    return result


def is_pydantic_model(candidate: type | object) -> bool:
    """Return whether a candidate is a supported Pydantic v2 model or instance."""

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
    """Return whether a candidate is a dataclass or supported Pydantic model."""

    return is_dataclass(candidate) or is_pydantic_model(candidate)


def from_json(clazz: type[T], s: str | None = None, file_like=None, path: str | None = None) -> T:
    """Read JSON input, recursively decode it, and construct a class instance."""

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
    """Encode a value as JSON text or write it to a JSON destination."""

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
    """Return whether a reflected field declares a value or factory default."""

    return f.default is not MISSING or f.default_factory is not MISSING


def fields_or_init_kwargs(target: type | Callable[..., Any]) -> list[FieldSpec]:
    """Reflect declared model fields or explicit callable parameters and relations."""

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
    if is_pydantic_model(target):
        model_fields = cast(Any, target).model_fields
        for field in result:
            relation = field.kwargs_relation
            if relation is not None and (
                model_fields[field.name].validation_alias is not None
                or model_fields[relation.name].validation_alias is not None
            ):
                raise TypeError(f"{owner_name}.{field.name}: kwargs_for fields do not support validation aliases")
    return result


def contains_relation(owner: type | Callable[..., Any]) -> bool:
    """Return whether a reflected owner has a field linked to a selector."""

    return any(field.kwargs_relation is not None for field in fields_or_init_kwargs(owner))


def load_callable(name: str) -> Any:
    """Load a trusted callable from its canonical module-qualified reference."""
    return pkgutil.resolve_name(name)


def dump_callable(value: Any) -> str:
    """Return a canonical reference that reloads to the identical callable."""

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
    """Convert a supported textual boolean spelling or raise TypeError."""

    normalized = value.lower()
    if normalized in ("y", "yes", "on", "1", "true", "t"):
        result = True
    elif normalized in ("n", "no", "off", "0", "false", "f"):
        result = False
    else:
        raise TypeError(f"invalid boolean value {value!r}; expected true/false, 1/0, yes/no, on/off, y/n, or t/f")
    return result


def maybe_idx(xs: tuple[Any, ...] | list[Any], idx: int, default: Any = None) -> Any:
    """Return an indexed item or a default when the index is past the end."""

    return xs[idx] if idx < len(xs) else default


def get_optional_type(annotation: Any) -> Any | None:
    """Return the non-None member of an optional annotation, if present."""

    annotation, _ = unwrap_annotated(annotation)
    args = get_args(annotation)
    if get_origin(annotation) in (Union, UnionType) and len(args) == 2 and type(None) in args:
        result = next(arg for arg in args if arg is not type(None))
    else:
        result = None
    return result


def get_collection_args(annotation: Any, count: int = 0) -> tuple[Any, ...]:
    """Return normalized key or item annotations for a supported collection."""

    annotation, _ = unwrap_annotated(annotation)
    origin = annotation_origin(annotation)
    args = get_args(annotation)
    if origin is dict:
        result = (maybe_idx(args, 0, Any), maybe_idx(args, 1, Any))
    elif origin in (list, set):
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
    """Return whether an annotation is a two-member union with None."""

    return get_optional_type(annotation) is not None


def annotation_origin(annotation: Any) -> Any:
    """Return an annotation's runtime origin after removing Annotated metadata."""

    annotation, _ = unwrap_annotated(annotation)
    return get_origin(annotation) or annotation


def effective_type(annotation: Any, field_name: str) -> Any:
    """Return a CLI annotation with optionality removed and reject other unions."""

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
    """Select the single best union member for a coercive source type."""

    candidates = []
    for member in get_args(annotation):
        if member is type(None):
            continue
        optional_type = get_optional_type(member)
        if concrete_type is type(None):
            compatible = optional_type is not None
        elif optional_type is not None:
            try:
                union_member(member, concrete_type, field_name)
            except TypeError:
                compatible = False
            else:
                compatible = True
        else:
            origin = annotation_origin(member)
            concrete_origin = annotation_origin(concrete_type)
            if origin in (Union, UnionType):
                try:
                    union_member(member, concrete_type, field_name)
                except TypeError:
                    compatible = False
                else:
                    compatible = True
            elif member is Any:
                compatible = True
            elif (enum_class := enum_type(member)) is not None:
                validate_enum_values(enum_class, field_name)
                compatible = concrete_origin is enum_class or any(
                    type(enum_member.value) is concrete_origin for enum_member in enum_class
                )
            elif is_structured_model(member):
                compatible = concrete_origin in (member, dict, str)
            elif origin is dict:
                compatible = concrete_origin in (dict, str)
            elif origin in (list, tuple):
                compatible = concrete_origin in (list, tuple)
            elif origin is Callable2:
                compatible = concrete_origin is str
            elif origin in (int, float, bool, str) and concrete_origin in (int, float, bool, str):
                compatible = True
            else:
                compatible = origin is concrete_origin
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
    """Return the Enum subclass represented by an annotation, if any."""

    origin = annotation_origin(annotation)
    if inspect.isclass(origin) and issubclass(origin, Enum):
        result = origin
    else:
        result = None
    return result


def validate_enum_values(enum_type: type[Enum], field_name: str) -> None:
    """Reject enums whose values cannot use msup's scalar representation."""

    supported_types = (str, int, float, bool)
    if any(type(member.value) not in supported_types for member in enum_type):
        raise TypeError(f"{field_name}: {enum_type.__name__} values must be str, int, float, or bool")


def is_annotation_supported(
    annotation: Any,
    *,
    operation: Literal["type_check", "dict", "json"],
) -> bool:
    """Return whether msup completely supports an annotation for one operation."""

    if operation not in ("type_check", "dict", "json"):
        raise ValueError(f"unknown annotation operation: {operation}")

    def check(current: Any, visiting: set[Any]) -> bool:
        current = normalize_annotation(current)
        origin = annotation_origin(current)
        if current in visiting:
            result = True
        elif current is Any:
            result = operation != "json"
        elif current is type(None):
            result = True
        elif origin in (Union, UnionType):
            result = all(check(member, visiting) for member in get_args(current))
        elif origin is dict:
            key_type, value_type = get_collection_args(current)
            if operation == "json":
                result = key_type is str and check(value_type, visiting)
            else:
                result = check(key_type, visiting) and check(value_type, visiting)
        elif origin in (list, tuple, set):
            args = get_args(current)
            if not args:
                item_types = (Any,)
            elif origin is tuple and len(args) == 2 and args[1] is Ellipsis:
                item_types = (args[0],)
            else:
                item_types = args
            result = (operation == "type_check" or origin is not set) and all(
                check(item, visiting) for item in item_types
            )
        elif origin in (int, float, str, bool, Callable2):
            result = True
        elif (enum_class := enum_type(current)) is not None:
            if operation == "type_check":
                result = True
            else:
                scalar_types = (str, int, float, bool)
                result = all(type(member.value) in scalar_types for member in enum_class)
        else:
            if is_structured_model(current):
                if operation == "type_check":
                    result = True
                else:
                    visiting.add(current)
                    result = all(
                        field.kwargs_relation is not None
                        or (field.annotation is not None and check(field.annotation, visiting))
                        for field in fields_or_init_kwargs(current)
                    )
                    visiting.remove(current)
            elif operation == "type_check" and inspect.isclass(origin):
                result = True
            else:
                result = False
        return result

    return check(annotation, set())


def is_value_of_type(value: Any, annotation: Any) -> bool:
    """Return whether a Python value recursively matches an annotation without conversion."""

    annotation = normalize_annotation(annotation)
    if not is_annotation_supported(annotation, operation="type_check"):
        result = False
    elif annotation is Any:
        result = True
    elif annotation is type(None):
        result = value is None
    else:
        origin = annotation_origin(annotation)
        optional_type = get_optional_type(annotation)
        if optional_type is not None:
            result = value is None or is_value_of_type(value, optional_type)
        elif origin in (Union, UnionType):
            result = any(is_value_of_type(value, member) for member in get_args(annotation))
        elif (enum_class := enum_type(annotation)) is not None:
            result = isinstance(value, enum_class)
        elif origin is Callable2:
            result = callable(value)
        elif origin in (int, float, str, bool):
            result = type(value) is origin
        elif origin is dict:
            key_type, value_type = get_collection_args(annotation)
            result = isinstance(value, dict) and all(
                is_value_of_type(key, key_type) and is_value_of_type(item, value_type) for key, item in value.items()
            )
        elif origin is list:
            (item_type,) = get_collection_args(annotation)
            result = isinstance(value, list) and all(is_value_of_type(item, item_type) for item in value)
        elif origin is set:
            args = get_args(annotation)
            item_type = maybe_idx(args, 0, Any)
            result = isinstance(value, set) and all(is_value_of_type(item, item_type) for item in value)
        elif origin is tuple:
            args = get_args(annotation)
            if not isinstance(value, tuple):
                result = False
            elif not args:
                result = True
            elif len(args) == 2 and args[1] is Ellipsis:
                result = all(is_value_of_type(item, args[0]) for item in value)
            else:
                item_types = get_collection_args(annotation)
                result = len(value) == len(item_types) and all(
                    is_value_of_type(item, item_types[index]) for index, item in enumerate(value)
                )
        elif is_structured_model(annotation):
            result = isinstance(value, annotation)
        else:
            result = isinstance(value, origin)
    return result


def selected_target_fields(target: type | Callable[..., Any]) -> list[FieldSpec]:
    """Reflect a selected target's explicit keyword-capable signature without invoking it."""

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
            annotation = None
            annotations = []
        else:
            annotation, annotations = unwrap_annotated(annotation)
            annotation = normalize_annotation(annotation)
        default = MISSING if parameter.default is inspect._empty else parameter.default
        result.append(FieldSpec(name, annotation, annotations, default, MISSING))

    prior_fields: dict[str, FieldSpec] = {}
    for field in result:
        field_name = f"{target.__qualname__}.{field.name}"
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


def validate_selected_mapping(
    parameters: list[FieldSpec],
    values: Mapping[str, Any],
    field_name: str,
) -> None:
    """Validate selected argument names and required parameters without rewriting values."""

    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name}: expected a mapping, got {type(values)}")
    parameter_names = {parameter.name for parameter in parameters}
    unknown = next((name for name in values if name not in parameter_names), None)
    if unknown is not None:
        raise TypeError(f"{field_name}.{unknown}: unknown target parameter")
    missing = next(
        (parameter.name for parameter in parameters if parameter.name not in values and parameter.default is MISSING),
        None,
    )
    if missing is not None:
        raise TypeError(f"{field_name}.{missing}: missing required target parameter")


def dict_from_str(x: str) -> dict[Any, Any]:
    """Load a dictionary from inline JSON text or a JSON file path."""

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
    """Recursively decode one dictionary-form value according to its annotation."""

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
                concrete_origin = annotation_origin(concrete_type)
                if field_type is Any:
                    compatible = True
                elif is_structured_model(field_type):
                    compatible = concrete_origin in (field_type, dict, str)
                elif origin is dict:
                    compatible = concrete_origin in (dict, str)
                elif origin in (list, tuple):
                    compatible = concrete_origin in (list, tuple)
                elif origin in (int, float, bool, str) and concrete_origin in (int, float, bool, str):
                    compatible = True
                else:
                    compatible = origin is concrete_origin
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


def to_dict_value(x: Any, field_type: Any, field_name: str = "value") -> Any:
    """Recursively encode one Python value and qualify failures with its field path."""

    try:
        origin = annotation_origin(field_type)
        optional_type = get_optional_type(field_type)
        if x is None:
            result = None
        elif optional_type is not None:
            result = to_dict_value(x, optional_type, field_name)
        elif origin in (Union, UnionType):
            result = to_dict_value(x, union_member(field_type, type(x), field_name), field_name)
        elif field_type is Any:
            result = x
        elif (enum_class := enum_type(field_type)) is not None:
            validate_enum_values(enum_class, field_name)
            if not isinstance(x, enum_class):
                raise TypeError(f"{field_name}: expected {enum_class.__name__} value, got {type(x)}")
            result = x.value
        elif is_structured_model(x):
            result = to_dict(x, field_name=field_name)
        elif origin is dict:
            key_type, value_type = get_collection_args(field_type)
            result = {
                to_dict_value(key, key_type, f"{field_name}.key"): to_dict_value(
                    value, value_type, f"{field_name}.value"
                )
                for key, value in x.items()
            }
        elif origin in (list, tuple):
            item_types = get_collection_args(field_type, len(x))
            values = [
                to_dict_value(
                    item,
                    item_types[index] if index < len(item_types) else Any,
                    f"{field_name}[{index}]",
                )
                for index, item in enumerate(x)
            ]
            result = tuple(values) if isinstance(x, tuple) else values
        elif origin is Callable2:
            if not callable(x):
                raise TypeError(f"{field_name}: expected callable value for {field_type}, got {type(x)}")
            result = dump_callable(x)
        elif origin in (int, float, str, bool):
            result = origin(x)
        else:
            result = x
    except (TypeError, ValueError) as error:
        message = str(error)
        qualified_prefixes = (f"{field_name}:", f"{field_name}.", f"{field_name}[")
        if message.startswith(qualified_prefixes):
            raise
        raise type(error)(f"{field_name}: {message}") from error
    return result


def to_dict(
    x: Any, type_class: type | Callable[..., Any] | None = None, *, field_name: str | None = None
) -> dict[str, Any]:
    """Recursively encode declared fields into dictionary-form values."""

    result: dict[str, Any] = {}
    mapping = x if isinstance(x, Mapping) else None
    owner = type(x) if type_class is None else type_class
    owner_name = field_name or cast(Any, owner).__qualname__
    selected_fields: dict[str, list[FieldSpec]] = {}
    for f in fields_or_init_kwargs(owner):
        value = mapping[f.name] if mapping is not None and f.name in mapping else getattr(x, f.name, MISSING)
        if value is MISSING:
            continue
        if f.kwargs_relation is None:
            if f.annotation is not Any and is_structured_model(value):
                result[f.name] = to_dict(value, field_name=f"{owner_name}.{f.name}")
            else:
                result[f.name] = to_dict_value(value, f.annotation or type(value), f"{owner_name}.{f.name}")
        else:
            target = (
                mapping.get(f.kwargs_relation.name, MISSING)
                if mapping is not None
                else getattr(x, f.kwargs_relation.name, MISSING)
            )
            field_name = f"{owner_name}.{f.name}"
            if target is MISSING:
                raise TypeError(f"{field_name}: missing selector {f.kwargs_relation.name!r}")
            parameters = selected_fields.get(f.kwargs_relation.name)
            if parameters is None:
                parameters = selected_fields[f.kwargs_relation.name] = selected_target_fields(target)
            validate_selected_mapping(parameters, value, field_name)
            converted = {}
            for parameter in parameters:
                if parameter.name in value:
                    raw = value[parameter.name]
                    annotation = parameter.annotation or type(raw)
                    converted[parameter.name] = (
                        to_dict(raw, field_name=f"{field_name}.{parameter.name}")
                        if is_structured_model(raw)
                        else to_dict_value(raw, annotation, f"{field_name}.{parameter.name}")
                    )
            result[f.name] = converted
    return result


def to_kwargs(clazz: type | Callable[..., Any], x: Any) -> dict[str, Any]:
    """Select a target's present top-level keyword-bindable values without conversion."""

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
        validate_selected_mapping(parameters, values, field_name)
    relation_names = {
        parameter.kwargs_relation.name for parameter in parameters if parameter.kwargs_relation is not None
    }
    validation_values = dict(values)
    for parameter in parameters:
        if parameter.kwargs_relation is not None or parameter.name in relation_names:
            validation_values.setdefault(parameter.name, MISSING)
    validate_selected_mapping(parameters, validation_values, field_name)
    result: dict[str, Any] = {}
    selectors: dict[str, tuple[Any, list[FieldSpec]]] = {}
    for parameter in parameters:
        current_field_name = f"{field_name}.{parameter.name}"
        value = values.get(parameter.name, MISSING)
        if parameter.kwargs_relation is not None:
            supplied = {} if value is MISSING else value
            if not isinstance(supplied, Mapping):
                raise TypeError(f"{current_field_name}: expected a mapping, got {type(supplied)}")
            relation = parameter.kwargs_relation
            if relation.name not in selectors:
                selected_target = values.get(relation.name, MISSING)
                if selected_target is MISSING:
                    if relation.default is MISSING:
                        raise TypeError(f"{field_name}.{relation.name}: missing selector")
                    selected_target = deepcopy(relation.default)
                selected_target = from_dict_value(
                    selected_target,
                    relation.annotation,
                    type(selected_target),
                    f"{field_name}.{relation.name}",
                )
                try:
                    selected_parameters = selected_target_fields(selected_target)
                except TypeError as error:
                    raise TypeError(f"{current_field_name}: {error}") from error
                selectors[relation.name] = selected_target, selected_parameters
                result[relation.name] = selected_target
            _, selected_parameters = selectors[relation.name]
            if any(selected_parameter.name not in supplied for selected_parameter in selected_parameters):
                default = deepcopy(parameter.default) if parameter.default is not MISSING else {}
            else:
                default = {}
            if not isinstance(default, Mapping):
                raise TypeError(f"{current_field_name}: expected a mapping default, got {type(default)}")
            merged = {**default, **supplied}
            validate_selected_mapping(selected_parameters, merged, current_field_name)
            converted = {}
            for selected_parameter in selected_parameters:
                if selected_parameter.name in merged:
                    selected_value = merged[selected_parameter.name]
                    converted[selected_parameter.name] = from_dict_value(
                        selected_value,
                        selected_parameter.annotation if selected_parameter.annotation is not None else Any,
                        type(selected_value),
                        f"{current_field_name}.{selected_parameter.name}",
                    )
            result[parameter.name] = converted
        elif value is not MISSING:
            value = values[parameter.name]
            result[parameter.name] = from_dict_value(
                value,
                parameter.annotation if parameter.annotation is not None else Any,
                type(value),
                current_field_name,
            )
    validate_selected_mapping(parameters, {**values, **result}, field_name)
    return result


def from_kwargs(
    owner: type | Callable[..., Any],
    values: Mapping[str, Any],
    *,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Temporarily delegate recursive callable argument decoding without invocation."""

    return kwargs_from_dict(owner, values, field_name=field_name or cast(Any, owner).__qualname__)


def from_dict(clazz: type[T], x: dict[Any, Any], *, field_name: str | None = None) -> T:
    """Recursively decode dictionary-form values and construct a class instance."""

    owner_name = field_name or clazz.__qualname__
    if contains_relation(clazz):
        if not isinstance(x, Mapping):
            raise TypeError(f"{owner_name}: expected a mapping, got {type(x)}")
        field_info = fields_or_init_kwargs(clazz)
        pydantic_owner = is_pydantic_model(clazz)
        values: dict[str, Any] = deepcopy(dict(x)) if pydantic_owner else {}
        selectors: dict[str, tuple[Any, list[FieldSpec]]] = {}
        for f in field_info:
            current_field_name = f"{owner_name}.{f.name}"
            value = x.get(f.name, MISSING)
            if f.kwargs_relation is not None:
                supplied = {} if value is MISSING else value
                if not isinstance(supplied, Mapping):
                    raise TypeError(f"{current_field_name}: expected a mapping, got {type(supplied)}")
                relation = f.kwargs_relation
                if relation.name not in selectors:
                    target = x.get(relation.name, MISSING)
                    if target is MISSING:
                        if relation.default is not MISSING:
                            target = deepcopy(relation.default)
                        elif relation.default_factory is not MISSING:
                            target = relation.default_factory()
                        else:
                            raise TypeError(f"{owner_name}.{relation.name}: missing selector")
                    target = from_dict_value(target, relation.annotation, type(target), f"{owner_name}.{relation.name}")
                    try:
                        parameters = selected_target_fields(target)
                    except TypeError as error:
                        raise TypeError(f"{current_field_name}: {error}") from error
                    selectors[relation.name] = target, parameters
                    values[relation.name] = target
                _, parameters = selectors[relation.name]
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
                validate_selected_mapping(parameters, merged, current_field_name)
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
            elif value is not MISSING:
                field_type = get_optional_type(f.annotation) or normalize_annotation(f.annotation) or type(value)
                if inspect.isclass(field_type) and contains_relation(field_type):
                    if isinstance(value, field_type):
                        converted = value
                    else:
                        raw = dict_from_str(value) if isinstance(value, str) else value
                        converted = from_dict(field_type, cast(dict[Any, Any], raw), field_name=current_field_name)
                elif not pydantic_owner:
                    converted = from_dict_value(value, f.annotation or field_type, type(value), current_field_name)
                else:
                    continue
            else:
                continue
            values[f.name] = converted
        if pydantic_owner:
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
