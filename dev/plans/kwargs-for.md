# Dynamic callable kwargs relation

## Goal

Add a base-owned relation between a callable selector field and a following
`dict[str, Any]` field. The relation resolves an importable function or class,
uses its signature to convert the dependent dictionary, and never invokes or
constructs the selected target. The CLI must use the same relation to add
target-specific options such as `--kwargs.workers` after the target is known.

The implementation starts from the `enum` baseline at commit `abca9b07`.
Production Python LOC means only `msup/base.py` and `msup/cli.py`; tests, plans,
documentation, examples, and runner changes do not count.

## Status

- Phase 1: Complete
- Phase 2: Complete
- Phase 3: Complete
- Phase 4: Not started
- Phase 5: Not started

Update these fields while executing the plan. Use `In progress`, `Complete`, or
`Blocked`, and record the validation result under each completed phase.

## Baseline code map

- `msup/base.py:47-54` defines `FieldSpec`, the shared reflected-field shape.
- `msup/base.py:56-61` unwraps `Annotated` metadata.
- `msup/base.py:124-166` reflects dataclass fields, Pydantic v2 fields, regular
  class constructor parameters, and function or method parameters.
- `msup/base.py:169-175` loads the current simple `module.name` callable form.
- `msup/base.py:324-421` performs annotation-directed value conversion,
  including callable loading and structured model construction.
- `msup/base.py:424-498` serializes values and implements `to_dict`,
  `to_kwargs`, and `from_dict`.
- `msup/cli.py:25-40` defines `CliArg` and reads it from `Annotated` metadata.
- `msup/cli.py:101-181` recursively adds options for structured models.
- `msup/cli.py:184-258` adds direct function options.
- `msup/cli.py:261-288` reads `--Args` and performs the current parse-known
  handling.
- `msup/cli.py:293-385` merges configuration, environment, and CLI sources and
  constructs structured or direct command arguments.
- `msup/cli.py:388-456` validates handlers, builds parsers, and dispatches the
  selected command.
- `tests/test_basic.py:1-357`, `tests/test_cli.py:1-784`, and
  `tests/test_pydantic.py:1-299` are the baseline behavior suites to extend.
- `README.md:150-164` documents callable conversion, nested dotted options,
  defaults, and source precedence.
- `pyproject.toml:1-5` requires Python 3.12, while `pyproject.toml:29-35`
  incorrectly configures Ruff for Python 3.10 and must be aligned with the
  package requirement before using Python 3.12 type alias syntax.

## Public contract and decisions

### Metadata and field link

Add these public base concepts:

```python
type Kwargs = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class Metadata:
    kwargs_for: str | None = None
```

`CliArg` inherits `Metadata`. A CLI relation therefore uses one metadata value:

```python
@dataclass(frozen=True)
class CliArg(Metadata):
    help: str = ""
    short: str | None = ""
    env: str | None = None
    pos: bool = False
    opt: bool = True
    secret: bool = False
```

Extend `FieldSpec` with one static, backward relation link:

```python
@dataclass
class FieldSpec:
    name: str
    annotation: Any
    annotations: list[Any]
    default: Any = MISSING
    default_factory: Any = MISSING
    kwargs_relation: "FieldSpec | None" = None
```

`kwargs_relation` is set only on the dependent kwargs field and references its
selector. The selector does not point forward, so there is no cycle. Do not
add `relation_index`, an
inverse selector map to the schema, relation edge lists, or a `FieldNode`.
Consumers that need the dependent field for a selector can scan the small
field list. Add a helper only if that scan has more than three real call sites.

`fields_or_init_kwargs` becomes the authoritative two-pass algorithm:

1. Reflect every field exactly as it does on the enum baseline. No default
   factory is evaluated in this pass.
2. Walk the completed list in declaration order, validate every
   `Metadata(kwargs_for=...)`, and assign the dependent field's
   `kwargs_relation` to the already-created preceding selector `FieldSpec`.

The second pass validates all of the following before conversion or parser
construction:

