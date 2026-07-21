# Refactor CLI metadata, Pydantic v2 models, and direct function commands

## Goal

Replace the dataclass-specific `cliarg(...)` field-default API with portable
`Annotated[T, CliArg(...)]` metadata. Extend the existing dataclass
serialization and CLI paths to support Pydantic v2 models without making
Pydantic a runtime dependency. Allow CLI command handlers with one or more
named, typed parameters while preserving the existing one-structured-argument
command form.

## Recommended approach and decisions

- Make `typing.Annotated[T, CliArg(...)]` the only supported way to attach CLI
  metadata. `CliArg` is a small immutable metadata value, not a
  `dataclasses.Field`. This works the same way for dataclasses, Pydantic v2
  models, and function parameters, and leaves default ownership with Python,
  dataclasses, or Pydantic.
- Define `CliArg` and its `Annotated` metadata handling directly in
  `msup.cli`. Keep `msup.base` CLI-agnostic: it strips generic `Annotated`
  wrappers for serialization and does not import or inspect `CliArg`.
- Treat the API change as intentionally breaking. Do not retain the old
  `field = cliarg(default=...)` compatibility shim. Migrate all in-repository
  examples and tests to `CliArg(...)` in the same change.
- Support Pydantic v2 only. Import Pydantic only inside the narrow helper that
  examines a candidate class or instance, catch `ImportError` there, and treat
  the candidate as non-Pydantic when it is unavailable. Declare Pydantic in a
  published `pydantic` extra, not `[project.dependencies]`. Make that extra an
  explicit input to the default test and coverage recipes, so a supported
  integration is always tested without becoming a required runtime dependency.
- Separate supported integrations from heavyweight examples. Pydantic is a
  supported library integration and therefore has a published extra plus
  mandatory unit and CLI tests. PyTorch is only an example dependency and
  belongs in an isolated `examples/` project with its own `pyproject.toml` and
  lockfile. Root test, lint, and coverage environments must not install or
  resolve example-only dependencies.
- Keep `fields_or_init_kwargs` as the structured-model discovery boundary.
  Extend it to return a common internal field shape for dataclasses, Pydantic
  v2 models, and regular constructors, rather than adding a parallel
  serialization implementation.
- Preserve source precedence for model and direct-parameter commands: command
  line, environment, `--Args` JSON/config file, then declared default. Direct
  functions have no nested dotted options in this change; structured dataclass
  and Pydantic arguments retain existing nested options.
- Interpret "variable arguments" as a variable number of named, typed
  function parameters. Reject `*args` and `**kwargs` with a direct `TypeError`.
  Do not silently ignore them, unlike regular-class serialization currently
  does.

## Public API after the refactor

```python
from dataclasses import dataclass, field
from typing import Annotated

from msup.cli import CliArg, cli

@dataclass
class DataclassArgs:
    values: Annotated[list[int], CliArg(help="values", short="v")] = field(
        default_factory=lambda: [1, 2]
    )

def run(
    count: Annotated[int, CliArg(help="item count")],
    ratio: Annotated[float, CliArg(help="ratio", short="r")] = 1.5,
) -> None:
    print(count, ratio)

cli(run)
```

```python
from typing import Annotated

from pydantic import BaseModel, Field

from msup.cli import CliArg

class PydanticArgs(BaseModel):
    values: Annotated[list[int], CliArg(help="values", short="v")] = Field(
        default_factory=lambda: [1, 2]
    )
```

`CliArg` accepts only CLI presentation and source metadata: `help`, `short`,
`env`, `pos`, `opt`, and `secret`. `short` is an optional string; `None` means
there is no short option. Defaults remain ordinary parameter defaults,
`dataclasses.field(...)`, or `pydantic.Field(...)`.

## Dependency graph

```text
Phase 0: establish optional-dependency and test policy
    -> Phase 1: metadata and shared field discovery
    -> Phase 2: serialization and Pydantic models
    -> Phase 3: structured CLI model arguments
    -> Phase 4: direct named function parameters
    -> Phase 5: documentation, compatibility removals, full validation
```

