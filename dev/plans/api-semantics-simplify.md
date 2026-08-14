# API semantics simplification

## Status

- Phase 1: Complete
- Phase 2: Complete
- Phase 3: Complete
- Phase 4: Complete
- Phase 5: Complete
- Phase 6: Complete
- Follow-up 1: Complete
- Follow-up 2: Complete
- Follow-up 3: Complete
- Follow-up 4: Complete

Update each phase to `In progress`, `Complete`, or `Blocked` while executing
this plan. Record the exact validation command and result beneath every
completed phase.

## Goal

Separate four concepts that are currently mixed together in `msup.base`:

1. Whether an annotation is fully supported for a particular operation.
2. Whether a runtime value matches an annotation without coercion.
3. Recursive conversion between Python objects and dictionary or JSON values.
4. Shallow projection to keyword arguments and construction or binding from
   keyword arguments.

The default conversion mode remains permissive. It performs the existing
useful coercions and passes a recursively type-correct value through when msup
does not implement conversion for its annotation. `strict=True` is an explicit
request for complete operation support and non-coercive value checking.
Dynamic `kwargs_for` relations continue to convert selected target arguments
recursively and never invoke or construct the selected target.

The recommended implementation is direct and direction-specific. Reflection
describes fields and parameters, annotation support reports capability,
strict checking validates values, recursive converters transform values, and
shallow kwargs helpers only select and bind. Do not add a conversion framework,
builder, visitor hierarchy, or mode object.

These semantics must reduce implementation LOC by replacing repeated branches
with shared operations. Measure implementation LOC separately from the
intentionally redundant top-of-module stable API declaration blocks. Preserve
focused public helpers such as `is_optional` and `maybe_idx`; do not inline or
delete them to meet the LOC target.

## End-state public API

Every declaration in `msup.base` and `msup.cli` remains public. Do not add or
retain declarations with a leading underscore. Every public type, class,
function, and method must have a behavior-focused docstring. Preserve the
top-of-module forward declarations that summarize each module's intended
interface and keep them synchronized with the implementations.
Dataclass definitions are not repeated in those forward-declaration blocks;
`Metadata`, `FieldSpec`, and `CliArg` each have one implementation definition.

Python type aliases cannot own a runtime `__doc__` attribute. Document
`Kwargs` with the adjacent string shown below. Every public class, function,
and method must expose its docstring through
`inspect.getdoc`; do not use an adjacent comment as a substitute. Verify this
during code review only. Do not add unit tests, source-text tests, or runtime
introspection tests that check whether docstrings exist or contain specific
text.

Public visibility and stability are separate promises. The stable public API
below is the compatibility-promised user surface. Its names, signatures,
return categories, default behavior, and documented semantics must not change
without a major version. The remaining public implementation API is importable
and documented so advanced callers and the other msup module can use it, but
it is provisional until explicitly promoted into the stable section. Do not
use an underscore prefix as a substitute for that stability distinction.

### Stable public API

The following is the complete compatibility-promised surface after this plan.
The implementation must copy these declarations into the appropriate module's
forward-declaration block with the shown docstrings or equally precise text.

```python
# msup.base

type Kwargs = dict[str, Any]
"""Keyword arguments whose effective schema comes from a selected callable."""

@dataclass(frozen=True, kw_only=True)
class Metadata:
    """Field metadata, including an optional relation to a callable selector."""

    kwargs_for: str | None = None


def is_annotation_supported(
    annotation: Any,
    *,
    operation: Literal["type_check", "dict", "json"],
) -> bool:
    """Return whether msup completely supports an annotation for one operation."""


def is_value_of_type(value: Any, annotation: Any) -> bool:
    """Return whether a Python value recursively matches an annotation without conversion."""


def to_dict(
    x: Any,
    type_class: type | Callable[..., Any] | None = None,
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Recursively encode declared fields into dictionary-form values."""


def from_dict(
    clazz: type[T],
    x: Mapping[Any, Any],
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> T:
    """Recursively decode dictionary-form values and construct a class instance."""


def to_json(
    x: Any,
    file_like=None,
    indent: int | None = 2,
    *,
    type_class: type | Callable[..., Any] | None = None,
    strict: bool = False,
) -> str | None:
    """Encode a value as JSON text or write it to a JSON destination."""


def from_json(
    clazz: type[T],
    s: str | None = None,
    file_like=None,
    path: str | None = None,
    *,
    strict: bool = False,
) -> T:
    """Read JSON input, recursively decode it, and construct a class instance."""


def to_kwargs(
    target: type | Callable[..., Any],
    x: Any,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Select a target's present top-level keyword-bindable values without conversion."""


@overload
def from_kwargs(target: type[T], values: Mapping[str, Any], *, strict: bool = False) -> T:
    """Filter keyword values and construct a class exactly once."""


@overload
def from_kwargs(
    target: Callable[..., T],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> partial[T]:
    """Filter keyword values and return a partial without invoking the callable."""


def kwargs_from_dict(
    target: type | Callable[..., Any],
    values: Mapping[str, Any],
    *,
    strict: bool = False,
    field_name: str = "kwargs",
) -> dict[str, Any]:
    """Recursively decode callable arguments without invoking or constructing the target."""


def load_callable(name: str) -> Any:
    """Load a trusted callable from its canonical module-qualified reference."""


def dump_callable(value: Any) -> str:
    """Return a canonical reference that reloads to the identical callable."""


def str_to_bool(value: str) -> bool:
    """Convert a supported textual boolean spelling or raise TypeError."""


def dict_from_str(value: str) -> dict[Any, Any]:
    """Load a dictionary from inline JSON text or a JSON file path."""


# msup.cli

@dataclass(frozen=True)
class CliArg(Metadata):
    """Configure CLI help, names, sources, visibility, and kwargs relations."""

    help: str = ""
    short: str | None = ""
    env: str | None = None
    pos: bool = False
    opt: bool = True
    secret: bool = False


def cli(cmd_or_cmds: Callable[..., Any] | dict[Callable[..., Any], str], **argparse_kwargs) -> None:
    """Parse command-line input and invoke the selected typed command."""
```

`from_kwargs` needs an implementation signature in addition to its overloads,
and that implementation carries the same docstring contract. The class
overload returns the constructed instance. The function or method overload
returns `functools.partial` and never invokes the callable.

### Provisional public implementation API

These declarations remain public, use no leading underscore, and each receives
a docstring. Their exact signatures remain implementation-facing and are not
part of the compatibility promise until promoted. Keep the list current if
execution adds, combines, or removes a declaration.