- At most one `Metadata` instance, including `CliArg` subclasses, occurs in a
  field's annotations.
- The dependent annotation is exactly `dict[str, Any]` or `Kwargs`, is not
  optional, and names a different field.
- The selector exists, precedes the dependent field, is annotated as
  `Callable`, and is not itself a dependent relation field.
- One selector has at most one dependent kwargs field.
- Relation owners may be dataclasses, Pydantic v2 models, regular class
  constructors, or direct functions and methods. Pydantic v1 remains
  unsupported.

Python 3.12 creates a `typing.TypeAliasType` object for `Kwargs`.
`get_origin(Kwargs)` does not expose the `dict` origin, so generic origin checks
cannot accidentally treat the alias like its value. Add one explicit
annotation-normalization operation that recognizes `TypeAliasType` and reads
its `__value__` before relation type validation and collection conversion.
Preserve the declared alias on `FieldSpec` for reflection and diagnostics, but
normalize it whenever code needs its origin or type arguments. Accept both
`Kwargs` and the literal `dict[str, Any]` after normalization.

The link describes only the static owner schema. Never store the selected
runtime callable or its reflected parameter fields on a `FieldSpec`. Those
values depend on defaults, `--Args`, environment, explicit selector options,
and subcommand selection for one parse.

### Callable references and selected signatures

Keep callable selectors annotated as `Callable[..., Any]`. Python classes are
callable, so this covers functions and class targets without an artificial
union. Runtime checks still accept only classes, functions, and methods for
signature reflection. Callable instances, partials, lambdas, and local
functions are rejected for canonical serialization.

Upgrade callable references from the baseline's one-attribute loader to the
canonical `module.qualname` form. Loading finds the longest importable module
prefix and traverses the remaining attributes. Dumping uses `__module__` and
`__qualname__`, reloads the reference, and requires object identity. Loading a
callable imports Python code, so dictionary, JSON, and CLI references are
trusted input and the documentation must say so.

Add a strict selected-target signature reader. Unlike general
`fields_or_init_kwargs`, it must reject positional-only parameters, `*args`,
`**kwargs`, missing annotations, and annotations unsupported by the existing
conversion path. It accepts positional-or-keyword and keyword-only parameters.
It omits `self` and `cls` for classes. A selected target's omitted parameters
with Python defaults remain absent from the explicit kwargs mapping so the
application's later call applies the target's normal defaults.

### Base conversion and serialization

Add public non-invoking functions:

```python
def kwargs_from_dict(
    target: type | Callable[..., Any],
    values: Mapping[str, Any],
    *,
    field_name: str = "kwargs",
) -> dict[str, Any]: ...


def from_kwargs(
    owner: type | Callable[..., Any],
    values: Mapping[str, Any],
) -> dict[str, Any]: ...
```

`kwargs_from_dict` reflects the selected signature, rejects unknown or missing
required parameters, and converts each explicit value through
`from_dict_value`. It returns a new dictionary and never calls the target.

`from_kwargs` walks linked owner fields in declaration order. An ordinary
selector is converted first. When its dependent field is reached, the function
reads `field.kwargs_relation`, obtains the already-converted selector from
the result, merges the dependent mapping over its copied default, and delegates
to `kwargs_from_dict`. There is no relation preparation lifecycle.

For each active relation field in one top-level operation:

- Deep-copy a declared mutable default before use.
- Evaluate a `default_factory` at most once and only if its default layer is
  needed. A higher-priority selector source replaces a selector default, so an
  overridden selector factory is called zero times.
- Evaluate a dependent kwargs factory only when its baseline mapping is needed
  because the field is otherwise absent or higher mapping sources overlay it
  by key. Do not evaluate it for an inactive optional containing owner or while
  serializing already-materialized values.
- Replace the selector default with an explicit selector source.
- Overlay explicit kwargs keys on the copied kwargs default or factory result.
- Inject all materialized relation values into dataclass construction so the
  dataclass constructor cannot evaluate the factory again.