Phase 0 is a blocking prerequisite for every Pydantic implementation step.
Phases 2 and 3 share the model-field contract from Phase 1. Phase 4 reuses the
argument construction and source-conversion contract stabilized in Phase 3.

## Phase 0: Establish optional-dependency, example, and test policy

**Status:** in progress

### Implementation

1. Add a published optional dependency in `pyproject.toml`:

   ```toml
   [project.optional-dependencies]
   pydantic = ["pydantic>=2,<3"]
   ```

   This extra is the only supported consumer installation path for Pydantic:
   `pip install 'msup[pydantic]'`. Do not add Pydantic to
   `project.dependencies` or duplicate it in the root `dev` group.
2. Update the root `test` and `coverage` Just recipes to select the extra
   explicitly, for example `uv run --group dev --extra pydantic pytest ...`.
   This makes Pydantic tests mandatory for normal contributor and CI
   validation while keeping `pip install msup` dependency-free.
3. Add a dedicated `tests/test_pydantic.py`. Do not use `pytest.importorskip`
   or conditional skips: Pydantic is selected by the root test recipes, so a
   missing or broken integration must fail those recipes. This file owns both
   serialization and CLI coverage for Pydantic v2.
4. Add a dependency-free import check that runs without optional extras, such
   as `uv run --no-default-groups --no-extra python -c 'import msup.base;
   import msup.cli'`. It proves module import remains valid when Pydantic is
   not installed. Keep Pydantic detection local with `try`/`except ImportError`
   in the candidate-inspection helper; never import it at module scope.
5. Add `examples/pyproject.toml` and `examples/uv.lock` as a non-package uv
   project (`[tool.uv] package = false`). Its dependencies are `msup[pydantic]`
   from the editable repository-root path source and `torch>=2`:

   ```toml
   [project]
   dependencies = [
       "msup[pydantic]",
       "torch>=2",
   ]
   ```

   Every example can then run with `uv run --project examples ...` without an
   extra selector. Document that users needing a CUDA-specific PyTorch build
   must adjust the isolated examples project's Torch source or install their
   platform-appropriate build before running the examples. Do not add PyTorch
   to root package extras, root dependency groups, or the root lockfile.
6. Add a `just examples` recipe that runs a deterministic smoke invocation of
   every example in the isolated examples environment, including the Pydantic
   example added by this plan and `pt_basic.py test_model`. Supply all required
   CLI values, use a temporary output directory for examples that write files,
   and set `PYTHONPATH=.` where the current examples import from the repository
   root. The recipe must fail on any example error and must not use an explicit
   `--extra` selector. Do not include the heavyweight examples recipe in the
   default `just` target or coverage command. If CI later needs to exercise it,
   add a separate platform-specific job rather than expanding the default test
   matrix.

The examples project and lockfile are established in this phase. Implement the
`just examples` smoke recipe in Phase 5, after Phase 1 has migrated every
example from the removed `cliarg(...)` API. This keeps each accepted milestone
runnable instead of adding a recipe that is known to fail before migration.

### Implementation progress

- Complete: published the `pydantic` extra, selected it in the root test and
  coverage recipes, and added the `no-extra-import` validation recipe. The
  root lockfile includes Pydantic only for the extra and no Torch dependency.
- Complete: created the isolated non-package examples project and lockfile;
  Torch is resolved only by `examples/uv.lock`.
- Remaining: add mandatory Pydantic tests after the shared model contract is
  implemented, then add the deferred example smoke recipe after example
  migration.

### Code pointers

- `pyproject.toml:1-44` contains published metadata and root development
  dependencies.
- `justfile:9-13` defines the default test and coverage environments.
- `examples/pt_basic.py:1-106` is the current unisolated PyTorch example.
- `examples/pyproject.toml` and `examples/uv.lock` are the new isolated
  examples environment.
- `README.md:53-61` documents the PyTorch example and must point to the
  examples project setup.

