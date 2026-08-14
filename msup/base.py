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
"""Keyword arguments described by a callable named in a related selector field."""


# fmt: off
def is_annotation_supported(annotation: Any, *, operation: Literal["type_check", "dict", "json"]) -> bool:
    """Return whether msup fully handles an annotation under the requested rules.

    ``type_check`` checks Python values without changing them. ``dict`` checks
    reading and writing dictionary-form values. ``json`` checks whether every
    value allowed by the annotation has one canonical JSON form that can be read
    back without loss. It is narrower than ``dict``: dictionary keys must be
    strings, and ``Any`` is not supported. The operation chooses these support
    rules; it does not request encoding or decoding. An unknown operation raises
    ``ValueError``.
    """
    ...


def is_value_of_type(value: Any, annotation: Any) -> bool:
    """Return whether a Python value and all nested values fit an annotation without conversion."""
    ...


def to_dict(
    x: Any,
    type_class: type | Callable[..., Any] | None = None,
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Convert present declared fields and nested values into a dictionary.

    By default, supported type conversions are applied and an unsupported value
    may pass through only when it already fits its full annotation.
    ``strict=True`` rejects unsupported annotations and values that do not
    already have the declared Python types. The function never fills missing
    fields.
    """
    ...


def from_dict(
    clazz: type[T],
    x: Mapping[Any, Any],
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> T:
    """Decode a mapping's nested values and construct one class instance.

    By default, supported type conversions are applied and an unsupported value
    may pass through only when it already fits its full annotation.
    ``strict=True`` rejects unsupported annotations and input values in the
    wrong encoded type. Missing constructor arguments remain the class's
    responsibility.
    """
    ...


def to_json(
    x: Any,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
    strict: bool = False,
) -> str | None:
    """Convert a value to JSON text, or write it and return ``None``.

    By default, supported type conversions are applied before JSON writing.
    ``strict=True`` rejects unsupported annotations and Python values that do
    not already match them. ``file_like`` may be an open destination or a JSON
    file path.
    """
    ...


def from_json(
    clazz: type[T],
    s: str | None = None,
    file_like=None,
    path: str | None = None,
    *,
    strict: bool = False,
) -> T:
    """Read JSON, decode its nested values, and construct one class instance.

    Input may come from ``s``, ``file_like``, or ``path``. By default, supported
    type conversions are applied. ``strict=True`` rejects unsupported
    annotations and input values in the wrong encoded type.
    """
    ...


def to_kwargs(
    target: type | Callable[..., Any],
    x: Any,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Copy present top-level values that ``target`` accepts by keyword.

    Nested values are not converted or copied, and missing values and defaults
    are not filled. ``strict=True`` checks each copied value against its
    annotation.
    """
    ...


@overload
def from_kwargs(target: type[T], values: Mapping[str, Any], *, strict: bool = False) -> T:
    """Filter keyword values and construct ``target`` exactly once.

    ``strict=True`` checks copied values without converting them.
    """
    ...


@overload
def from_kwargs(
    target: Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> partial[T]:
    """Filter keyword values and return a partial without calling ``target``.

    ``strict=True`` checks copied values without converting them. Missing
    required arguments and callable defaults remain open for the later call.
    """
    ...


def from_kwargs(
    target: type[T] | Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> T | partial[T]:
    """Construct a class once or return a partial without calling a callable.

    Only present top-level keyword values are used. ``strict=True`` checks them
    without converting them.
    """
    ...


def kwargs_from_dict(
    target: type | Callable[..., Any],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
    field_name: str = "kwargs",
) -> dict[str, Any]:
    """Decode a callable's nested argument values without running the target.

    Unknown and missing required arguments are rejected. ``strict=True``
    rejects unsupported annotations and input values in the wrong encoded type.
    A class is not constructed and a function or method is not called.
    """
    ...


def load_callable(name: str) -> Any:
    """Load a trusted callable from its fully qualified import name.

    Only use names from a trusted source because importing can run code.
    """
    ...


def dump_callable(value: Any) -> str:
    """Return the canonical module-qualified name for the same callable.

    A value that cannot be imported by that name raises ``TypeError``.
    """
    ...


def str_to_bool(value: str) -> bool:
    """Convert a supported true or false spelling, or raise ``TypeError``."""
    ...


def dict_from_str(value: str) -> dict[Any, Any]:
    """Read a dictionary from inline JSON or a path ending in ``.json``."""
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
    """Extra field settings, including an optional link to a callable selector."""

    kwargs_for: str | None = None


@dataclass
class FieldSpec:
    """Description of a field or parameter found by inspecting its owner.

    When the field uses ``kwargs_for``, ``kwargs_relation`` points to the
    earlier field that selects the callable.
    """

    name: str
    annotation: Any
    annotations: list[Any]
    default: Any = MISSING
    default_factory: Any = MISSING
    kwargs_relation: "FieldSpec | None" = None


@dataclass(frozen=True)
class ConversionAttempt:
    """Result of trying a conversion without raising a conversion error.

    ``error`` is ``None`` on success. When it is set, ``value`` must not be
    used.
    """

    value: Any = None
    error: Exception | None = None


def unwrap_annotated(annotation: Any) -> tuple[Any, list[Any]]:
    """Return an ``Annotated`` value's base type and ordered metadata.

    Other annotations are returned unchanged with an empty metadata list.
    """

    if get_origin(annotation) is Annotated:
        annotation, *annotations = get_args(annotation)
    else:
        annotations = []
    return annotation, annotations


def normalize_annotation(annotation: Any) -> Any:
    """Remove ``Annotated`` metadata and unwrap one runtime type alias."""

    annotation, _ = unwrap_annotated(annotation)
    return annotation.__value__ if isinstance(annotation, TypeAliasType) else annotation


def metadata_from_annotations(annotations: list[Any], field_name: str = "") -> Metadata | None:
    """Return the only ``Metadata`` item, or ``None`` when there is no item.

    More than one item raises ``TypeError``.
    """

    metadata = [value for value in annotations if isinstance(value, Metadata)]
    if len(metadata) > 1:
        prefix = f"{field_name}: " if field_name else ""
        raise TypeError(f"{prefix}an annotation can contain at most one CliArg or Metadata")
    result = metadata[0] if metadata else None
    return result


def is_pydantic_model(candidate: type | object) -> bool:
    """Return whether a class or instance is a supported Pydantic v2 model.

    A Pydantic v1 model raises ``TypeError``.
    """

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
    """Return whether a class or instance is a dataclass or Pydantic v2 model.

    A Pydantic v1 model raises ``TypeError``.
    """

    return is_dataclass(candidate) or is_pydantic_model(candidate)


def from_json(
    clazz: type[T],
    s: str | None = None,
    file_like=None,
    path: str | None = None,
    *,
    strict: bool = False,
) -> T:
    """Read JSON, decode its nested values, and construct one class instance.

    Input may come from ``s``, ``file_like``, or ``path``. By default, supported
    type conversions are applied. ``strict=True`` rejects unsupported
    annotations and input values in the wrong encoded type.
    """

    if path:
        assert os.path.exists(path), f"{path} does not exist"
        with open(path) as in_f:
            result = cast(T, from_dict_operation(clazz, json.load(in_f), strict=strict, operation="json"))
    elif file_like:
        result = cast(T, from_dict_operation(clazz, json.load(file_like), strict=strict, operation="json"))
    else:
        assert s is not None, "s must be provided when file_like and path are absent"
        result = cast(T, from_dict_operation(clazz, json.loads(s), strict=strict, operation="json"))
    return result


def to_json(
    x: Any,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
    strict: bool = False,
) -> str | None:
    """Convert a value to JSON text, or write it and return ``None``.

    By default, supported type conversions are applied before JSON writing.
    ``strict=True`` rejects unsupported annotations and Python values that do
    not already match them. ``file_like`` may be an open destination or a JSON
    file path.
    """

    value = to_dict_operation(x, type_class, strict=strict, operation="json")
    if file_like:
        if isinstance(file_like, str):
            assert file_like.endswith(".json"), f"file should end with json, got: {file_like}"
            parent = os.path.dirname(file_like)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(file_like, "w") as out_f:
                json.dump(value, out_f, indent=indent)
        else:
            json.dump(value, file_like, indent=indent)
        result = None
    else:
        result = json.dumps(value, indent=indent)
    return result


def has_default_value(f: FieldSpec) -> bool:
    """Return whether a field has a fixed default or a default factory."""

    return f.default is not MISSING or f.default_factory is not MISSING


def materialize_default(f: FieldSpec, fallback: Any = MISSING) -> Any:
    """Copy a fixed default, call a default factory once, or return ``fallback``."""

    if f.default is not MISSING:
        result = deepcopy(f.default)
    elif f.default_factory is not MISSING:
        result = f.default_factory()
    else:
        result = fallback
    return result


def fields_or_init_kwargs(target: type | Callable[..., Any], *, selected: bool = False) -> list[FieldSpec]:
    """Inspect a model's fields or a callable's named parameters.

    The result includes defaults, annotations, and ``kwargs_for`` links. With
    ``selected=True``, parameters that cannot be passed by keyword are rejected.
    The target is never constructed or called.
    """

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
        try:
            hints = get_type_hints(inspected_target, include_extras=True)
        except (AttributeError, NameError, SyntaxError, TypeError) as error:
            if selected:
                raise TypeError(f"selected target annotations cannot be resolved: {error}") from error
            raise
        for name, parameter in inspect.signature(inspected_target).parameters.items():
            if selected and parameter.kind is parameter.POSITIONAL_ONLY:
                raise TypeError(f"{name}: selected target parameters cannot be positional-only")
            elif selected and parameter.kind is parameter.VAR_POSITIONAL:
                raise TypeError(f"{name}: selected target parameters cannot use *args")
            elif selected and parameter.kind is parameter.VAR_KEYWORD:
                raise TypeError(f"{name}: selected target parameters cannot use **kwargs")
            elif name in ("self", "cls") and (inspect.isclass(target) or not selected):
                continue
            elif parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
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
    """Return whether an inspected field uses ``kwargs_for``."""

    return any(field.kwargs_relation is not None for field in fields_or_init_kwargs(owner))


def load_callable(name: str) -> Any:
    """Load a trusted callable from its fully qualified import name.

    Only use names from a trusted source because importing can run code.
    """

    return pkgutil.resolve_name(name)


def dump_callable(value: Any) -> str:
    """Return the canonical module-qualified name for the same callable.

    A value that cannot be imported by that name raises ``TypeError``.
    """

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
    """Convert a supported true or false spelling, or raise ``TypeError``."""

    normalized = value.lower()
    if normalized in ("y", "yes", "on", "1", "true", "t"):
        result = True
    elif normalized in ("n", "no", "off", "0", "false", "f"):
        result = False
    else:
        raise TypeError(f"invalid boolean value {value!r}; expected true/false, 1/0, yes/no, on/off, y/n, or t/f")
    return result


def maybe_idx(xs: tuple[Any, ...] | list[Any], idx: int, default: Any = None) -> Any:
    """Return an item by index, or ``default`` when the index is past the end."""

    return xs[idx] if idx < len(xs) else default


def get_optional_type(annotation: Any) -> Any | None:
    """Return the non-``None`` type from an optional annotation, if present."""

    annotation, _ = unwrap_annotated(annotation)
    args = get_args(annotation)
    if get_origin(annotation) in (Union, UnionType) and len(args) == 2 and type(None) in args:
        result = next(arg for arg in args if arg is not type(None))
    else:
        result = None
    return result


def get_collection_args(annotation: Any, count: int = 0) -> tuple[Any, ...]:
    """Return the key or item types declared by a supported collection.

    ``count`` repeats the item type for a plain or variable-length collection.
    """

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
    """Return whether an annotation is a two-type union containing ``None``."""

    return get_optional_type(annotation) is not None


def annotation_origin(annotation: Any) -> Any:
    """Return the runtime type behind an annotation after removing metadata."""

    annotation, _ = unwrap_annotated(annotation)
    return get_origin(annotation) or annotation


def effective_type(annotation: Any, field_name: str) -> Any:
    """Remove ``None`` from an optional CLI type.

    Other union types raise ``TypeError`` because the CLI cannot choose one.
    """

    annotation, _ = unwrap_annotated(annotation)
    optional_type = get_optional_type(annotation)
    if optional_type is not None:
        result = optional_type
    elif annotation_origin(annotation) in (Union, UnionType):
        raise TypeError(f"{field_name}: non-optional union annotations are not supported by the CLI: {annotation}")
    else:
        result = annotation
    return result


def attempt_union_member(annotation: Any, concrete_type: type, field_name: str = "value") -> ConversionAttempt:
    """Try to choose one union type that can read ``concrete_type``.

    The returned attempt contains an error when no type matches or the choice is
    ambiguous.
    """

    candidates = []
    concrete_origin = annotation_origin(concrete_type)
    scalar_origins = (int, float, bool, str)
    coercive_sources = {
        dict: (dict, str),
        list: (list, tuple),
        tuple: (list, tuple),
        Callable2: (str,),
        type(None): (type(None),),
        int: scalar_origins,
        float: scalar_origins,
        bool: scalar_origins,
        str: scalar_origins,
    }
    for member in get_args(annotation):
        origin = annotation_origin(member)
        if origin in (Union, UnionType):
            compatible = attempt_union_member(member, concrete_type, field_name).error is None
        elif member is Any:
            compatible = True
        elif (enum_class := enum_type(member)) is not None:
            if any(type(enum_member.value) not in (str, int, float, bool) for enum_member in enum_class):
                return ConversionAttempt(
                    error=TypeError(f"{field_name}: {enum_class.__name__} values must be str, int, float, or bool")
                )
            else:
                compatible = concrete_origin is enum_class or any(
                    type(enum_member.value) is concrete_origin for enum_member in enum_class
                )
        else:
            compatible_sources = (member, dict, str) if is_structured_model(member) else coercive_sources.get(origin)
            compatible = (
                concrete_origin in compatible_sources if compatible_sources is not None else origin is concrete_origin
            )
        if compatible:
            candidates.append(member)

    exact = [member for member in candidates if annotation_origin(member) is concrete_type]
    if len(exact) == 1:
        result = ConversionAttempt(exact[0])
    elif len(candidates) == 1:
        result = ConversionAttempt(candidates[0])
    elif not candidates:
        result = ConversionAttempt(
            error=TypeError(f"{field_name}: {annotation} cannot be converted from {concrete_type}")
        )
    else:
        result = ConversionAttempt(
            error=TypeError(f"{field_name}: ambiguous conversion from {concrete_type} to {annotation}: {candidates}")
        )
    return result


def union_member(annotation: Any, concrete_type: type, field_name: str = "value") -> Any:
    """Choose one union type that can read ``concrete_type``.

    Raise ``TypeError`` when no type matches or the choice is ambiguous.
    """

    attempt = attempt_union_member(annotation, concrete_type, field_name)
    if attempt.error is not None:
        raise attempt.error
    return attempt.value


def enum_type(annotation: Any) -> type[Enum] | None:
    """Return the ``Enum`` class named by an annotation, if there is one."""

    origin = annotation_origin(annotation)
    if inspect.isclass(origin) and issubclass(origin, Enum):
        result = origin
    else:
        result = None
    return result


def validate_enum_values(enum_type: type[Enum], field_name: str) -> None:
    """Reject an enum unless every value has exact type ``str``, ``int``, ``float``, or ``bool``."""

    supported_types = (str, int, float, bool)
    if any(type(member.value) not in supported_types for member in enum_type):
        raise TypeError(f"{field_name}: {enum_type.__name__} values must be str, int, float, or bool")


def is_annotation_supported(
    annotation: Any,
    *,
    operation: Literal["type_check", "dict", "json"],
) -> bool:
    """Return whether msup fully handles an annotation under the requested rules.

    ``type_check`` checks Python values without changing them. ``dict`` checks
    reading and writing dictionary-form values. ``json`` checks whether every
    value allowed by the annotation has one canonical JSON form that can be read
    back without loss. It is narrower than ``dict``: dictionary keys must be
    strings, and ``Any`` is not supported. The operation chooses these support
    rules; it does not request encoding or decoding. An unknown operation raises
    ``ValueError``.
    """

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
            elif args == (args[0], Ellipsis):
                item_types = (args[0],)
            else:
                item_types = args
            result = (operation == "type_check" or origin is not set) and all(
                check(item, visiting) for item in item_types
            )
        elif origin in (int, float, str, bool, Callable2):
            result = True
        elif (enum_class := enum_type(current)) is not None:
            result = operation == "type_check" or all(
                type(member.value) in (str, int, float, bool) for member in enum_class
            )
        elif not is_structured_model(current):
            result = operation == "type_check" and inspect.isclass(origin)
        elif operation == "type_check":
            result = True
        else:
            visiting.add(current)
            result = all(
                field.kwargs_relation is not None
                or (field.annotation is not None and check(field.annotation, visiting))
                for field in fields_or_init_kwargs(current)
            )
            visiting.remove(current)
        return result

    return check(annotation, set())


def is_value_of_type(value: Any, annotation: Any) -> bool:
    """Return whether a Python value and all nested values fit an annotation without conversion."""

    annotation = normalize_annotation(annotation)
    if not is_annotation_supported(annotation, operation="type_check"):
        result = False
    elif annotation is Any:
        result = True
    elif annotation is type(None):
        result = value is None
    else:
        origin = annotation_origin(annotation)
        if origin in (Union, UnionType):
            result = any(is_value_of_type(value, member) for member in get_args(annotation))
        elif (enum_class := enum_type(annotation)) is not None:
            result = isinstance(value, enum_class)
        elif origin is Callable2:
            result = callable(value)
        elif origin in (int, float, str, bool):
            result = type(value) is origin
        elif origin in (dict, list, set):
            if not isinstance(value, origin):
                result = False
            else:
                item_types = get_collection_args(annotation)
                if origin is dict:
                    result = all(
                        is_value_of_type(key, item_types[0]) and is_value_of_type(item, item_types[1])
                        for key, item in value.items()
                    )
                else:
                    result = all(is_value_of_type(item, item_types[0]) for item in value)
        elif origin is not tuple:
            result = isinstance(value, annotation if is_structured_model(annotation) else origin)
        elif not isinstance(value, tuple):
            result = False
        else:
            args = get_args(annotation)
            if not args:
                result = True
            elif len(args) == 2 and args[1] is Ellipsis:
                result = all(is_value_of_type(item, args[0]) for item in value)
            else:
                result = len(value) == len(args) and all(
                    is_value_of_type(item, args[index]) for index, item in enumerate(value)
                )
    return result


def selected_target_fields(target: type | Callable[..., Any]) -> list[FieldSpec]:
    """Inspect the named parameters of a selected class, function, or method.

    Parameters that cannot be passed by keyword are rejected. The target is
    never constructed or called.
    """

    if not (inspect.isclass(target) or inspect.isfunction(target) or inspect.ismethod(target)):
        raise TypeError(f"{target}: selected targets must be classes, functions, or methods")

    return fields_or_init_kwargs(target, selected=True)


def validate_selected_mapping(
    parameters: list[FieldSpec],
    values: Mapping[str, Any],
    field_name: str,
) -> None:
    """Check a selected argument mapping without changing its values.

    Unknown names and missing required parameters raise ``TypeError``.
    """

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


def dict_from_str(value: str) -> dict[Any, Any]:
    """Read a dictionary from inline JSON or a path ending in ``.json``."""

    assert isinstance(value, str)
    if value.startswith("{"):
        result = json.loads(value)
    elif value.endswith(".json"):
        assert os.path.exists(value), f"{value} does not exist"
        with open(value) as in_f:
            result = json.load(in_f)
    else:
        raise AssertionError(f"unexpected str: {value}")
    return result


def attempt_from_dict_value(
    x: Any,
    field_type: Any,
    field_name: str,
    *,
    strict: bool = False,
    operation: Literal["dict", "json"] = "dict",
) -> ConversionAttempt:
    """Try to decode one value and return the result or its conversion error.

    ``operation="dict"`` checks the rules for dictionary conversion.
    ``operation="json"`` checks the narrower rules for JSON conversion. The
    operation changes only those support rules; this function always decodes.
    With ``strict=True``, the annotation must be fully supported and the input
    must already use an accepted dictionary or JSON form. The default mode keeps
    the built-in type conversions and otherwise accepts only a value that already
    matches the full annotation.
    """

    field_type = normalize_annotation(field_type)
    origin = annotation_origin(field_type)
    concrete_type = type(x)
    if strict and not is_annotation_supported(field_type, operation=operation):
        return ConversionAttempt(
            error=TypeError(f"{field_name}: {field_type} is not supported for {operation} conversion")
        )
    if x is None:
        if is_optional(field_type) or field_type in (Any, type(None)):
            result = ConversionAttempt(None)
        else:
            result = ConversionAttempt(error=TypeError(f"{field_name}: {field_type} cannot be converted from None"))
    elif origin in (Union, UnionType):
        if not strict:
            member_attempt = attempt_union_member(field_type, concrete_type, field_name)
            if member_attempt.error is not None:
                result = member_attempt
            else:
                result = attempt_from_dict_value(x, member_attempt.value, field_name, operation=operation)
        else:
            attempts = [
                attempt_from_dict_value(x, member, field_name, strict=True, operation=operation)
                for member in get_args(field_type)
            ]
            matches = [attempt for attempt in attempts if attempt.error is None]
            if len(matches) != 1:
                detail = "no exact conversion" if not matches else "ambiguous exact conversion"
                result = ConversionAttempt(
                    error=TypeError(f"{field_name}: {detail} from {concrete_type} to {field_type}")
                )
            else:
                result = matches[0]
    elif (enum_class := enum_type(field_type)) is not None:
        values = [member.value for member in enum_class]
        if any(type(value) not in (str, int, float, bool) for value in values):
            result = ConversionAttempt(
                error=TypeError(f"{field_name}: {enum_class.__name__} values must be str, int, float, or bool")
            )
        elif isinstance(x, enum_class):
            result = ConversionAttempt(x)
        elif strict and not any(type(x) is type(value) and x == value for value in values):
            result = ConversionAttempt(
                error=TypeError(
                    f"{field_name}: invalid exact {enum_class.__name__} value {x!r}; expected one of {values}"
                )
            )
        else:
            try:
                result = ConversionAttempt(enum_class(x))
            except ValueError as error:
                converted_error = TypeError(
                    f"{field_name}: invalid {enum_class.__name__} value {x!r}; expected one of {values}"
                )
                converted_error.__cause__ = error
                result = ConversionAttempt(error=converted_error)
    elif origin is Callable2:
        if callable(x):
            result = ConversionAttempt(x)
        elif not isinstance(x, str):
            result = ConversionAttempt(
                error=TypeError(f"{field_name}: expected a callable or importable callable reference")
            )
        else:
            try:
                callable_value = load_callable(x)
            except (AttributeError, ImportError, ValueError) as error:
                converted_error = TypeError(f"{field_name}: {x!r} does not resolve to a callable")
                converted_error.__cause__ = error
                result = ConversionAttempt(error=converted_error)
            else:
                if not callable(callable_value):
                    result = ConversionAttempt(error=TypeError(f"{field_name}: {x} does not resolve to a callable"))
                else:
                    try:
                        canonical_name = dump_callable(callable_value) if strict else x
                    except TypeError as error:
                        result = ConversionAttempt(error=error)
                    else:
                        if canonical_name != x:
                            result = ConversionAttempt(
                                error=TypeError(
                                    f"{field_name}: {x!r} is not the canonical reference {canonical_name!r}"
                                )
                            )
                        else:
                            result = ConversionAttempt(callable_value)
    elif field_type is Any:
        result = ConversionAttempt(x)
    elif is_structured_model(field_type):
        if isinstance(x, field_type):
            result = ConversionAttempt(x)
        else:
            if isinstance(x, str) and not strict:
                x = dict_from_str(x)
            if isinstance(x, Mapping):
                try:
                    value = from_dict_operation(
                        field_type, x, strict=strict, field_name=field_name, operation=operation
                    )
                except (AssertionError, AttributeError, ImportError, TypeError, ValueError) as error:
                    result = ConversionAttempt(error=error)
                else:
                    result = ConversionAttempt(value)
            else:
                result = ConversionAttempt(
                    error=TypeError(f"{field_name}: {field_type} cannot be converted from {concrete_type}")
                )
    elif origin in (int, float, str, bool):
        if strict and type(x) is not origin:
            result = ConversionAttempt(
                error=TypeError(f"{field_name}: expected exact {origin.__name__}, got {type(x).__name__}")
            )
        else:
            try:
                value = str_to_bool(x) if origin is bool and isinstance(x, str) else field_type(x)
            except (TypeError, ValueError) as error:
                result = ConversionAttempt(error=error)
            else:
                result = ConversionAttempt(value)
    elif origin is dict:
        raw = dict_from_str(x) if isinstance(x, str) and not strict else x
        if not isinstance(raw, Mapping):
            result = ConversionAttempt(error=TypeError(f"{field_name}: expected a mapping, got {type(raw)}"))
        else:
            key_type, value_type = get_collection_args(field_type)
            values = {}
            error = None
            for key, value in raw.items():
                key_attempt = attempt_from_dict_value(
                    key, key_type, f"{field_name}.key", strict=strict, operation=operation
                )
                if key_attempt.error is not None:
                    error = key_attempt.error
                    break
                else:
                    value_attempt = attempt_from_dict_value(
                        value, value_type, f"{field_name}.value", strict=strict, operation=operation
                    )
                    if value_attempt.error is not None:
                        error = value_attempt.error
                        break
                    values[key_attempt.value] = value_attempt.value
            result = ConversionAttempt(values, error)
    elif origin in (list, tuple):
        accepts = isinstance(x, list if strict and origin is list else (list, tuple))
        if not accepts:
            result = ConversionAttempt(
                error=TypeError(f"{field_name}: {field_type} cannot be converted from {type(x)}")
            )
        else:
            item_types = get_collection_args(field_type, len(x))
            fixed_tuple = origin is tuple and len(get_args(field_type)) > 1 and get_args(field_type)[1] is not Ellipsis
            if fixed_tuple and len(x) != len(item_types):
                result = ConversionAttempt(
                    error=TypeError(f"{field_name}: expected {len(item_types)} tuple values, got {len(x)}")
                )
            else:
                values = []
                error = None
                for index, item in enumerate(x):
                    attempt = attempt_from_dict_value(
                        item,
                        item_types[index] if index < len(item_types) else Any,
                        f"{field_name}[{index}]",
                        strict=strict,
                        operation=operation,
                    )
                    if attempt.error is not None:
                        error = attempt.error
                        break
                    values.append(attempt.value)
                result = ConversionAttempt(origin(values), error)
    elif not strict and is_value_of_type(x, field_type):
        result = ConversionAttempt(x)
    else:
        result = ConversionAttempt(
            error=TypeError(f"{field_name}: {field_type} cannot be converted from {concrete_type}")
        )
    return result


def from_dict_value(
    x: Any,
    field_type: Any,
    field_name: str,
    *,
    strict: bool = False,
    operation: Literal["dict", "json"] = "dict",
) -> Any:
    """Decode one value according to its annotation.

    ``operation="dict"`` checks the rules for dictionary conversion.
    ``operation="json"`` checks the narrower rules for JSON conversion. The
    operation changes only those support rules; this function always decodes.
    With ``strict=True``, the annotation must be fully supported and the input
    must already use an accepted dictionary or JSON form. The default mode keeps
    the built-in type conversions and otherwise accepts only a value that already
    matches the full annotation. A failed conversion raises the conversion error.
    """

    attempt = attempt_from_dict_value(x, field_type, field_name, strict=strict, operation=operation)
    if attempt.error is not None:
        raise attempt.error
    return attempt.value


def to_dict_value(
    x: Any,
    field_type: Any,
    field_name: str = "value",
    *,
    strict: bool = False,
    operation: Literal["dict", "json"] = "dict",
) -> Any:
    """Encode one Python value according to its annotation.

    ``operation="dict"`` checks the rules for dictionary conversion.
    ``operation="json"`` checks the narrower rules for JSON conversion. The
    operation changes only those support rules; this function always encodes.
    With ``strict=True``, the annotation must be fully supported and the value
    must already match its Python type. The default mode keeps the built-in type
    conversions and otherwise passes through only a value that matches the full
    annotation.
    """

    field_type = normalize_annotation(field_type)
    origin = annotation_origin(field_type)
    if strict and not is_annotation_supported(field_type, operation=operation):
        raise TypeError(f"{field_name}: {field_type} is not supported for {operation} conversion")
    if strict and not is_value_of_type(x, field_type):
        raise TypeError(f"{field_name}: expected {field_type}, got {type(x)}")
    if x is None:
        if field_type in (Any, type(None)) or is_optional(field_type):
            result = None
        else:
            raise TypeError(f"{field_name}: expected {field_type}, got None")
    elif origin in (Union, UnionType):
        matches = [member for member in get_args(field_type) if is_value_of_type(x, member)]
        if strict and len(matches) != 1:
            raise TypeError(f"{field_name}: ambiguous exact value for {field_type}")
        member = matches[0] if strict else union_member(field_type, type(x), field_name)
        result = to_dict_value(x, member, field_name, strict=strict, operation=operation)
    elif field_type is Any:
        result = x
    elif (enum_class := enum_type(field_type)) is not None:
        validate_enum_values(enum_class, field_name)
        if isinstance(x, enum_class):
            result = x.value
        else:
            raise TypeError(f"{field_name}: expected {enum_class.__name__} value, got {type(x)}")
    elif is_structured_model(field_type):
        result = to_dict_operation(x, strict=strict, field_name=field_name, operation=operation)
    elif origin is dict:
        key_type, value_type = get_collection_args(field_type)
        result = {
            to_dict_value(key, key_type, f"{field_name}.key", strict=strict, operation=operation): to_dict_value(
                value, value_type, f"{field_name}.value", strict=strict, operation=operation
            )
            for key, value in x.items()
        }
    elif origin in (list, tuple):
        item_types = get_collection_args(field_type, len(x))
        values = [
            to_dict_value(item, item_types[index], f"{field_name}[{index}]", strict=strict, operation=operation)
            for index, item in enumerate(x)
        ]
        result = tuple(values) if isinstance(x, tuple) else values
    elif origin is Callable2:
        if callable(x):
            try:
                result = dump_callable(x)
            except TypeError as error:
                raise TypeError(f"{field_name}: {error}") from error
        else:
            raise TypeError(f"{field_name}: expected callable value for {field_type}, got {type(x)}")
    elif origin in (int, float, str, bool):
        try:
            result = origin(x)
        except (TypeError, ValueError) as error:
            raise type(error)(f"{field_name}: {error}") from error
    elif not strict and is_value_of_type(x, field_type):
        result = x
    else:
        raise TypeError(f"{field_name}: {field_type} cannot encode value of type {type(x)}")
    return result


def to_dict_operation(
    x: Any,
    type_class: type | Callable[..., Any] | None = None,
    *,
    strict: bool = False,
    field_name: str | None = None,
    operation: Literal["dict", "json"] = "dict",
) -> dict[str, Any]:
    """Encode an object's present declared fields and their nested values.

    ``operation="dict"`` checks the rules for dictionary conversion.
    ``operation="json"`` checks the narrower rules for JSON conversion. The
    operation changes only those support rules; this function always encodes.
    With ``strict=True``, every present annotation must be fully supported and
    each value must already match its Python type. The default mode keeps the
    built-in type conversions and otherwise passes through only values that
    match their full annotations. Missing fields are not filled. Selected
    callables used by ``kwargs_for`` are inspected but never constructed or
    called.
    """

    result: dict[str, Any] = {}
    mapping = x if isinstance(x, Mapping) else None
    owner = type(x) if type_class is None else type_class
    owner_name = field_name or cast(Any, owner).__qualname__
    selected_fields: dict[str, list[FieldSpec]] = {}
    for f in fields_or_init_kwargs(owner):
        value = mapping[f.name] if mapping is not None and f.name in mapping else getattr(x, f.name, MISSING)
        if value is MISSING:
            continue
        elif f.kwargs_relation is None:
            if strict and f.annotation is None:
                raise TypeError(f"{owner_name}.{f.name}: annotation is not supported for {operation} conversion")
            annotation = f.annotation if f.annotation is not None else type(value)
            result[f.name] = to_dict_value(
                value,
                annotation,
                f"{owner_name}.{f.name}",
                strict=strict,
                operation=operation,
            )
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
                    if strict and parameter.annotation is None:
                        raise TypeError(
                            f"{field_name}.{parameter.name}: annotation is not supported for {operation} conversion"
                        )
                    annotation = parameter.annotation if parameter.annotation is not None else type(raw)
                    converted[parameter.name] = to_dict_value(
                        raw,
                        annotation,
                        f"{field_name}.{parameter.name}",
                        strict=strict,
                        operation=operation,
                    )
            result[f.name] = converted
    return result


def to_dict(
    x: Any,
    type_class: type | Callable[..., Any] | None = None,
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Convert present declared fields and nested values into a dictionary.

    By default, supported type conversions are applied and an unsupported value
    may pass through only when it already fits its full annotation.
    ``strict=True`` rejects unsupported annotations and values that do not
    already have the declared Python types. The function never fills missing
    fields.
    """

    return to_dict_operation(x, type_class, strict=strict, field_name=field_name, operation="dict")


def to_kwargs(
    target: type | Callable[..., Any],
    x: Any,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Copy present top-level values that ``target`` accepts by keyword.

    Nested values are not converted or copied, and missing values and defaults
    are not filled. ``strict=True`` checks each copied value against its
    annotation.
    """

    result: dict[str, Any] = {}
    missing = object()
    owner_name = cast(Any, target).__qualname__
    if inspect.isclass(target):
        parameters = [(field.name, field.annotation) for field in fields_or_init_kwargs(target)]
    else:
        annotations = get_type_hints(target, include_extras=True)
        parameters = [
            (parameter.name, annotations.get(parameter.name, parameter.annotation))
            for parameter in inspect.signature(target).parameters.values()
            if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
        ]
    for parameter_name, annotation in parameters:
        if isinstance(x, Mapping):
            if parameter_name not in x:
                continue
            value = x[parameter_name]
        else:
            value = getattr(x, parameter_name, missing)
            if value is missing:
                continue
        if strict:
            if annotation in (None, inspect.Parameter.empty) or not is_annotation_supported(
                annotation, operation="type_check"
            ):
                raise TypeError(f"{owner_name}.{parameter_name}: annotation is not supported for type_check")
            elif not is_value_of_type(value, annotation):
                raise TypeError(f"{owner_name}.{parameter_name}: expected {annotation}, got {type(value)}")
        result[parameter_name] = value
    return result


def kwargs_from_dict(
    target: type | Callable[..., Any],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
    field_name: str = "kwargs",
) -> dict[str, Any]:
    """Decode a callable's nested argument values without running the target.

    Unknown and missing required arguments are rejected. ``strict=True``
    rejects unsupported annotations and input values in the wrong encoded type.
    A class is not constructed and a function or method is not called.
    """

    return from_dict_operation(
        target,
        values,
        strict=strict,
        field_name=field_name,
        operation="dict",
        construct=False,
    )


@overload
def from_kwargs(target: type[T], values: Mapping[str, Any], *, strict: bool = False) -> T:
    """Filter keyword values and construct ``target`` exactly once.

    ``strict=True`` checks copied values without converting them.
    """


@overload
def from_kwargs(
    target: Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> partial[T]:
    """Filter keyword values and return a partial without calling ``target``.

    ``strict=True`` checks copied values without converting them. Missing
    required arguments and callable defaults remain open for the later call.
    """


def from_kwargs(
    target: type[T] | Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> T | partial[T]:
    """Construct a class once or return a partial without calling a callable.

    Only present top-level keyword values are used. ``strict=True`` checks them
    without converting them.
    """

    filtered = to_kwargs(target, values, strict=strict)
    if inspect.isclass(target):
        result = target(**filtered)
    else:
        result = partial(target, **filtered)
    return result


def from_dict_operation(
    clazz: type[T] | Callable[..., Any],
    x: Mapping[Any, Any],
    *,
    strict: bool = False,
    field_name: str | None = None,
    operation: Literal["dict", "json"] = "dict",
    construct: bool = True,
) -> T | dict[str, Any]:
    """Decode the named values for a class or callable.

    ``operation="dict"`` checks the rules for dictionary conversion.
    ``operation="json"`` checks the narrower rules for JSON conversion. The
    operation changes only those support rules; this function always decodes.
    With ``strict=True``, every used annotation must be fully supported and the
    input must already use an accepted dictionary or JSON form. The default mode
    keeps the built-in type conversions and otherwise accepts only values that
    match their full annotations. With ``construct=True``, the function
    constructs or calls ``clazz`` once; a Pydantic model is validated once.
    With ``construct=False``, it returns the decoded named arguments without
    constructing or calling ``clazz``.
    """

    owner_name = field_name or cast(Any, clazz).__qualname__
    if not isinstance(x, Mapping):
        raise TypeError(f"{owner_name}: expected a mapping, got {type(x)}")
    parameters = fields_or_init_kwargs(clazz) if construct else selected_target_fields(clazz)
    pydantic_owner = construct and is_pydantic_model(clazz)
    if pydantic_owner and not any(field.kwargs_relation is not None for field in parameters):
        return cast(Any, clazz).model_validate(x, strict=strict)

    values: dict[str, Any] = deepcopy(dict(x)) if pydantic_owner else {}
    if not construct:
        validation_values = dict(x)
        relation_names = {
            parameter.kwargs_relation.name for parameter in parameters if parameter.kwargs_relation is not None
        }
        for parameter in parameters:
            if parameter.kwargs_relation is not None or parameter.name in relation_names:
                validation_values.setdefault(parameter.name, MISSING)
        validate_selected_mapping(parameters, validation_values, owner_name)
    selectors: dict[str, tuple[Any, list[FieldSpec]]] = {}
    for parameter in parameters:
        name = parameter.name
        current_name = f"{owner_name}.{name}"
        value = x.get(name, MISSING)
        relation = parameter.kwargs_relation
        if relation is not None:
            supplied = {} if value is MISSING else value
            if not isinstance(supplied, Mapping):
                raise TypeError(f"{current_name}: expected a mapping, got {type(supplied)}")
            if relation.name not in selectors:
                target = x.get(relation.name, MISSING)
                if target is MISSING:
                    target = materialize_default(relation)
                    if target is MISSING:
                        raise TypeError(f"{owner_name}.{relation.name}: missing selector")
                target = from_dict_value(
                    target,
                    relation.annotation or type(target),
                    f"{owner_name}.{relation.name}",
                    strict=strict,
                    operation=operation,
                )
                try:
                    selected = selected_target_fields(target)
                except TypeError as error:
                    raise TypeError(f"{current_name}: {error}") from error
                selectors[relation.name] = target, selected
                values[relation.name] = target
            selected = selectors[relation.name][1]
            if any(field.name not in supplied for field in selected):
                default = materialize_default(parameter, {})
            else:
                default = {}
            if not isinstance(default, Mapping):
                raise TypeError(f"{current_name}: expected a mapping default, got {type(default)}")
            merged = {**default, **supplied}
            validate_selected_mapping(selected, merged, current_name)
            value = {}
            for field in selected:
                if field.name in merged:
                    annotation = field.annotation
                    if annotation is None and not strict:
                        annotation = Any
                    value[field.name] = from_dict_value(
                        merged[field.name],
                        annotation,
                        f"{current_name}.{field.name}",
                        strict=strict,
                        operation=operation,
                    )
        elif value is MISSING or pydantic_owner:
            continue
        else:
            annotation = parameter.annotation
            if annotation is None and not strict:
                annotation = Any
            value = from_dict_value(
                value,
                annotation,
                current_name,
                strict=strict,
                operation=operation,
            )
        values[name] = value

    if not construct:
        validate_selected_mapping(parameters, {**x, **values}, owner_name)
        result = values
    elif pydantic_owner:
        result = cast(Any, clazz).model_validate(values, strict=strict)
    else:
        result = clazz(**values)
    return result


def from_dict(
    clazz: type[T],
    x: Mapping[Any, Any],
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> T:
    """Decode a mapping's nested values and construct one class instance.

    By default, supported type conversions are applied and an unsupported value
    may pass through only when it already fits its full annotation.
    ``strict=True`` rejects unsupported annotations and input values in the
    wrong encoded type. Missing constructor arguments remain the class's
    responsibility.
    """

    return cast(T, from_dict_operation(clazz, x, strict=strict, field_name=field_name, operation="dict"))