- Leave ordinary omitted fields to normal dataclass or function defaults.

`from_dict` uses `from_kwargs` for dataclass owners and constructs only the
owner. Direct function owners use `from_kwargs` directly and are not invoked.
`from_json` continues to route through `from_dict`.

`to_dict` follows the same linked field order. When it reaches a selector with
a dependent field, it emits the canonical callable reference. When it reaches
the dependent field, it reads the selector value from the source object or
mapping, validates and types the explicit kwargs with `kwargs_from_dict`, and
serializes those values against the selected parameter annotations. Support
`to_dict(mapping, type_class=function)` and the corresponding `to_json` call.
A partial typed mapping may omit both relation fields, but kwargs without its
selector is an error. `to_kwargs` remains a shallow field selection helper.

Nested dataclass owners are converted through a relation-aware recursive owner
decoder, not by blindly calling `from_dict_value` on a relation-owning
container. Each nested owner receives a fresh linked field list, so same-named
relations at different paths are independent. Multiple relation pairs in one
owner are processed independently in declared order. Relation-free structured
fields continue through the existing `from_dict_value` and `to_dict_value`
paths.

### CLI parsing and source precedence

Use one argparse tree and parse the original argv twice:

1. Build the complete static parser with `add_help=False`. Include selector
   options, whole dependent mapping options such as `--kwargs`, `--Args`, and
   ordinary static fields. Run `parse_known_args` on the unchanged argv.
2. Select the active command, merge and resolve effective selectors, reflect
   only the selected targets, recursively add their dotted options to the same
   parser, add normal `-h` and `--help` actions, then run `parse_args` on the
   same unchanged argv.

Mutating the bootstrap parser is simpler than rebuilding it and avoids a
parallel parser schema. Keep only parse-local plain dictionaries keyed by
qualified field path for materialized raw owner trees, resolved targets, and
selected parameter fields. These values genuinely cross the two parse passes.
Do not introduce `RelationContext`, `RelationPath`, `GeneratedOption`,
`FieldNode`, a runtime-generated dataclass, or a public parser-state API.

Bootstrap nested owners as raw trees. Before any selector is pinned, a
containing JSON, environment, or whole-field CLI value for a dataclass that
owns a relation must become either a raw mapping or a shallow projection of an
already-existing object. Do not call relation-aware `from_dict_value`,
`from_kwargs`, or a dataclass constructor for that container during bootstrap.
Recursively collect its static relation paths, then pin selectors only after
all static source layers for those paths have been applied.

Apply this exact raw-tree precedence from lowest to highest:

1. Lazily copied owner field default or one lazy evaluation of its
   `default_factory`, only when the default layer is needed.
2. The matching `--Args` subtree.
3. The containing structured field's environment value.
4. The containing structured field's whole CLI option.
5. Descendant field environment values and descendant whole-field CLI options.
6. Descendant dotted CLI options.
7. For a relation kwargs field, selected-target parameter environment values.
8. Generated target-parameter dotted CLI options such as
   `--kwargs.workers` and `--kwargs.limits.memory_gb`.

Mapping layers overlay by present key and never mutate a default or source
object. A containing whole-object layer establishes the raw subtree at that
point, then descendant layers override its leaves. An already-materialized
containing object is shallow-projected by its reflected fields and is treated
as the authoritative containing layer, so its own factory has already run and
must not be evaluated by the parser. A dependent kwargs mapping retains its
special overlay contract: its copied default or factory mapping supplies
missing keys and each higher mapping source overrides only supplied keys.

Determine factory need after collecting the higher-priority raw sources for a
path, but before pinning:

- Skip a selector factory when any higher selector source exists. Evaluate it
  once when it is the only way to select a target.
- Evaluate a dependent kwargs factory once only when it can supply a selected
  parameter absent from higher mapping sources. Skip it when higher sources
  cover every selected parameter, its optional containing owner is inactive,
  or an authoritative already-materialized owner supplies the mapping.