### Tests and validation

- `just test` and `just coverage` must run `tests/test_pydantic.py` without
  skips and include its coverage in the normal report.
- Run the no-extra import check after the normal test suite; it must import
  `msup.base` and `msup.cli` successfully without Pydantic installed.
- Run `just examples` after locking the examples project. It must execute a
  deterministic smoke invocation of every documented example without an extra
  selector. This is explicit example validation, not a default test-suite
  dependency.

### Success criteria

- `msup[pydantic]` is the documented installation path for the supported
  Pydantic v2 integration, and `pip install msup` still installs no Pydantic.
- Pydantic v2 tests are mandatory in `just test` and `just coverage` and have
  no conditional skip.
- The root lockfile and default test environment contain no PyTorch dependency.
- All examples are reproducible from `examples/uv.lock`; the PyTorch example
  no longer relies on an undeclared ambient installation.

## Phase 1: Establish portable metadata and structured-field discovery

**Status:** complete

### Implementation

1. Add an immutable `CliArg` dataclass and an `Annotated` helper directly in
   `msup/cli.py`. The helper returns the base type and selects at most one
   `CliArg` metadata value, rejecting duplicates and ignoring unrelated
   metadata. Remove the obsolete `cliarg` implementation that calls
   `dataclasses.field`, and retain `CliArg` as the public type declaration.
2. Define `CliArg(help="", short=None, env=None, pos=False, opt=True,
   secret=False)`. `short` is a string or `None`; do not normalize it into a
   collection. Do not add a
   convenience `cliarg()` factory: it performs no extra work and obscures that
   this value is annotation metadata.
3. In `msup/base.py`, replace the dataclass-only assumptions around
   `InitArg`, `has_default_value`, and `fields_or_init_kwargs` with one common
   internal field record containing name, unwrapped annotation, default, and
   whether a default factory exists. Keep it CLI-agnostic and internal unless
   callers require it.
4. Read annotations with `get_type_hints(..., include_extras=True)`. Base
   conversion strips generic `Annotated` wrappers; CLI construction reads the
   original annotations and interprets only `CliArg` metadata.
5. For dataclasses, combine the unwrapped annotation with `Field.default` and
   `Field.default_factory`. Do not read CLI metadata from
   `Field.metadata` after this migration.
6. For regular classes, retain constructor-signature discovery and variadic
   constructor omission. Unwrap `Annotated` constructor annotations, but give
   them no CLI-specific behavior in serialization.

### Code pointers

- `msup/cli.py:22-58` exposes the public metadata type and implements the
  current dataclass-only
  `cliarg` API that this refactor removes.
- `msup/base.py:18-75` defines `InitArg`, default detection, and constructor
  field discovery.
- `msup/base.py:315-343` consumes field discovery during serialization and
  deserialization.

### Tests

- Add focused unit tests proving `Annotated` base annotations still use the
  existing scalar, optional, list, tuple, dictionary, callable, and nested
  conversion rules.
- Add errors for duplicate `CliArg` metadata on one annotation.
- Update every existing test fixture using `cliarg(default=...)` or
  `cliarg(default_factory=...)` to use `CliArg(...)` plus an ordinary default or
  `dataclasses.field(default_factory=...)`.

### Success criteria

- Every in-repository dataclass CLI fixture uses `Annotated[..., CliArg(...)]`.
- `CliArg` never becomes a dataclass field default or a value passed to a
  command handler.
- Existing regular-class serialization behavior remains covered and unchanged.

### Implementation progress

- Complete: defined immutable `CliArg` and its metadata unwrapping in
  `msup.cli`; `short` is a string or `None` and `None` means no short option.
- Complete: removed `cliarg(...)`, migrated the in-repository test fixtures,
  and retained the public `CliArg` declaration in `msup.cli`.
- Complete: made `msup.base` CLI-agnostic. Its shared field record contains
  only serialization information, and it strips generic `Annotated` wrappers
  without importing or inspecting `CliArg`.