- `msup.base`: `FieldSpec`, `ConversionAttempt`, `unwrap_annotated`, `normalize_annotation`,
  `metadata_from_annotations`, `is_pydantic_model`, `is_structured_model`,
  `has_default_value`, `materialize_default`, `fields_or_init_kwargs`,
  `contains_relation`, `maybe_idx`, `get_optional_type`, `get_collection_args`, `is_optional`,
  `annotation_origin`, `effective_type`, `attempt_union_member`, `union_member`, `enum_type`,
  `validate_enum_values`, `selected_target_fields`, `attempt_from_dict_value`, `from_dict_value`,
  `to_dict_value`, `from_dict_operation`, `to_dict_operation`, and
  `validate_selected_mapping`. The operation helpers are the shared owner
  traversals that preserve the stable wrapper signatures while carrying
  dictionary or JSON capability provenance.
- `msup.cli`: `cliarg_from_annotations`, `error_exit`,
  `enum_argument_type`, `mapping_argument_type`, `argument_type`,
  `add_argument`, `add_fields`, `add_args`, `add_direct_args`,
  `config_values`, `parse_args`, `has_nested_source`, `merge`,
  `target_options`, `bootstrap`, `from_cli_args`, and
  `from_direct_cli_args`.

Rename the current underscore-prefixed CLI declarations directly to the names
above and update all call sites in the same phase. Do not retain aliases or
wrappers under the old names. Do not introduce a private conversion context;
pass the same inline `Literal["type_check", "dict", "json"]` operation through
the provisional recursive value APIs where operation provenance is required.

## Code map

- `msup/base.py:fields_or_init_kwargs` reflects dataclass, Pydantic v2,
  regular-class, function, and method fields and links `kwargs_for` metadata.
- `msup/base.py:is_compat` currently chooses permissive conversion routes from
  an annotation and one concrete input type. It does not recursively validate
  container values.
- `msup/base.py:_conversion_annotation_supported` currently implements one
  recursive conversion whitelist and is called unconditionally by
  `selected_target_fields`.
- `msup/base.py:selected_target_fields` reflects the explicit keyword-capable
  signature of a dynamically selected class, function, or method.
- `msup/base.py:from_dict_value` and `msup/base.py:to_dict_value` perform
  annotation-directed recursive value conversion.
- `msup/base.py:to_dict` currently duplicates selected-target mapping,
  unknown-key, required-key, and conversion checks in its relation branch.
- `msup/base.py:kwargs_from_dict` prepares a selected callable's explicit
  arguments without invocation.
- `msup/base.py:from_kwargs` currently performs recursive relation conversion
  and returns a dictionary. `msup/base.py:from_dict` depends on that behavior.
- `msup/cli.py:_bootstrap`, `msup/cli.py:_target_options`, and
  `msup/cli.py:_from_cli_args` are current migration points for selected option
  discovery, source merging, and selected-argument conversion. Phase 5 renames
  every underscore-prefixed CLI declaration and updates its call sites.
- `tests/test_basic.py` contains the base conversion, reflection, defaults,
  relation, and selected-signature coverage.
- `tests/test_pydantic.py` covers native Pydantic v2 validation, aliases,
  defaults, and relation conversion.
- `tests/test_cli.py` covers ordinary and dynamically selected CLI types,
  source precedence, defaults, help, and non-invocation.
- `README.md` and `examples/kwargs_for.py` document the current recursive
  relation behavior and the old dictionary-returning meaning of `from_kwargs`.

Delete `is_compat` without a public replacement. The current
`msup/base.py:is_compat` name suggests strict value compatibility, but it sees
only a source type, permits coercive primitive routes, checks only collection
origins, and returns a tuple that also attempts union selection.

Move source-shape checks into the conversion branches that consume them.
`from_dict_value` already knows whether it is decoding a primitive, enum,
callable, structured model, dictionary, list, or tuple, so each branch should
validate its accepted input shape directly. Keep coercive union route scoring
inside `union_member`. Do not add a conversion-route predicate under any name;
with the current two sites, direct branch logic is the repository-consistent
solution. Permissive identity fallback is not source-type routing: it requires recursive
`is_value_of_type(value, annotation)`.

### Annotation capability

`is_annotation_supported` is recursive and operation-specific:

- `type_check` means msup can recursively check a Python-side runtime value.
  It supports parameterized `set[T]` and arbitrary runtime classes through
  `isinstance` checks even when those values have no serialized form.
- `dict` means msup guarantees recursive conversion in both dictionary
  directions. It returns true for primitives, `Any`, `None`, optionals whose
  member is supported, unions whose members are all supported, enums with
  supported scalar backing values, callables, recursively supported
  dictionaries, lists, tuples, dataclasses, and Pydantic v2 models. Reflectable
  regular classes remain valid root targets for `to_dict` and `from_dict`;
  strict root conversion checks their reflected fields, but they are not
  advertised as recursively supported nested annotations unless the
  implementation adds that behavior and round-trip coverage.
- `json` means the annotation has a canonical JSON-compatible representation.
  It returns true for `None`, exact JSON primitives, enums backed only by JSON
  scalars, canonical callable references, lists, tuples, optionals, unions, and
  structured models whose nested annotations are all JSON-supported. A
  dictionary must have exactly `str` keys and a JSON-supported value annotation
  so JSON object-key coercion cannot break strict round trips. `Any` is false
  for `json` because its runtime value may not be JSON representable.

The nominal `dict[str, Any]` annotation on a `kwargs_for` dependent is a schema
placeholder, not its effective capability. During an owner traversal, defer
that field's `dict` or `json` decision until its selector is resolved, then
require the operation for every reflected selected parameter. A standalone
`dict[str, Any]` remains unsupported for strict JSON. This is another reason
selected-target reflection must be cached and passed to directional callers.

CLI capability is not an accepted operation of `is_annotation_supported`. In
`msup/cli.py`, the authoritative annotation capability question is whether
`argument_type` can produce an argparse converter for one annotation. Keep
that classification in `argument_type`; do not duplicate it in
`is_annotation_supported`. Field
metadata, positional layout, short-option rules, nested relation topology, and
selected-target restrictions remain contextual checks in `add_argument`,
`add_fields`, `target_options`, and `bootstrap` after the public-name migration.
They are not properties of
an annotation alone.

An operation returning `False` means that msup cannot guarantee recursive
handling. It does not prevent permissive identity pass-through. For example,
`set[int]` is supported for `type_check` and is not supported for `dict` or
`json`. `{1, 2}` may pass through permissive dictionary conversion unchanged,
but `{"1", "2"}` may not because recursive value checking fails.

Replace `_conversion_annotation_supported` with this public capability query.
Remove the unconditional capability gate from `selected_target_fields`.
Selected-target reflection validates only callable shape: class, function, or
method; keyword-bindable explicit parameters; no positional-only parameters,
`*args`, or `**kwargs`. Preserve a missing annotation as missing so strict and
CLI callers can reject it, but permissive base conversion can treat its value
as `Any`.

### Strict value semantics