- Evaluate a containing owner factory once only when its projected fields are
  needed to fill leaves not supplied by a higher containing layer. A whole
  existing object makes that projection authoritative and suppresses the
  factory.
- For help, materialize only defaults needed to identify selected targets.
  Never evaluate a dependent kwargs factory merely to display its target's
  options. An explicit selector suppresses its selector factory; a selector
  supplied only by a factory evaluates that factory once.

Within the same tree, each selector follows its field default or factory,
`--Args` subtree, containing layers, selector environment, whole selector CLI,
and descendant dotted CLI in that order. If any higher source supplies the
selector, skip its factory entirely. Resolve it after every static selector
layer is known. Pin that callable for generated option discovery and final
conversion so target resolution occurs once per parse.

After the final parse, run one concrete recursive decoder over the bootstrap
tree. For an owner path it:

1. Walks the linked fields once in declaration order.
2. Converts each ordinary scalar or relation-free structured field once.
3. Recurses into a raw nested dataclass owner when that type contains a static
   relation.
4. Injects the already-pinned selector for a selector field without rereading
   its default or factory.
5. Converts a dependent mapping from the cached selected parameter fields,
   injects the typed kwargs, and never rereads its default or factory.
6. Returns a kwargs dictionary for a direct function owner, constructs a
   dataclass or regular class once after all fields are ready, or calls
   Pydantic v2 `model_validate` once with the typed relation values.

This decoder is the only final CLI construction path for root and nested
relation owners. It reuses pure base helpers for cached selected-field
conversion and final owner construction, but does not call public
`from_kwargs`, because doing so would rematerialize defaults. It never invokes
the selected target. Relation-free owners retain the current direct conversion
path.

Generated target options reuse existing long-option conversion, help,
environment, secret, Enum, collection, and nested structured-model rules.
They use only canonical qualified long names in this feature. Existing static
field short aliases remain unchanged. Reject a selected target parameter with
a non-empty `CliArg.short` during dynamic option discovery; do not add short
name qualification or collision machinery.
Recursion is implemented with direct functions carrying a tuple path. A
selected target parameter such as `limits: Limits` retains its literal name
and produces `--kwargs.limits.memory_gb`; it is never flattened. A statically
known `run(limits: Limits)` retains `--limits.memory_gb`.

Support relations nested inside statically declared dataclass fields and
multiple independent relations at any finite static depth. Do not support a
second `Metadata(kwargs_for=...)` relation inside a structured parameter of a
dynamically selected target in this feature. Detect and reject it while
generating options with the full path. This boundary avoids unbounded dynamic
parser expansion while still supporting ordinary structured target parameters.

Reject a positional or remainder argument anywhere in a command parser scope
that also contains a dynamic relation. Unknown dynamic options must survive
bootstrap parsing for the final pass, which is incompatible with remainder
capture. Preserve current remainder behavior for relation-free commands.

### Help behavior

- Root help with no selected subcommand is static and imports no target.
- Command help with no effective selector is static and reports no generated
  target options.
- If a selector is effective from a default, factory, `--Args`, environment,
  or explicit option, command help resolves that selector once and includes
  its generated options.
- `--help` before or after selector and generated options has the same result
  because both passes receive the original argv unchanged.
- Help exits through argparse with status 0. Invalid selected targets and
  signatures fail with qualified errors rather than silently falling back to
  static help.

### Errors and Pydantic policy

All schema, conversion, serialization, and CLI errors name the qualified owner
path, dependent field, and parameter where applicable, for example
`Job.kwargs.limits.memory_gb`. Reject missing selectors, non-callable selector
values, non-mapping kwargs defaults or sources, unknown kwargs, missing
required target parameters, unsupported signatures, and unsupported nested
dynamic relations before handler dispatch. Generated options use argparse's
configured conflict policy.

Regular class owners use the same declared-order relation conversion as
dataclasses and are constructed once after all fields are typed. Pydantic v2
owners convert only their linked selector and dependent fields before calling
`model_validate` exactly once, preserving native field and model validation for
the complete object. Canonical field names and simple string validation aliases
are supported for linked fields; reject complex alias paths or choices on a
linked field with a qualified error. Pydantic v1 keeps its existing rejection.