- Complete: covered duplicate and unrelated annotation metadata, immutable
  `CliArg`, generic conversion, and annotated regular constructors.

## Phase 2: Add optional Pydantic v2 model serialization

**Status:** complete

### Implementation

1. Add Pydantic v2 detection in `msup/base.py` using a local `try`/`except
   ImportError` import only when a candidate class or instance is examined.
   Absence of Pydantic must leave module imports and all dataclass/regular-
   class behavior working.
2. Extend common field discovery using
   `get_type_hints(Model, include_extras=True)` for the original `Annotated`
   annotation and `Model.model_fields[name]` for required/default/default-
   factory state. Do not rely solely on `FieldInfo.annotation` or
   `FieldInfo.metadata`, whose contents also represent Pydantic constraints.
   Do not support Pydantic v1, aliases, validators as CLI metadata, or
   `json_schema_extra` in this plan.
3. Define a shared `is_structured_model` check for dataclasses and Pydantic v2
   models, then use it in conversion compatibility, `from_dict_value`, and
   `to_dict_value`. A Pydantic model accepts an already-created model instance,
   a dictionary, or the existing JSON-object/path string input; construct it
   with `Model(**values)` so Pydantic performs its own validation.
4. Update `to_dict`, `to_kwargs`, and `from_dict` to obtain unwrapped field
   annotations from common discovery. Serialize Pydantic fields through the
   existing recursive conversion rules, not `model_dump`, so callable handling
   and this library's JSON format stay consistent.
5. Refresh `uv.lock` after Phase 0 adds the published Pydantic extra. Do not
   add Pydantic to `[project.dependencies]` or duplicate it in the `dev`
   dependency group.

### Code pointers

- `msup/base.py:58-75` is the current discovery hook to extend.
- `msup/base.py:151-286` contains compatibility and value conversion logic.
- `msup/base.py:315-343` implements the public dictionary conversion path.
- `pyproject.toml:14-20` owns published optional dependencies and development
  dependencies.

### Tests

- Add a Pydantic v2 model with scalar, optional, collection, nested-model, and
  `Field(default_factory=...)` fields.
- Verify `from_dict`, `to_dict`, `from_json`, and `to_json` round trip the
  model, preserve defaults when keys are omitted, and surface Pydantic
  validation errors for invalid model data.
- Verify Pydantic remains optional by exercising dataclass conversion without
  importing Pydantic from module import paths; do not simulate an unavailable
  installed package by mutating `sys.modules`.

### Success criteria

- Pydantic v2 models round trip through all public serialization helpers.
- Installing `msup` without Pydantic remains valid and does not import it.
- Pydantic v1 classes produce an explicit unsupported-class error rather than
  being mistaken for regular `__init__(**data)` classes.

### Implementation progress

- Complete: added local, guarded Pydantic v2 detection in `msup.base`; module
  imports remain Pydantic-free and Pydantic v1 compatibility classes raise an
  explicit unsupported-model error.
- Complete: integrated Pydantic `model_fields` into generic field discovery,
  preserving `Annotated` base annotations and default/default-factory state.
- Complete: serialization uses the existing recursive conversion logic for
  dataclasses and Pydantic models, including nested model instances, objects,
  JSON strings, and JSON paths. Missing Pydantic inputs remain omitted so the
  model controls defaults.
- Complete: added mandatory Pydantic v2 serialization tests for public
  dictionary, JSON, and constructor-keyword helpers.

## Phase 3: Generalize structured CLI argument models

**Status:** complete

### Implementation

1. Refactor `_add_args` and `_from_cli_args` in `msup/cli.py` to consume the
   shared field records and `is_structured_model`, rather than
   `dataclasses.fields`, `Field.metadata`, and `is_dataclass` directly.
2. Preserve all established dataclass command behavior: `--Args` and its type
   name alias, positional configuration when enabled, short options, optional
   booleans, collection/remainder handling, nested dotted options, help
   defaults, secrets, and CLI/environment/config/default precedence.