`is_value_of_type` checks a Python-side value recursively and never converts
it. Primitive checks are exact, so `bool` is not accepted as `int`; containers
check their container kind and every key or element; tuples check their
declared arity; unions require at least one matching member; enums require an
instance of the enum; structured annotations require an instance of the
declared model with `isinstance`; and `Any` accepts every value. Parameterized
sets and arbitrary runtime classes are type-checkable even when no dict or JSON
encoding exists. Return `False`, rather than guessing, for an annotation
unsupported by `type_check`.

Use `is_value_of_type` only on Python-side values:

- `to_dict` and `to_json` validate each value before serialization.
- `to_kwargs` validates each selected top-level value without transforming it.
- `from_kwargs` gets the same validation through `to_kwargs`, then performs
  normal class construction or partial binding.

Do not use `is_value_of_type` to validate encoded dictionary or JSON input.
`from_dict_value` owns exact strict source rules because the encoded shape is
intentionally different from the resulting Python value:

- `Any` accepts the source unchanged. `None` is accepted only for `None`,
  `Any`, or an optional annotation.
- `int`, `float`, `str`, and `bool` require exact source types. In particular,
  `bool` is not `int`, and strict mode rejects `"3"` to `int`, `1` to `bool`,
  `3` to `str`, and `1` to `float`.
- An enum accepts an existing instance of the declared enum or one of its
  declared backing values with the exact backing scalar type. It rejects
  constructor-coercible alternatives.
- A callable accepts an already-callable Python value or a string canonical
  reference that resolves to a callable. No other source shape is accepted.
- A structured annotation accepts an existing instance or a `Mapping` whose
  fields are decoded recursively. Strict mode does not accept inline JSON text
  or a file path as a structured value.
- `dict[K, V]` requires a `Mapping` and decodes every key and value under their
  annotations. `list[T]` requires a list. A tuple annotation accepts a tuple
  from dictionary input and also a list because lists are the canonical JSON
  carrier; fixed tuples enforce exact arity and variable tuples decode every
  item.
- An optional delegates non-`None` input to its member. A non-optional union
  evaluates the exact strict source rules for each member and requires one
  unambiguous match.
- An unsupported annotation is never strict-decodable, even if the runtime
  value happens to match it.

The strict operation capability is fixed by public entry point:

| Entry point | Required annotation capability |
| --- | --- |
| `to_dict`, `from_dict` | `dict` |
| `to_json`, `from_json` | `json` |
| `to_kwargs`, `from_kwargs` | `type_check` |
| `kwargs_from_dict` | `dict` |

Apply that requirement to each present value the operation visits. Do not
reject an absent ordinary field merely because its annotation is unsupported;
partial typed mappings remain serializable, and omitted constructor parameters
remain the constructor's responsibility. Once a `kwargs_for` mapping is
present, it is active: validate its selected schema, including required names
and the capability of every present selected value. Selected-target parameters
omitted because they have defaults remain absent and are not value-checked.

The JSON helpers must not grow second converters. `from_json` parses JSON and
delegates all transformation to the implementation that backs `from_dict`;
`to_json` delegates all transformation to the implementation that backs
`to_dict`. Pass the inline literal operation through the provisional recursive
value APIs so root fields and dynamically resolved `kwargs_for`
parameters are checked as `json`, not merely `dict`, when their values are
present. Dictionary entries pass `dict`. The operation argument selects
capability checks only; it carries no callbacks, source values, defaults, or
traversal state. Thus JSON performs one recursive conversion with stricter
capability, followed or preceded only by standard-library JSON encoding or
parsing.

Default `strict=False` preserves coercive primitive, enum, callable,
collection, and structured-model conversion. When no conversion branch exists,
identity pass-through requires recursive `is_value_of_type(value, annotation)`.
It permits valid subclass instances where `isinstance` permits them, rejects
`set[str]` for `set[int]`, and never treats a matching outer origin as enough.
`to_json(strict=False)` may still reach the standard library JSON encoder and
fail naturally for a valid pass-through set. `to_json(strict=True)` rejects
that unsupported JSON annotation earlier with the qualified field path.

### Recursive dictionary and JSON conversion

`to_dict` and `from_dict` remain recursive inverses for fully supported `dict`
annotations. They recurse through annotated fields, collections, enums,
callables, and structured models. `type_class` continues to let `to_dict`
serialize a mapping such as `locals()` against a class or function schema.

For dataclasses and regular classes, unknown outer keys are filtered, omitted
fields are left to constructor defaults and factories, and missing required
fields fail when the constructor is called. For relation-aware fields,
selected-target unknown and required-parameter checks remain explicit because
the relation mapping promises callable-ready keyword arguments. A selected
parameter with a Python default remains omitted so a later target call applies
that default.

Keep the current relation default contract in recursive conversion and CLI
aggregation: a supplied dependent mapping overlays a copied declared mapping
default only when missing selected parameters require that default, factories
run at most once and only when needed, an explicit selector suppresses its
selector factory, and target parameter defaults remain absent. This behavior
belongs to `from_dict` and CLI source aggregation, not to shallow
`from_kwargs`.

For a direct function or unbound method that itself owns a `kwargs_for`
relation, `kwargs_from_dict` owns the corresponding behavior. It resolves an
omitted selector from the function parameter default, deep-copies an omitted or
partially overlaid dependent mapping default, overlays supplied dependent keys
on that copy, converts only explicit selected-target arguments, and leaves
selected-target defaults absent. If every selected parameter is supplied, it
does not read or copy the owner mapping default; otherwise it copies that
default once before overlaying supplied keys. A supplied selector or dependent
value wins over its owner default. Plain function parameters have no
`default_factory`;
factory-count behavior remains applicable to dataclass and Pydantic relation
owners handled by `from_dict`, and to CLI materialization. No default lookup,
copy, or factory evaluation may invoke the owner function or selected target.

Pydantic v2 policy remains explicit:

- Relation-free recursive `from_dict` and `from_json` delegate the original
  mapping to `model_validate`, passing `strict=strict`, so native aliases,
  extra-field policy, validators, defaults, and factories remain authoritative.
- Relation-aware models preprocess canonical selector and dependent fields,
  then call `model_validate(..., strict=strict)` exactly once. They continue
  rejecting validation aliases on linked fields. Unrelated Pydantic fields
  remain native.
- `to_dict` emits canonical field names and applies msup's enum and callable
  representation rather than silently switching to `model_dump` semantics.
- Shallow `from_kwargs` filters canonical reflected names and calls the
  Pydantic class like any other class. It does not interpret validation aliases
  or preserve unknown keys. With `strict=True`, msup first performs Python-side
  `type_check` validation and then uses normal construction because a Pydantic
  constructor call has no native `strict` argument.
- Pydantic v1 remains unsupported.

`from_json` parses JSON and delegates to `from_dict` with the same `strict`
value. `to_json` delegates to `to_dict`, then uses `json.dump` or `json.dumps`.
Do not duplicate a second conversion implementation in the JSON helpers.