## Concrete end-to-end example

The implementation and tests must include an equivalent example with a real
importable module path:

```python
from dataclasses import MISSING, dataclass, field
from typing import Annotated, Any, Callable

from msup.base import FieldSpec, Kwargs
from msup.cli import CliArg


calls = 0


@dataclass
class Limits:
    memory_gb: int = 4


def default_kwargs() -> dict[str, Any]:
    return {"label": "factory"}


def launch(
    workers: Annotated[int, CliArg(env="JOB_WORKERS")],
    limits: Limits,
    label: str = "target-default",
) -> None:
    global calls
    calls += 1


@dataclass
class Job:
    target: Callable[..., Any] = launch
    kwargs: Annotated[
        Kwargs,
        CliArg(kwargs_for="target", help="Arguments for the selected target"),
    ] = field(default_factory=default_kwargs)
```

After reflection pass 1, the relevant values are conceptually:

```python
target_field = FieldSpec(
    name="target",
    annotation=Callable[..., Any],
    annotations=[],
    default=launch,
    default_factory=MISSING,
    kwargs_relation=None,
)
kwargs_field = FieldSpec(
    name="kwargs",
    annotation=Kwargs,
    annotations=[
        CliArg(
            kwargs_for="target",
            help="Arguments for the selected target",
        )
    ],
    default=MISSING,
    default_factory=default_kwargs,
    kwargs_relation=None,
)
```

After pass 2, `target_field` is unchanged and
`kwargs_field.kwargs_relation is target_field`. No runtime target parameter
schema is attached to either field.

With `JOB_WORKERS=4`, parse this unchanged argv twice:

```text
--Args {"kwargs":{"label":"config"}} \
--kwargs {"limits":{"memory_gb":"12"}} \
--kwargs.workers 6 \
--kwargs.limits.memory_gb 24
```

The bootstrap pass produces these raw parse-local values:

```python
selected_target = launch
raw_kwargs = {
    "label": "config",
    "limits": {"memory_gb": "12"},
}
```

It then reflects, but does not store on `FieldSpec`, these selected-target
parameter fields:

```python
[
    FieldSpec("workers", int, [CliArg(env="JOB_WORKERS")]),
    FieldSpec("limits", Limits, []),
    FieldSpec("label", str, [], default="target-default"),
]
```

The final pass applies the parameter environment and dotted options:

```python
effective_raw_kwargs = {
    "label": "config",
    "limits": {"memory_gb": "24"},
    "workers": "6",
}
typed_kwargs = {
    "label": "config",
    "limits": Limits(memory_gb=24),
    "workers": 6,
}
job = Job(target=launch, kwargs=typed_kwargs)
```

`calls` is still 0 after reflection, both parser passes, `from_kwargs`,
`from_dict`, `to_dict`, and `to_json`. Only application code may invoke the
target:

```python
job.target(**job.kwargs)
assert calls == 1
```

This example proves the direct `--kwargs.workers` option, recursive structured
`--kwargs.limits.memory_gb` option, source overlays, typed final values, and
no-invocation contract.

## Phase 1: Link and validate relation fields

**Status:** Complete

**Validation result:** 79 tests and 44 subtests passed; `./run.py check`
passed; `git diff --check` passed; correctness and code-guideline reviews
approved the phase.

### Implementation

1. Add `Kwargs`, `Metadata`, `metadata_from_annotations`, and the public
   declarations to `msup/base.py` without importing `msup.cli`.
2. Add `kwargs_relation` to `FieldSpec` and implement the second pass inside
   `fields_or_init_kwargs`. Keep reflection as pass 1 and relation validation
   and linking as pass 2.
3. Normalize `TypeAliasType` values for origin and argument inspection while
   preserving `Kwargs` in reflected annotations, and set Ruff's target version
   to `py312` at `pyproject.toml:29-35`.