3. Apply the same behavior to Pydantic v2 command models. Nested Pydantic and
   dataclass fields are both structured fields and must accept config objects,
   JSON strings, JSON paths, environments, and dotted command-line overrides.
   When no source supplies a nested Pydantic value, omit it from the
   constructor input so Pydantic's `Field(default=...)` or `default_factory`
   remains authoritative. If that nested field is required, let Pydantic raise
   its validation error rather than constructing an empty nested model.
4. Keep aliases out of scope. CLI option names and config keys remain Python
   field names even when a Pydantic field declares an alias.
5. Keep unsupported annotations, including enums, rejected as they are today;
   this refactor does not add enum conversion.

### Code pointers

- `msup/cli.py:83-128` converts annotations into argparse argument types.
- `msup/cli.py:131-211` declares structured CLI options.
- `msup/cli.py:232-274` applies source precedence and constructs nested
  dataclass values.
- `tests/test_cli.py:286-445` captures existing parser and conversion
  contracts.

### Tests

- Port representative existing dataclass CLI metadata tests to `Annotated`.
- Add Pydantic model command tests for scalar/default options, help text,
  environment/config/CLI precedence, JSON and dotted nested overrides, and
  nested default factories. Cover an omitted nested default, an omitted nested
  default factory, and an omitted required nested model separately.
- Retain rejection tests for invalid short options, non-final positional
  collections, unsupported unions, fixed tuples, and enums for both model
  kinds where applicable.

### Success criteria

- A Pydantic v2 model can be the sole structured argument to `cli()` and has
  the same observable parser semantics as the equivalent dataclass.
- No dataclass-only field or metadata access remains in the structured CLI
  build and construct paths.

### Implementation progress

- Complete: structured command discovery, parser construction, and value
  construction use common field records and `is_structured_model`.
- Complete: Pydantic models support CLI metadata, scalar options, help,
  environment/config/CLI precedence, JSON nested values, and dotted overrides.
- Complete: absent nested Pydantic values are omitted so model defaults and
  default factories apply, while required nested values surface Pydantic's
  validation error.

## Phase 4: Support direct named function parameters

**Status:** pending

### Implementation

1. Replace `_get_first_arg` with command-signature discovery that identifies
   one of two modes:
   - A single structured parameter retains the existing model-command mode.
   - One or more named typed parameters use direct-parameter mode.
2. Reject missing annotations, positional-only parameters, `*args`, and
   `**kwargs` before parser construction. Require keyword-capable,
   non-variadic parameters so parsed values can always be invoked as
   `func(**kwargs)`.
3. Reuse `_add_argument`, annotation conversion, `CliArg` metadata, default
   discovery, and source-precedence conversion for direct parameters. Required
   parameters have no Python default and are not optional; optional parameters
   use their ordinary Python default. `CliArg` configures names, help,
   environments, positional behavior, and secrecy only.
4. Add direct-parameter `--Args` configuration support using a JSON object or
   `.json` path keyed by parameter name. Honor `pos_arg_config` consistently.
   Direct nested dataclass/Pydantic parameters accept a JSON object/path value
   but do not generate dotted child options in this phase.
5. For a subcommand mapping, store the selected command's invocation mode and
   signature descriptor in parser defaults, then invoke either the structured
   object or direct keyword arguments after parsing.

### Code pointers

- `msup/cli.py:69-81` currently requires a dataclass first argument.
- `msup/cli.py:276-305` selects command parsers and invokes handlers.
- `tests/test_cli.py:420-425` currently asserts the behavior this phase
  intentionally replaces.

### Tests

- Add a direct handler such as
  `def command(a: int, b: Annotated[float, CliArg(help="abc")] = 1.5)` and
  assert values, defaults, help text, `--Args`, environment, and CLI
  precedence.
- Cover direct string, int, float, bool, optional, collection, callable,
  dictionary, and nested structured parameter conversion that is already
  supported by `argument_type` and `from_dict_value`.