### Shallow kwargs conversion

`to_kwargs` reflects `target` once and selects only declared, keyword-bindable
top-level names. From a mapping it copies matching entries. From an object it
reads matching attributes. It does not recurse, copy nested values, resolve a
`kwargs_for` selector, convert callable references, fill omitted fields, or
evaluate defaults and factories.

Receiver handling follows the actual callable signature. Class reflection
omits the constructor's `self` or `cls`; a bound method's signature naturally
omits its already-bound receiver. A plain function or unbound method retains
keyword-bindable parameters named `self` or `cls` because those names have no
special binding semantics there. Do not reuse the current unconditional
name-based omission in `fields_or_init_kwargs` for shallow callable binding.

`from_kwargs` applies `to_kwargs(target, values, strict=strict)` and then:

- For a class, returns `target(**filtered_kwargs)`. The constructor is called
  exactly once. Omitted parameters use normal constructor defaults and
  factories, unknown input keys are ignored, and missing required parameters
  produce the constructor's native error.
- For a function or method, returns
  `functools.partial(target, **filtered_kwargs)`. It never calls the target.
  Omitted required parameters remain open for later binding, omitted defaulted
  parameters use the function's defaults when the partial is eventually
  called, and unknown input keys are ignored.

The shallow helpers do not special-case `kwargs_for`. A serialized relation
payload must first go through `from_dict` for a class owner or through
`kwargs_from_dict` before it is passed to `from_kwargs` for a direct function.
This explicit composition prevents a shallow API from acquiring a second
recursive conversion implementation.

### Selected callable kwargs and relations

`kwargs_from_dict` is the non-invoking recursive decoder for one callable's
explicit arguments. It reflects selected parameters once, rejects unknown
keys, rejects omitted required parameters, recursively converts present
values, and leaves target-defaulted parameters absent. It supports linked
`kwargs_for` metadata when the target itself is a direct function owner, so
this is valid:

```python
prepared = kwargs_from_dict(run, payload)
bound = from_kwargs(run, prepared)
```

Neither call invokes `run` or its selected target. Calling `bound()` is the
first invocation.

Add one shared provisional public selected-schema validator with this narrow
shape:

```python
def validate_selected_mapping(
    parameters: list[FieldSpec],
    values: Mapping[str, Any],
    field_name: str,
) -> None: ...
```

It accepts already-reflected selected parameters and does only three things:
validate the mapping boundary, reject unknown names, and reject omitted
parameters whose `FieldSpec.default` is `MISSING`. It does not reflect, merge
defaults, convert, serialize, invoke, or return a rewritten mapping.

`kwargs_from_dict` reflects its target exactly once, passes the resulting
parameters to `validate_selected_mapping`, then converts directionally.
Relation-aware `from_dict` and `to_dict` callers pass parameters cached by
selector name for the current traversal. CLI passes the parameters already
cached by relation path during `bootstrap`. This preserves once-per-selector
reflection instead of hiding a second reflection in a convenient helper.
Directional conversion remains in the caller: `to_dict` validates Python-side
values when strict and serializes with `to_dict_value`; it must not call
`from_dict_value` merely to validate. `from_dict`, `kwargs_from_dict`, and CLI
use `from_dict_value`. Four callers justify this single shared validator under
the repository reuse threshold.

## Key and default behavior summary

| Operation | Unknown names | Missing names | Defaults and factories |
| --- | --- | --- | --- |
| `to_kwargs` | Filtered | Left absent | Never evaluated |
| `from_kwargs` with a class | Filtered | Native constructor error if required | Applied once by constructor |
| `from_kwargs` with a function | Filtered | Left open on returned partial | Applied only on later invocation |
| `to_dict` outer owner | Nondeclared outer mapping keys are filtered | Missing ordinary fields stay absent; only a present relation mapping requires its selector and every required selected parameter | Never materialized; serialization preserves partial typed mappings |
| `from_dict` outer owner | Filtered for dataclass or regular class; Pydantic stays native | Constructor or Pydantic error if required | Applied by owner construction; relation defaults retain the contract above |
| `kwargs_from_dict` outer owner | Rejected for the direct callable schema | Required owner parameters are rejected after relation defaults are resolved | Direct-function selector and dependent mapping defaults are copied or resolved; factories do not exist on function parameters |
| Active `kwargs_for` mapping | Rejected with a qualified path | Required selected parameters rejected; target-defaulted parameters omitted | Selected-target defaults are never copied into the explicit mapping |
| CLI sources | Static argparse behavior; selected kwargs rejected if unknown | Existing CLI required-value errors | Existing precedence and at-most-once factory behavior |

## Phase 1: Separate reflection, capability, and strict type checking

**Status:** Complete

1. Add `is_annotation_supported` with its inline
   `Literal["type_check", "dict", "json"]` operation and add
   `is_value_of_type` to the forward declarations and implementations in
   `msup/base.py`. Do not introduce a named operation alias. Keep the recursive
   implementations direct and aligned with `normalize_annotation`,
   `annotation_origin`, `get_collection_args`, `enum_type`, and
   `is_structured_model`.
2. Delete `_conversion_annotation_supported`. Make `selected_target_fields`
   validate signature shape without rejecting an annotation solely because
   recursive conversion or JSON does not support it. Preserve unresolved
   annotation errors from `get_type_hints` with the selected target context.
3. Delete `is_compat` and remove every import and expectation of its tuple
   return shape from `tests/test_basic.py`. Inline its source-route cases into
   `union_member` and the existing `from_dict_value` branches without changing
   conversion behavior in this phase. Do not add identity fallback here and do
   not add a replacement predicate. Keep the two source-route decisions direct
   rather than introducing another declaration.
4. Add one parameterized base test covering operation differences, including
   `set[int]`: supported for `type_check` and unsupported for `dict` and
   `json`. In the same test, show that `is_value_of_type(["1"], list[int])` is
   false so outer-origin matching cannot be mistaken for strict checking. Do
   not test source-type routing as a public contract.
5. Update selected-target reflection tests so an unsupported conversion
   annotation can be reflected, while missing annotations and CLI capability
   restrictions are tested at the consumers that require them.
6. Make the `msup.base` forward declarations match the complete stable API
   block at the top of this plan. Add or improve behavior-focused docstrings
   for every stable and provisional public declaration in `msup.base`,
   including `FieldSpec` and all value, reflection, annotation, callable,
   boolean, and dictionary helpers. Do not add a leading-underscore
   declaration. Review docstrings manually and do not add tests for their
   presence or contents. Per the execution override, do not repeat dataclass
   definitions in the forward-declaration block.
7. Move the current relation predicate from `msup.cli:_contains_relation` to
   public `msup.base:contains_relation`. It is a schema query over reflected
   `FieldSpec.kwargs_relation`, not CLI behavior. Import it from `msup.cli` and
   reuse it for base conversion decisions that need the same owner-level
   question. Preserve `is_optional` and `maybe_idx` as documented public
   helpers; do not inline or delete them.