4. Make `CliArg` inherit `Metadata` and make CLI metadata discovery share the
   base duplicate check.
5. Add canonical callable loading and dumping and strict selected-target
   signature validation. Reuse ordinary `FieldSpec` values for selected
   parameters without attaching them to owner fields.

### Tests

- Assert the public `fields_or_init_kwargs` result contains the validated
  one-way kwargs relation link and that conversion behavior uses it. Do not
  expose or test an intermediate reflection pass.
- Cover valid dataclass, direct-function, regular-class, and Pydantic v2 pairs,
  plus duplicate metadata, wrong dependent type, missing, self, forward,
  non-callable, reused, and relation selectors.
- Cover both `Kwargs` and literal `dict[str, Any]` annotations under Python
  3.12.
- Cover canonical nested qualified-name loading, identity-checked dumping, and
  rejection of non-importable or unsupported callable forms.
- Cover accepted keyword-only parameters and every rejected signature form.

### Validation

Run focused base and metadata tests, `./run.py type_check`, and
`git diff --check`.

### Success criteria

- Every valid dependent field directly references its preceding selector
  `FieldSpec` after one call to `fields_or_init_kwargs`.
- No relation index, reverse relation schema, runtime target, or target
  parameter schema is stored on `FieldSpec`.
- Base imports remain independent of `msup.cli`.

## Phase 2: Add symmetric non-invoking base conversion

**Status:** Complete

**Validation result:** 82 tests passed; `./run.py check` passed;
`git diff --check` passed; correctness and code-guideline reviews approved
the phase. Production Python is 1,153 lines, within the user-approved 10%
margin of the 1,110-line target (effective ceiling 1,221).

### Implementation

1. Implement `kwargs_from_dict` and `from_kwargs` as direct declared-order
   field algorithms using `kwargs_relation`.
2. Route dataclass and regular-class `from_dict` and JSON conversion through
   the relation-aware path. Keep direct functions non-invoking. For Pydantic v2
   owners, convert linked values once before one native `model_validate` call.
3. Make `to_dict` and `to_json` relation-aware for dataclass objects and typed
   direct-function mappings. Validate and serialize dependent values against
   the selected target fields.
4. Implement copied defaults, lazy at-most-once factories, overlay semantics,
   multiple pairs, and finite nested dataclass conversion without
   prepared-state types.
   The base recursive owner decoder may construct typed nested fields but
   returns an argument mapping for its requested owner; `from_dict` constructs
   the requested root dataclass, while direct `from_kwargs` never calls its
   function owner.

### Tests

- Round-trip function and class targets through dictionaries and JSON with
  scalar, Enum, collection, dataclass, and Pydantic v2 target parameters.
- Cover direct-function owners, nested owners, multiple pairs, partial typed
  mappings, copied mutable defaults, and factory overlays.
- Count selector and kwargs factory calls and assert zero when a higher source
  makes the default layer unnecessary and one when the layer supplies a value
  or mapping baseline. Cover root and nested owners.
- Assert target bodies and class constructors remain untouched during all
  conversion and serialization operations.
- Cover missing selector, non-mapping kwargs, unknown and missing parameters,
  unsupported annotations, and fully qualified error paths.

### Validation

Run `./run.py test`, `./run.py type_check`, and `git diff --check`.

Enforce this cumulative production gate from enum after Phase 2:

```text
msup/base.py + msup/cli.py <= 1,110 lines
cumulative increase <= 156 lines
```

### Success criteria

- Dictionary and JSON loading and dumping preserve a canonical selected target
  and typed explicit kwargs without invocation.
- Every relation factory is evaluated at most once per top-level operation and
  only when its default layer is needed.
- Regular-class and Pydantic v2 relation owners, Pydantic selected parameters,
  and the Pydantic v1 rejection are explicit and tested.

## Phase 3: Add target-specific options with two parser passes

**Status:** Complete

### Implementation

1. Refactor static option registration only enough to defer target parameter
   options for linked kwargs fields. Keep selectors and whole kwargs options
   static.