- Cover direct positional arguments and the final positional collection rule.
- Cover direct handlers inside a subcommand mapping.
- Assert clear errors for zero-parameter handlers, unannotated parameters,
  positional-only parameters, `*args`, and `**kwargs`.
- Replace the old invalid one-parameter-function test with direct-parameter
  coverage; keep an invalid-handler test for the new rejected signatures.

### Success criteria

- `cli()` invokes a direct multi-parameter handler once with correctly typed
  keyword arguments and never passes `CliArg` metadata to user code.
- Direct handlers and structured-model handlers share conversion semantics and
  precedence where their input shapes overlap.
- Unsupported signature forms fail before argparse parses user input.

## Phase 5: Migrate documentation and validate the public contract

**Status:** pending

### Implementation

1. Update `README.md` to describe dataclasses, optional Pydantic v2 models,
   and direct function handlers as supported CLI inputs. Replace all legacy
   `cliarg(default=...)` and `cliarg(default_factory=...)` examples with
   `Annotated[..., CliArg(...)]` plus normal defaults or framework factories.
2. Add concise examples for a mutable list default in a dataclass and a
   Pydantic model, and for a direct two-parameter function. State explicitly
   that Pydantic is optional and that enum support remains a TODO.
3. Update the embedded `ExampleArgs` code in `msup/cli.py` so executing the
   module demonstrates the supported API.
4. Run formatting and the complete validation suite after all test and
   documentation changes. Inspect the final coverage report and add targeted
   tests for any newly introduced behavior branches.

### Code pointers

- `README.md:1-130` contains feature claims and all current `cliarg` examples.
- `msup/cli.py:315-331` is an embedded runnable example.
- `justfile:9-13` defines the repository test and coverage commands.

### Validation

```text
just test
just coverage
uv run --group dev ruff check .
uv run --group dev ruff format --check .
uv run --group dev ty check .
uv run --no-default-groups --no-extra python -c 'import msup.base; import msup.cli'
```

### Success criteria

- Documentation examples use only the new API and execute when copied into
  their documented dependency environment.
- `just coverage` passes with all Pydantic integration and direct-function
  tests enabled.
- The final coverage report has no untested new public error or invocation
  path.

## Alternatives considered

- Keep `cliarg` returning `dataclasses.Field`: rejected because it is only
  meaningful during dataclass creation, cannot describe Pydantic fields or
  function parameters, and conflates CLI metadata with defaults.
- Use a class or function decorator sidecar mapping: viable, but it separates
  metadata from the declared type, makes field renames easier to miss, and adds
  an additional public mapping API. `Annotated` keeps metadata next to the
  parameter it controls.
- Store metadata in `dataclasses.field(metadata=...)` and
  `pydantic.Field(json_schema_extra=...)`: rejected because it requires
  framework-specific syntax and puts CLI details into Pydantic JSON schema
  output.
- Add Pydantic as a required dependency: rejected because it conflicts with
  the package's no-dependencies-by-default design.
- Put Pydantic only in the root development group: rejected because consumers
  would have no declared installation path for a supported integration.
- Put PyTorch in a root extra or dependency group: rejected because its
  platform-specific heavyweight distributions would affect the root resolver,
  lockfile, and contributor environment for an example-only feature.
- Treat `*args` and `**kwargs` as CLI collections or arbitrary options:
  rejected because argparse cannot determine stable names, help text,
  precedence, or type contracts for them.

## Overall success criteria

- `Annotated[T, CliArg(...)]` is the sole documented and tested CLI metadata
  syntax for dataclasses, Pydantic v2 models, and direct functions.
- Pydantic v2 is optional in production and fully covered in development.
- `cli()` supports both existing one-structured-argument handlers and direct
  handlers with multiple named typed parameters.
- Existing supported dataclass serialization and CLI behavior remains intact
  except for the intentional removal of `cliarg` as a default-value factory.

## External references

- uv dependency fields: https://docs.astral.sh/uv/concepts/projects/dependencies/
- uv project configuration and resolution: https://docs.astral.sh/uv/concepts/projects/config/