**Success criteria:** capability and exact runtime checking have independent
names and tests; `is_compat`, its tuple return contract, and any public
replacement routing predicate are absent;
`selected_target_fields` no longer imposes a global recursive annotation
whitelist; conversion behavior, including the current unsupported fallback,
has not changed yet; and every remaining `msup.base` declaration is public and
documented, with the stable subset matching the top-of-plan contract.

**Validation:** Run `uv run --group dev --extra pydantic pytest
tests/test_basic.py -k 'annotation or compat or selected_target'`,
`./run.py type_check`, `./run.py lint_check`, `./run.py format_check`, and
`git diff --check`.

**Validation result:** `uv run --group dev --extra pydantic pytest
tests/test_basic.py -k 'annotation or compat or selected_target'` passed with
7 tests passed and 20 deselected. `uv run --group dev --extra pydantic pytest
tests/test_basic.py tests/test_cli.py` passed with 82 tests. `./run.py
type_check`, `./run.py lint_check`, `./run.py format_check`, and `git diff
--check` passed.

## Phase 2: Decouple and simplify recursive relation conversion

**Status:** Complete

1. Move the current recursive owner and `kwargs_for` conversion out of
   `from_kwargs` and into the declaration-order `from_dict` path before
   changing the public `from_kwargs` return type. Keep relation-free regular
   owners as one field conversion followed by one constructor call.
2. Add `validate_selected_mapping(parameters, values, field_name)` with the
   exact validation-only contract above. Make `kwargs_from_dict` the
   authoritative recursive decoder for a callable's explicit schema,
   including a direct function or unbound method that itself declares a
   `kwargs_for` relation. It reflects once, resolves copied owner defaults and
   relation overlays, calls the validator with already-reflected parameters,
   and converts present values. Cached owner callers reuse the validator
   without reflection. Phase 5 passes CLI's cached parameters to the same
   validator after base behavior is stable.
3. Rewrite the relation branch of `to_dict` to use the shared selected schema
   validation and serialize present values directly with their selected
   annotations. Remove the duplicated mapping, unknown, required, and
   `from_dict_value` validation in that branch. Cache reflection once per
   selector per owner traversal.
4. Preserve lazy selectors, copied mapping defaults, factory counts, qualified
   errors, multiple dependents, nested relations, and target non-invocation.
   Keep the current public `from_kwargs` behavior only as a temporary direct
   delegation during this phase, with no duplicate conversion body. Phase 3
   removes that temporary return shape.
5. Preserve Pydantic v2 native validation and alias behavior for unrelated
   fields. Preprocess only canonical relation fields and call `model_validate`
   once. Keep the linked alias rejection and Pydantic v1 rejection.
6. Add focused direct-function `kwargs_from_dict` coverage for an omitted
   default selector, supplied-over-default dependent key precedence, deep-copy
   isolation of a mutable dependent default, selected-target defaults remaining
   absent, owner and selected-target non-invocation, and qualified unknown or
   missing errors. Keep the existing dataclass/Pydantic factory-count cases to
   prove selector and dependent factories run at most once; do not invent a
   function `default_factory` concept.

**Success criteria:** `from_dict` no longer depends on the eventual shallow
`from_kwargs` contract; selected mapping validation exists in one shared path;
relation serialization no longer deserializes values to validate them; all
current recursive relation, factory, Pydantic, and non-invocation tests pass;
and Phase 3 can replace `from_kwargs` without breaking recursive conversion.

**Validation:** Run `uv run --group dev --extra pydantic pytest
tests/test_basic.py tests/test_pydantic.py -k 'relation or kwargs'`,
`./run.py type_check`,
`./run.py lint_check`, `./run.py format_check`, and `git diff --check`.

**Validation result:** `uv run --group dev --extra pydantic pytest
tests/test_basic.py tests/test_pydantic.py -k 'relation or kwargs'` passed with
9 tests passed and 37 deselected. The same two test files passed all 46 tests.
`./run.py type_check`, `./run.py lint_check`, `./run.py format_check`, and `git
diff --check` passed.

## Phase 3: Implement the shallow kwargs contract

**Status:** Complete

1. Add `functools.partial` and the class/function overloads to `msup/base.py`.
   Keep top-level reflection direct and exclude parameters that cannot be bound
   by keyword. Omit a class constructor receiver and rely on bound-method
   signatures to omit their bound receiver, but retain explicit `self` and
   `cls` parameters on plain functions and unbound methods. Do not recurse into
   annotations or relations.
2. Keep `to_kwargs` as shallow selection of present values from a mapping or
   object. Do not copy nested values, fill omissions, or evaluate defaults and
   factories.
3. Replace `from_kwargs` with shallow projection followed by one class
   construction or one `partial` creation. Remove `field_name`, the temporary
   mapping-returning delegation from Phase 2, and every relation-specific
   branch from this function.
4. Replace the existing dictionary-returning `from_kwargs` test with one
   compact class case and one function case. The function case must prove
   non-invocation, unknown-key filtering, retained supplied keyword values,
   omitted default handling, an omitted required parameter remaining bindable,
   and successful later invocation. In the same focused group, cover a plain
   function and an unbound method whose keyword-bindable `self` or `cls`
   parameter is retained, plus a bound method whose receiver is naturally
   absent.
5. Add the direct function composition test
   `from_kwargs(function, kwargs_from_dict(function, payload))` for a serialized
   `kwargs_for` payload. Assert that neither the owner function nor its selected
   target is invoked during preparation.

**Success criteria:** `to_kwargs` is visibly shallow; `from_kwargs(Class,
values)` returns a constructed instance; `from_kwargs(function, values)`
returns a `partial`; no function body runs until the partial is called; defaults
or factories are not evaluated by projection; and recursive dict conversion
continues to pass independently.

**Validation:** Run `uv run --group dev --extra pydantic pytest
tests/test_basic.py -k 'kwargs or relation'`, then `uv run --group dev --extra
pydantic pytest tests/test_basic.py tests/test_pydantic.py`, `./run.py type_check`,
`./run.py lint_check`, `./run.py format_check`, and `git diff --check`.

**Validation result:** The focused command passed with 10 tests passed and 22
deselected. The complete base and Pydantic command passed all 48 tests.
`./run.py type_check`, `./run.py lint_check`, `./run.py format_check`, and `git
diff --check` passed.

## Phase 4: Add strict recursive and shallow conversion

**Status:** Complete

1. Add and propagate `strict` through `from_dict_value`, `to_dict_value`,
   `from_dict`, `to_dict`, `from_json`, `to_json`, `kwargs_from_dict`,
   `to_kwargs`, and `from_kwargs`. Keep `field_name` propagation in recursive
   paths so nested failures name the actual field. Pass the public `dict` or
   `json` operation value through recursive serialization and deserialization.