2. Build one parser tree without help, parse known static values, select the
   command, recursively normalize containing sources into raw trees, and
   discover all active static relation paths without constructing a
   relation-owning container.
3. Lazily materialize needed defaults at most once, apply the complete nested
   source precedence, resolve each selected target once, and retain only the
   three necessary path-keyed maps: raw owner trees, selected targets, and
   selected parameter fields.
4. Recursively add generated options to the same parser, then add help actions
   and parse the original argv again. Deliver baseline static help and
   minimally correct expanded help listing the selected target's canonical
   long options in this phase. Carry paths as tuples through ordinary
   functions instead of building schema node or generated option classes.
5. Run the one recursive final constructor over bootstrap-materialized values
   and pinned target maps. Dispatch only the declared command handler.
6. Reject dynamic target parameter short aliases, positional or remainder
   conflicts, and nested dynamic relations in selected structured parameters
   before final parsing. Let argparse apply its configured long-option conflict
   policy when generated and static options collide.
7. Reuse pure base selected-field conversion and owner-construction helpers so
   CLI conversion does not duplicate unknown, missing, typing, or native class
   construction behavior. Keep argparse, environment, precedence, and pinned
   parse state in `msup.cli`.
8. Support regular-class and Pydantic v2 relation owners at root and nested
   paths without treating every arbitrary class annotation as a structured CLI
   model.

### Tests

- Cover `--kwargs.workers`, `--kwargs.limits.memory_gb`, whole kwargs JSON and
  files, `--Args`, relation and parameter environments, and every precedence
  boundary.
- Cover default and explicit function and class targets, direct handlers,
  dataclass handlers, subcommands, nested owner relations, and multiple pairs.
- Cover a nested relation owner supplied through `--Args`, containing whole
  JSON, containing field environment, and an already-materialized containing
  object, with descendant environment, whole-field, and dotted overrides.
- Count target resolution and selector, kwargs, and containing-owner factories
  for normal parses, static help, expanded help, and nested owners. Assert the
  required zero-call and one-call cases.
- Cover source replacement of a default target before target-specific kwargs
  are converted.
- Cover regular-class and Pydantic v2 relation owners, including native
  Pydantic validation, simple aliases, and at-most-once construction.
- Assert generated target parameters have qualified long options, reject their
  short aliases, and preserve existing static field short aliases.
- Preserve all relation-free CLI and positional remainder tests.
- Prove final dispatch invokes the handler once and never invokes the selected
  target or class constructor.

### Validation

Run focused CLI and help tests, the full `./run.py test`,
`./run.py type_check`, and `git diff --check`.

Completed validation: `./run.py test` passed 97 tests; `./run.py check` passed
type, lint, and format checks; `git diff --check` passed. Production code is
1,443 lines (`msup/base.py` 741 and `msup/cli.py` 702), within the
user-approved 10 percent ceiling of 1,445 lines. Separate correctness and
code-guidelines reviews approved the final worktree and found no unnecessary
validation.

Enforce this cumulative production gate from enum after Phase 3:

```text
msup/base.py + msup/cli.py <= 1,294 lines
cumulative increase <= 340 lines
```

### Success criteria

- One parser tree consumes unchanged argv in a bootstrap pass and a final
  pass, and generated options are available only for the effective target.
- Parse-local state contains no duplicate owner relation graph and no runtime
  generated model.
- Source precedence, recursive structured options, multiple and nested owner
  relations, and lazy at-most-once behavior match the public contract.
- Static help and selected-target help are usable before Phase 4 begins its
  exhaustive hardening pass.

## Phase 4: Complete help, errors, and compatibility boundaries

**Status:** Not started

### Implementation

1. Harden the Phase 3 root, command, static, and target-specific help behavior
   across subcommands, selector sources, argument ordering, and failures.
2. Qualify parser-generation and conversion failures with owner and parameter
   paths. Preserve argparse status 0 for help and status 2 for invalid option
   values.