2. Implement the exact strict encoded-source rules in `from_dict_value`; do not
   call `is_value_of_type` on serialized input. Require `dict` capability for
   `from_dict` and `kwargs_from_dict`, and `json` capability for `from_json`.
   Make `from_json` parse once and delegate transformation to the shared
   `from_dict` implementation with operation `json`.
3. In permissive conversion only, make the final fallback in both
   `from_dict_value` and `to_dict_value` return the value unchanged only when
   recursive `is_value_of_type(value, annotation)` succeeds. Replace the
   deserializer's current unsupported-annotation failure and guard the
   serializer's current unconditional identity fallback. Retain failure for
   recursively incompatible input, including `set[str]` for `set[int]`, and
   accept valid subclass instances where the annotation permits them.
4. For `to_dict`, `to_json`, and shallow strict conversion, validate present
   Python-side values recursively with `is_value_of_type`. Require `dict`,
   `json`, or `type_check` capability according to the entry-point table. For
   `to_json`, delegate to the shared `to_dict` implementation with operation
   `json` before calling the standard library encoder. For
   `to_kwargs` and `from_kwargs`, validate only projected values, raise a
   qualified `TypeError` for an unannotated or unsupported strict field, and do
   not transform a nested value after validating it.
5. For recursive Pydantic v2 `from_dict` and `from_json`, pass `strict=strict`
   to native `model_validate`. For relation-aware input, strictly preprocess
   canonical relation values and still call native validation once. Shallow
   `from_kwargs(strict=True)` uses msup `type_check` validation followed by a
   normal constructor call, never a nonexistent constructor `strict` keyword.
   Keep unrelated aliases and validators native.
6. Consolidate tests instead of mirroring every branch. Cover permissive scalar
   coercion versus strict rejection, strict Python-side serialization,
   permissive valid `set[int]` identity, rejection of invalid `set[str]`, strict
   dict and JSON rejection for the set annotation, exact primitive types, enum
   backing scalars, callable strings and values, structured mappings and
   instances, dictionary/list/tuple carriers, optional/union/Any/None behavior,
   one shallow strict mismatch, selected unknown and missing errors, and target
   non-invocation. Use parameterized cases to minimize test count.
7. Add focused Pydantic tests for native `model_validate(..., strict=True)`,
   relation preprocessing followed by one native validation call, canonical
   linked fields, unchanged relation-free aliases, and shallow construction
   without forwarding `strict` to the Pydantic constructor.

**Success criteria:** recursive conversion has one directional implementation
per direction; strict mode rejects coercion before conversion; permissive mode
accepts already-compatible unsupported values; shallow strict mode validates
without transforming; Pydantic remains native at its boundary; and all
selected targets remain uncalled.

**Validation:** Run `uv run --group dev --extra pydantic pytest
tests/test_basic.py tests/test_pydantic.py`, `./run.py type_check`,
`./run.py lint_check`, `./run.py format_check`, and `git diff --check`.

**Validation result:** The base and Pydantic command passed all 56 tests and 90
parameterized subtests. `./run.py type_check`, `./run.py lint_check`,
`./run.py format_check`, and `git diff --check` passed.

## Phase 5: Make CLI capability checks explicit and reuse conversion

**Status:** Complete

1. Rename every remaining underscore-prefixed declaration in `msup/cli.py` to
   the corresponding provisional public name listed at the top of this plan:
   `add_argument`, `add_fields`, `add_args`,
   `config_values`, `parse_args`, `merge`, `target_options`, `bootstrap`, and
   `from_cli_args`. Import `contains_relation` from `msup.base`. Update all call
   sites directly and retain no aliases or wrappers under the old names.
2. Keep CLI annotation capability in `msup/cli.py:argument_type`: it succeeds
   only when it can return an argparse converter and raises a qualified
   `TypeError` otherwise. Refactor its existing branches only as needed to make
   that ownership explicit. Do not add `operation="cli"` to the base capability
   API or duplicate the type classifier in a second predicate. A missing
   selected-target annotation is a CLI schema error when `argument_type` is
   requested, not a global reflection error.
3. Keep CLI parsing permissive because strings from argv, environment, and
   JSON configuration intentionally require conversion. Do not expose a CLI
   `strict` flag as part of this change.
4. After existing source precedence and default merging choose the selected
   relation mapping, pass `bootstrap`'s cached `list[FieldSpec]` and the mapping
   to `validate_selected_mapping`, then convert present values directionally.
   Remove the matching mapping, unknown, and required validation loop from
   `from_cli_args`. Do not call `kwargs_from_dict`, because that would reflect
   the selected callable a second time.
5. Preserve the current two-pass dynamic option discovery, one reflection per
   selected callable, qualified dotted options, at-most-once factories, native
   Pydantic construction, help behavior, and prohibition on nested dynamic
   relations, short selected options, positional-only parameters, `*args`, and
   `**kwargs`. Keep those layout and topology checks at their current
   `FieldSpec` or parser-context call sites; `argument_type` covers only
   converter production.
6. Update the selected-signature CLI tests so `set[int]` and an unannotated
   parameter are accepted by reflection but rejected when a CLI schema is
   requested. Retain focused non-invocation and parser error-status coverage.
7. Make the `msup.cli` forward declarations match the stable API block and add
   behavior-focused docstrings to `CliArg`, `cli`, and every provisional public
   CLI declaration. Do not encode the stability tier through naming and do not
   add docstring-existence tests.

**Success criteria:** base reflection is permissive; `argument_type` owns only
the question of argparse converter production; contextual parser checks remain
authoritative; selected mapping validation is shared without a second target
reflection; dynamic source precedence is unchanged; parser construction or
parsing never invokes a selected target; and `msup.cli` contains no
underscore-prefixed declarations or undocumented public declarations.

**Validation:** Run `uv run --group dev --extra pydantic pytest
tests/test_cli.py -k 'dynamic or selected or unsupported'`, then
`uv run --group dev --extra pydantic pytest tests/test_cli.py`,
`./run.py type_check`, `./run.py lint_check`, `./run.py format_check`, and
`git diff --check`.

**Validation result:** The focused CLI command passed with 15 tests passed and
41 deselected. The complete CLI command passed all 56 tests. `./run.py
type_check`, `./run.py lint_check`, `./run.py format_check`, and `git diff
--check` passed. `rg -n '^def _|^class _' msup/cli.py` produced no matches.

## Phase 6: Migrate public documentation and complete validation

**Status:** Complete

**Implementation discovery:** `materialize_default` is a provisional public
helper shared by five base and CLI call sites. It preserves lazy default
evaluation, deep-copy isolation, and at-most-once factory behavior without
adding a conversion mode or callback framework.

**Execution override:** The historical normalized LOC thresholds are
informational rather than acceptance criteria. The implementation must retain
the meaningful reuse and branch-collapse requirements and must not compress
formatting, remove required docstrings or errors, move code outside the metric,
or introduce a mode or callback conversion framework merely to reduce LOC.

**Phase 6 validation result:** `./run.py test` passed all 112 tests and 114
parameterized subtests. `./run.py examples`, `./run.py check`, and `git diff
--check` passed. `rg -n '^def _|^class _' msup` produced no matches. Physical
LOC is 1,210 for `msup/base.py` and 642 for `msup/cli.py`. The exact redundant
declaration blocks are `msup/base.py:31-156` (126 lines) and
`msup/cli.py:31-35` (5 lines), producing normalized counts of 1,084 base, 637
CLI, and 1,721 combined. At the Phase 5 commit, physical LOC was 1,400 base and
651 CLI; using its 124-line base and 5-line CLI declaration blocks gives
normalized counts of 1,276 base, 646 CLI, and 1,922 combined. Phase 6 therefore
reduced normalized implementation LOC by 192 base lines, 9 CLI lines, and 201
combined lines through shared semantics and branch collapse.

1. Update `README.md` to describe operation-specific annotation support,
   permissive defaults, strict directionality, recursive dict and JSON
   conversion, and shallow kwargs conversion. State that `to_json` has a
   narrower representable domain than `to_dict`.
2. Replace the direct-function example that expects `from_kwargs` to return a
   dictionary. Show `kwargs_from_dict` for recursive serialized input,
   `from_kwargs` returning a partial, an assertion or observable counter that
   the function has not run, and explicit later invocation.
3. Update `examples/kwargs_for.py` only where needed to demonstrate the new
   composition. Keep the selected target non-invocation output and explicit
   application-owned call.
4. Remove obsolete tests and documentation for relation-aware,
   dictionary-returning `from_kwargs`. Do not retain a deprecated return-shape
   switch or compatibility shim. This branch is still in development and the
   new contract is intentionally breaking.
5. Review the final production diff against `enum` and the current branch.
   Delete validation or conversion branches made redundant by the shared
   selected-argument path. Do not remove top-of-module forward declarations,
   useful public docstrings, or error paths at actual input boundaries merely
   to reduce line count.
6. Audit the complete public surface against the two top-of-plan API lists.
   Confirm that every declaration is public and documented, the stable list is
   compatibility-promised in `README.md`, provisional names are not presented
   as stable, and no declaration in `msup.base` or `msup.cli` begins with an
   underscore. Perform the docstring portion as review, not as an automated
   source-content or introspection test.
7. Record physical LOC and normalized implementation LOC before and after
   execution. Normalized implementation LOC is physical LOC minus only the
   contiguous redundant top-of-module forward-declaration block in each
   module, including that block's formatting guards and declaration docstrings.
   Do not exclude imports, implementation signatures, implementation
   docstrings, or any other production lines. The current normalized baseline
   is 756 for `msup/base.py`, 620 for `msup/cli.py`, and 1,376 combined: current
   physical LOC of 784 and 621 minus declaration blocks of 28 and 1 lines.
8. Record normalized implementation LOC and the meaningful reduction from the
   Phase 5 implementation. The historical pre-plan thresholds are not an
   acceptance gate. Obtain reductions through reuse and branch collapse, not
   compressed formatting, removed docstrings, removed boundary errors, or
   inlining `is_optional` and `maybe_idx`.
9. Inspect the intended collapse points before accepting the result: strict and
   permissive behavior share each directional converter; JSON delegates to the
   dictionary conversion path with an operation literal; `from_kwargs`
   composes `to_kwargs`; all selected mapping shape checks use
   `validate_selected_mapping`; relation-aware owner and direct-function
   decoding share parameter conversion; and CLI consumes its cached selected
   fields without a second reflection or validation implementation.

**Success criteria:** public documentation and examples describe only the new
contract; no caller expects `from_kwargs` to return a dictionary; strict and
permissive behavior are discoverable; all declarations are public and
documented; the stable API is explicitly promoted; no underscore-prefixed
declaration remains; meaningful implementation reuse and branch collapse are
recorded without superficial compression; and the repository's full tests,
examples, type checks, lint, formatting, and whitespace checks pass.

**Validation:** Run `./run.py test`, `./run.py examples`, `./run.py check`,
`git diff --check`, `rg -n '^def _|^class _' msup`, and
`wc -l msup/base.py msup/cli.py`. The `rg` command must produce no matches.
Record the exact declaration-block ranges and normalized calculation so the
comparison is reproducible.

## Final success criteria

- Annotation capability, strict runtime validation, permissive conversion
  routing, recursive dict or JSON transformation, and shallow kwargs binding
  are separate operations. `is_compat` and its tuple contract are deleted with
  no public source-type-routing replacement.
- `strict=False` is the default everywhere and preserves useful coercion plus
  recursively valid identity pass-through. `strict=True` rejects unsupported
  operation annotations and enforces Python-side output validation or canonical
  encoded-source rules at the correct side of each conversion boundary.
- `to_dict` and `from_dict` recursively transform supported fields and retain
  callable, enum, collection, structured model, relation, and nested error-path
  behavior.
- `to_kwargs` only projects top-level declared values. `from_kwargs` constructs
  a class exactly once or returns a non-invoking `functools.partial` for a
  function or method.
- Function partial tests prove filtered keys, normal defaults, open required
  parameters, retained plain-function and unbound-method `self` or `cls`,
  bound-receiver omission, non-invocation, and successful later invocation.
- `kwargs_from_dict` and `kwargs_for` retain recursive selected-argument
  conversion, reject unknown and missing required selected parameters, preserve
  lazy default and factory behavior, and never invoke selected targets.
- Recursive Pydantic v2 `from_dict` and `from_json` use native validation once,
  including native strict mode and relation-free aliases. Shallow
  `from_kwargs(strict=True)` performs msup Python-side checking followed by
  normal construction. Linked fields retain their documented canonical-name
  restriction. Pydantic v1 remains rejected.
- CLI converter capability remains owned by `argument_type`, while contextual
  layout and relation checks remain at their `FieldSpec` and parser call sites.
  Dynamic CLI precedence, help, errors, and non-invocation remain stable.
- The top-of-plan stable public API is explicitly compatibility-promised.
  Every remaining declaration is public and documented, provisional public
  declarations are clearly identified, and neither module contains a
  leading-underscore declaration.
- Physical and normalized line counts are recorded. The implementation records
  its meaningful reduction from the Phase 5 state through shared semantics and
  collapsed branches without treating the historical pre-plan counts as an
  acceptance gate. `is_optional` and `maybe_idx` remain public, documented,
  and uninlined.
- `README.md`, `examples/kwargs_for.py`, and all focused and aggregate
  validation commands describe and verify the same final API.

## Follow-up passes