3. Enforce the remainder, dynamic-inside-dynamic, Pydantic v1, and complex
   linked-field alias boundaries consistently at every entry point. Verify
   argparse's configured option-conflict behavior.
4. Verify existing Enum, optional, collection, secret, short option, nested
   model, subcommand, and configuration behavior remains unchanged outside
   relations.

### Tests

- Cover root help without imports, static command help without a selector, and
  expanded help selected from every selector source.
- Cover `--help` ordering relative to selector and generated options.
- Cover invalid import references, non-callables, signature failures, unknown
  generated options, argparse conflict handling, remainders, and nested dynamic
  relations.
- Run all existing baseline tests without weakening assertions.

### Validation

Run `./run.py test`, `./run.py check`, and `git diff --check`.

### Success criteria

- Help is deterministic, target-aware when possible, and side-effect free
  apart from importing a selected trusted target.
- Unsupported boundaries fail explicitly before command dispatch.
- Relation-free behavior remains compatible with the enum baseline.

## Phase 5: Document, demonstrate, and measure

**Status:** Not started

### Implementation

1. Add a dependency-free executable example based on the concrete example in
   this plan. Show dictionary or JSON conversion, dynamic CLI options, and the
   application's explicit target call.
2. Update `README.md` with `Kwargs`, `Metadata`, inherited `CliArg`, canonical
   callable references, trusted imports, no invocation, source precedence,
   defaults and factories, structured paths, help behavior, direct-function
   usage, and Pydantic policy.
3. Add deterministic example invocations to `run.py` only if needed by the
   repository's existing examples workflow.
4. Measure production Python LOC from the exact enum baseline and record the
   result below. If the hard budget is exceeded, simplify production code
   before considering the plan complete.

### Production LOC budget

| File | Enum baseline | Hard maximum | Maximum increase |
| --- | ---: | ---: | ---: |
| `msup/base.py` | 498 | 638 | 140 |
| `msup/cli.py` | 456 | 676 | 220 |
| Total | 954 | 1,314 | 360 |

The hard budget is a maximum net increase of 360 production lines from the
enum baseline. Aim for a stretch result at or below 1,250 total production
lines, but do not compress readable control flow merely to reach the stretch
number. Tests, plans, docs, examples, and runner changes are excluded from this
measurement.

Record final measurements here during execution:

- `msup/base.py`: Pending
- `msup/cli.py`: Pending
- Total production LOC: Pending
- Net increase from enum: Pending

### Validation

Run from the repository root:

```bash
./run.py test
./run.py check
./run.py examples
git diff --check
wc -l msup/base.py msup/cli.py
git diff --numstat enum -- msup/base.py msup/cli.py
```

Inspect static help, selector-specific help, whole kwargs JSON, direct dotted
kwargs, nested structured dotted kwargs, environment precedence, and the
example's side-effect counter.

### Success criteria

- The README and executable example are sufficient to use the feature without
  prior knowledge of this plan.
- Every repository validation command passes.
- Production code remains within the 1,314-line hard maximum and contains none
  of the relation index or parser-state frameworks rejected by this plan.

## Final success criteria

- `Annotated[Kwargs, Metadata(kwargs_for="target")]` sets the dependent
  `FieldSpec.kwargs_relation` to its preceding callable selector during pass 2
  of `fields_or_init_kwargs`.
- No static field stores a runtime-selected callable or dynamic parameter
  schema, and there is no separate relation index or relation tree.
- Dataclass, regular-class, Pydantic v2, and direct-function dictionary
  conversion, JSON conversion, and serialization are symmetric and typed,
  evaluate needed defaults and factories at most once, and never invoke or
  construct the selected target.
- The CLI uses one parser tree in two unchanged-argv passes to expose options
  such as `--kwargs.workers` and `--kwargs.limits.memory_gb` for the effective
  target.
- Source precedence, static and expanded help, multiple and nested owner
  relations, structured target parameters, errors, and Pydantic policy are
  explicit and fully tested.
- Production Python is no more than 360 lines above the 954-line enum baseline.