The follow-ups run in order because each pass reviews the accepted result of
the prior pass. Each pass uses its own worker and reviewer loop and is committed
separately. The production audit scope is limited to lines changed between the
pre-implementation plan commit `d0703db` and the start of each follow-up.

### Follow-up 1: Enforce repository code guidelines

**Status:** Complete

Audit only previously modified production lines against `AGENTS.md` and
`CODE_GUIDELINES.md`. Apply clear, behavior-preserving fixes for documented
rules, including direct control flow, public API structure, declaration order,
naming, comments, and justified abstraction reuse. Do not restyle unchanged
code, mass-format files, or force ambiguous interpretations. Tests may change
only when a behavior-preserving refactor requires a call-site update.

**Code pointers:** `msup/base.py`, `msup/cli.py`, and the changed-line boundary
from `git diff d0703db..HEAD`.

**Success criteria:** every clear guideline violation in the modified
production lines is fixed; ambiguous cases are recorded rather than rewritten;
behavior and the stable API remain unchanged; and aggregate validation passes.

**Validation:** Run `./run.py test`, `./run.py examples`, `./run.py check`, and
`git diff --check`.

**Validation result:** `./run.py test` passed all 112 tests. `./run.py
examples`, `./run.py check` (ty, Ruff lint, and Ruff format), and `git diff
--check` passed. The audit changed only `msup/base.py`; no clear in-scope
violation was found in `msup/cli.py`. Exception-driven union selection, deeper
branch redesign, and broad docstring rewriting remain assigned to Follow-ups 2
through 4.

### Follow-up 2: Remove exceptions used as control flow

**Status:** Complete

Replace expected-outcome exception probing in previously modified production
code with explicit conditionals or return values. Start with
`msup/base.py:union_member`, where candidate selection currently probes union
members by catching conversion errors. Preserve exceptions at invalid input,
precondition, I/O, and external boundaries, and preserve qualified public error
messages and strict or permissive conversion behavior.

**Code pointers:** `msup/base.py:union_member`, `msup/base.py:from_dict_value`,
`msup/base.py:to_dict_value`, and any directly related changed call sites.

**Success criteria:** expected union or conversion route selection does not use
exceptions for normal branching; remaining catches recover, add context, or
translate at a real boundary; public behavior is unchanged; and aggregate
validation passes.

**Validation:** Run focused base conversion tests, then `./run.py test`,
`./run.py examples`, `./run.py check`, and `git diff --check`.

**Implementation discovery:** `ConversionAttempt` carries either a converted
value or the boundary error that prevented conversion. Recursive
`attempt_from_dict_value` and `attempt_union_member` use this result so normal
union candidate selection does not catch conversion exceptions. The public
wrappers retain their signatures and raise the stored error only at their API
boundaries. Constructor, Pydantic validation, callable resolution, enum, and
primitive conversion catches remain boundary translations.

**Validation result:** Focused strict union and conversion tests passed with 3
tests. The complete base and Pydantic suites passed all 56 tests. `./run.py
test` passed all 112 tests. `./run.py examples`, `./run.py check` (ty, Ruff
lint, and Ruff format), and `git diff --check` passed.

### Follow-up 3: Simplify complicated branches

**Status:** Complete

Analyze branch-heavy code in the previously modified production lines after
Follow-up 2. Reduce complexity through direct control flow, stronger local
invariants, and removal of redundant branches. Take out the largest coherent
chunks first only when a helper has at least four same-meaning uses; do not
introduce mode objects, callback walkers, builders, single-use helpers, or
superficial line compression.

**Code pointers:** branch-heavy functions in `msup/base.py` and `msup/cli.py`
identified from the accepted Follow-up 2 implementation and the changed-line
boundary from `d0703db`.

**Success criteria:** complicated branches are materially easier to follow;
the result follows the repository preference for branching and one final
`result` return where values are assembled; no premature abstraction is added;
behavior and public errors remain stable; and aggregate validation passes.

**Validation:** Run focused tests for each changed branch family, then
`./run.py test`, `./run.py examples`, `./run.py check`, and `git diff --check`.

**Implementation discovery:** `attempt_union_member` now computes the concrete
origin once and uses an explicit data table for the repeated coercive source
families while keeping recursive unions, `Any`, enums, and exact matching
direct. `from_cli_args` computes config, environment, and CLI precedence once
per field, caches selector names, and reuses the Pydantic-owner decision.
`to_kwargs` shares validation and assignment while preserving membership plus
indexing for custom mappings. Broader dispatch functions remain intact because
their branches implement distinct required behavior and extraction would add
single-use helpers or a generalized walker.

**Complexity result:** `attempt_union_member` decreased from Ruff McCabe 16 to
10 and from 17 to 12 direct AST branch constructs. `from_cli_args` decreased
from Ruff McCabe 28 to 26 and from 47 to 44 direct AST branch constructs. The
CLI function decreased from 97 to 93 lines.

**Validation result:** Focused base union, kwargs, selected-target, and custom
mapping tests passed with 15 tests. Focused CLI source, precedence, selected,
dynamic, nested, and direct tests passed with 29 tests. `./run.py test` passed
all 112 tests. `./run.py examples`, `./run.py check` (ty, Ruff lint, and Ruff
format), and `git diff --check` passed.

### Follow-up 4: Simplify docstrings

**Status:** Complete

Rewrite docstrings added or modified by this plan in simple language. Preserve
the complete public behavior, constraints, return categories, errors, stable
versus provisional distinction, operation-specific meanings, strict versus
permissive behavior, conversion direction, and non-invocation guarantees.
Keep forward declarations synchronized with implementation docstrings. Remove
jargon when a familiar concrete phrase is equally precise.

**Code pointers:** public docstrings changed since `d0703db` in `msup/base.py`
and `msup/cli.py`, plus `README.md` only if a public contract phrase must stay
consistent.

**Success criteria:** changed public docstrings use plain language without
losing contract details; forward and implementation declarations agree; no
source-content or docstring-existence tests are added; and aggregate validation
passes.

**Validation:** Run `./run.py test`, `./run.py examples`, `./run.py check`, and
`git diff --check`.

**Implementation discovery:** Plain wording can preserve the complete contract
when each docstring states concrete behavior instead of internal terminology.
The operation functions now name every allowed operation, explain the narrower
JSON rules, and state plainly that the operation changes support checks rather
than encode or decode direction. Exact Python and dependency names remain only
where they identify real public concepts.

**Validation result:** An AST comparison with commit `2897285` after removing
docstrings confirmed no executable, signature, or control-flow changes. Every
public declaration remains documented, stable forward and implementation
docstrings match, and the `from_kwargs` overloads and implementation agree.
`./run.py test` passed all 112 tests. `./run.py examples`, `./run.py check` (ty,
Ruff lint, and Ruff format), and `git diff --check` passed. Only
`msup/base.py` and `msup/cli.py` changed; `README.md` already matched the public
contract.
