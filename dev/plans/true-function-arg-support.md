# True function-argument support

## Goal

Make a function's annotated parameters a first-class shared field shape. The
same metadata should drive direct CLI commands and serialization of a
function's `locals()` mapping:

```python
def greet(name: str, times: int = 1):
    print(to_json(locals(), type_class=greet))
```

The JSON contains only `name` and `times`, serialized using their annotations.
It excludes helper variables from `locals()`.

## Implementation status

**Complete:** 5/5 phases complete.

## Recommended approach and decisions

- Extend `fields_or_init_kwargs` in `msup/base.py` to accept classes,
  functions, and methods. For a function or method, inspect it rather than its
  `__init__` and return generic `FieldSpec` records.
- Rename the internal `InitArg` record to `FieldSpec`. Its fields describe a
  typed named value across dataclass fields, constructors, Pydantic fields,
  and function parameters, so the constructor-specific name is no longer
  accurate. Do not keep a compatibility alias.
- Refactor `msup.cli.command_args` to use that shared discovery for direct
  parameters. Keep all CLI-specific signature validation in `msup.cli`.
- Add an optional `type_class` argument to `to_dict` and `to_json`. Keep it a
  trailing keyword on `to_json`, after the existing `file_like` and `indent`
  parameters, so calls such as `to_json(value, path)` retain their meaning.
  This makes `to_json(locals(), type_class=greet)` concise and unambiguous.
- Serialize only parameters that occur in the mapping. This filters unrelated
  locals and matches `to_kwargs` behavior for partial values.
- Reuse `to_dict_value` with each parameter annotation. Direct function
  arguments then serialize with the same scalar, nested, collection, optional,
  and callable rules as dataclass fields.
- Keep the base layer independent from `CliArg` and `msup.cli`.
- Support functions and bound or unbound methods in this change. Do not extend
  the contract to arbitrary callable instances until `__call__` metadata has a
  concrete consumer and test coverage.
- Defer deleting `command_args` until Phase 5. That cleanup will preserve the
  CLI contract while reducing `msup` source lines below its 924-line baseline.

### Alternatives considered

1. Recommended: extend `fields_or_init_kwargs` for functions and methods, then
   reuse it from CLI parsing and serialization. This provides one source of names,
   unwrapped annotations, `Annotated` metadata, and defaults.
2. Rejected: inspect function signatures independently in `command_args` and
   `to_json`. That duplicates conversion metadata and future bug fixes.
3. Rejected: construct temporary dataclasses from function signatures. Dynamic
   type creation adds complexity without behavior that `FieldSpec` lacks.

## Dependency graph

```text
Phase 1: shared callable field discovery
    -> Phase 2: direct CLI refactor
    -> Phase 3: function-argument serialization
    -> Phase 4: examples, README, and validation
    -> Phase 5: direct CLI cleanup and LOC reduction
```

## Phase 1: Extend shared field discovery for callables

**Status:** complete

### Implementation

1. Update `fields_or_init_kwargs` to accept a class, function, or method.
   Preserve the existing dataclass, Pydantic, and ordinary-class paths.
2. Rename `InitArg` to `FieldSpec` throughout `msup.base` and `msup.cli`. It
   remains an internal record with `name`, annotation metadata, and default
   information. Do not leave an `InitArg` alias behind.
3. For a function or method, use `inspect.signature(target)` and
   `get_type_hints(target, include_extras=True)`. Build `FieldSpec` records with
   the same `Annotated` unwrapping and `MISSING` default representation used
   for constructors.
4. Preserve current class-constructor behavior: skip `self` and `cls`, and
   ignore variadic constructor parameters. Do not enforce CLI handler
   restrictions in this base-level helper.
5. Add focused tests for a function with `Annotated` metadata, required and
   defaulted parameters, and a callable-valued parameter.

### Code pointers

- `msup/base.py:InitArg` is the constructor-centric record to rename to
  `FieldSpec`.
- `msup/base.py:unwrap_annotated` owns generic `Annotated` handling.
- `msup/base.py:fields_or_init_kwargs` currently supports structured models
  and class constructors only.

### Success criteria

- `fields_or_init_kwargs(function)` returns the expected `FieldSpec` records.
- Dataclass, Pydantic, and regular-class discovery behavior remains unchanged.
- `msup.base` has no dependency on `CliArg` or `msup.cli`.
- No source or test references the retired `InitArg` name.

### Implementation notes

- Completed with no changes to the planned callable contract. Function, bound
  method, and unbound method discovery are covered alongside existing class
  behavior.

## Phase 2: Refactor direct CLI commands onto shared discovery

**Status:** complete

### Implementation

1. Retain the handler validation at the start of `command_args`: reject
   no-argument, unannotated, positional-only, `*args`, and `**kwargs` command
   handlers with the existing error behavior.
2. After validation, replace the manual `FieldSpec` construction in
   `command_args` with `fields_or_init_kwargs(func)`. Filter those shared
   records to the validated parameter names, retaining the current behavior
   that direct handlers named `self` or `cls` do not expose those names.
3. Use the shared records to distinguish a one-structured-argument command
   from a direct-parameter command. Retain current `CliArg` handling, help
   text, configuration precedence, positional support, and subcommands.
4. Do not move argparse errors or command restrictions into `msup.base`.

### Code pointers

- `msup/cli.py:command_args` currently duplicates callable signature and hint
  handling.
- `msup/cli.py:add_direct_args` consumes `FieldSpec` records for argparse.
- `msup/cli.py:from_direct_cli_args` applies config, environment, and command
  line values.
- `tests/test_cli.py:direct_command` and `CliContractTests` define the current
  direct-command contract.

### Success criteria

- Direct commands and direct subcommands preserve their current parsing,
  help, precedence, and error behavior.
- `command_args` performs validation and mode selection only. It does not
  construct a second, divergent `FieldSpec` list.

### Implementation notes

- Completed by validating handler signatures before filtering the shared
  callable records. The direct command tests cover reuse of the same records
  and exclusion of handler parameter names `self` and `cls`.

## Phase 3: Serialize function argument mappings

**Status:** complete

### Implementation

1. Add an optional `type_class` argument to `to_dict` and `to_json`, then
   update their top-of-module forward declarations in `msup/base.py`.
   `to_json` must pass it through to `to_dict`. Make it keyword-only on
   `to_json`, with the public shape
   `to_json(x, file_like=None, indent=2, *, type_class=None)`, to preserve its
   existing positional `file_like` and `indent` API. The matching dictionary
   form is `to_dict(x, type_class=None)`.
2. When `type_class` is provided, use `fields_or_init_kwargs(type_class)` to
   select fields rather than `type(x)`. If `x` is a mapping, read a field value
   by name; otherwise retain the existing attribute lookup. Serialize every
   selected value through `to_dict_value` and the field annotation.
3. Ignore mapping values that are not function parameters, including handler
   helpers and unrelated locals. Do not synthesize missing values from defaults
   because serialization should reflect supplied values.
4. `to_json(locals(), type_class=greet)` returns a JSON string. Existing path
   and stream output remain supported, including
   `to_json(value, file_like=path)`, and are not broadened in this phase.
5. Add focused tests for scalars, a nested dataclass, collections, importable
   callable values, `Annotated` metadata, and ignored locals. Assert both
   `to_dict(locals(), type_class=greet)` and
   `to_json(locals(), type_class=greet)`, plus `to_json` output through a
   `StringIO` and a JSON path with `type_class=greet`. Retain regression
   coverage for ordinary-object file and stream output.

### Code pointers

- `msup/base.py:to_json` owns JSON-string and file-output behavior.
- `msup/base.py:to_dict_value` owns type-directed value serialization.
- `msup/base.py:to_kwargs` already filters a mapping by known `FieldSpec`
  names.
- `tests/test_basic.py:BasicTests` covers object serialization and JSON output.

### Success criteria

- `to_json(locals(), type_class=greet)` serializes only `greet` parameters
  with their declared types.
- The typed serialization path accepts mappings as well as ordinary objects.
- Existing `to_json` object, path, and stream behavior remains unchanged.

### Implementation notes

- Completed with keyword-only `type_class` support on `to_json` and shared
  typed field selection in `to_dict`. Tests serialize actual function
  `locals()` values through string, stream, and path output.

## Phase 4: Add examples, rewrite the README, and validate

**Status:** complete

### Implementation

1. Create `examples/function_args.py` as an executable PEP 723 uv script. It
   must use normal typed parameters, call
   `print(to_json(locals(), type_class=greet))`, and register the handler with
   `cli(greet)`. Import `to_json` from `msup.base`, not through an incidental
   re-export from `msup.cli`.
2. Extend the `examples` recipe in `justfile` with the new script's help and a
   representative invocation. Retain `set -euxo pipefail` and temporary-file
   cleanup.
3. Restructure `README.md` top-down: introduce the library, then show a
   concise nested-dataclass example from `examples/nested.py`, the direct
   function-argument example, and a concise multi-command example from
   `examples/multicli.py`. Link each section to its full executable script and
   show `./examples/<file>.py` usage.
4. Move the existing README TODO backlog into `dev/TODO.md` without changing
   its items or nesting. Remove the TODO section from `README.md`; add only a
   brief link when it still improves contributor discoverability.
5. Redact configuration details that do not teach the core concept. Retain the
   dependency-free emphasis, brief feature list, and links to the PyTorch and
   Pydantic examples after the three primary demonstrations. Preserve the
   README's terse, opinionated writing style.

### Follow-up F4-002: Restore the terse example-led README

**Status:** complete

1. Restore the opening `# **M**icro **S**erialization **U**tilities for
   **P**ython` heading. Place the direct function-argument code example and
   project description under it.
2. Restore the original dependency-free introduction, LOC statement, design
   philosophy, and detailed feature list. Keep their meaning and level of
   detail while incorporating direct function arguments where useful.
3. Use exactly these top-level headings: the opening project title, `# Install`,
   `# Features`, `# Design Philosophy`, and bottom `# More Examples`. Remove
   root-directory prose and collect links to the complete executable examples
   in the bottom section.
4. Keep the new direct-function example accurate and do not disturb the TODO
   migration or executable example integration.

### Follow-up F4-003: Expand examples and feature coverage

**Status:** complete

1. Replace the More Examples reference-only list with concise, accurate code
   snippets for the additional command forms, followed by links to their full
   executable sources.
2. Make the Features section exhaustive for the supported CLI, conversion,
   serialization, annotation, configuration, and callable capabilities. Do
   not claim that regular classes are CLI models when they are only supported
   for construction and serialization.
3. Update the opening capability statement to include regular Python classes
   accurately.
4. Tighten all displayed examples so they do not use consecutive blank lines.

### Code pointers

- `examples/nested.py` is the nested-dataclass command.
- `examples/multicli.py` is the advanced multi-command example.
- `justfile:examples` is the executable-example integration recipe.
- `README.md` is the primary top-down onboarding document.
- `dev/TODO.md` is the destination for the contributor backlog.

### Success criteria

- The README introduces the three command forms in increasing complexity
  without a long unstructured source dump.
- The TODO backlog exists only in `dev/TODO.md`, with its current content and
  nesting preserved.
- Each documented primary example is executable from the repository root.
- `just examples` exercises every primary example and stops at the first
  failure.

### Follow-up success criteria

- The README uses the requested project-title, Install, Features, Design
  Philosophy, and More Examples headings. The direct-function example follows
  the opening project title.
- The dependency-free introduction, LOC statement, design philosophy, and
  detailed feature list are present.
- References to the executable examples occur only in the bottom reference
  list, without root-directory prose.

### Follow-up F4-003 success criteria

- More Examples contains compact code snippets and links to their full
  executable sources.
- Features describes all supported capabilities without claiming unsupported
  behavior.
- The opening capability statement includes regular Python classes accurately.
- Displayed code examples have no consecutive blank lines.

### Implementation notes

- The executable example, recipe coverage, and TODO migration are complete.
  Follow-up F4-002 restored the requested heading structure. Follow-up F4-003
  added compact code snippets and a complete, implementation-checked feature
  inventory.

## Phase 5: Reduce direct CLI setup LOC (Follow-up F4-001)

**Status:** complete

### Implementation

1. Delete `msup.cli.command_args` and its tests. Keep CLI-specific signature
   validation in `cli`, but use `fields_or_init_kwargs` directly for command
   field discovery and structured-command selection.
2. Consolidate the single-command and subcommand setup paths in `cli` where
   that reduces duplication without changing direct or structured command
   behavior.
3. Preserve command validation, parsing, help, configuration precedence,
   positional support, and subcommands. Do not move `CliArg` or CLI errors
   into `msup.base`.
4. Reduce the total source line count reported by `wc -l msup/*.py` below the
   924-line baseline recorded before this follow-up.

### Code pointers

- `msup/cli.py:command_args` is the one-use wrapper to remove.
- `msup/cli.py:cli` owns command setup and dispatch.
- `msup/base.py:fields_or_init_kwargs` owns shared callable field discovery.
- `tests/test_cli.py:CliContractTests` defines the direct-command contract.

### Success criteria

- `command_args` no longer exists and direct CLI setup uses shared field
  discovery from `msup.base`.
- Direct and structured command parsing, help, precedence, positional
  support, validation, and subcommands remain covered and unchanged.
- `wc -l msup/*.py` reports fewer than 924 total lines.

### Implementation notes

- Removed `command_args` and performed handler validation, shared callable
  discovery, structured-command selection, setup, and dispatch directly in
  `cli`.
- Single commands and subcommands share setup and dispatch. Opaque parser
  metadata uses a per-call identity marker and a destination that cannot
  collide with direct or root structured fields.
- `command_type` uses explicit `is not None` checks, preserving structured
  commands whose class has falsey truthiness.
- Final validation passed: `just test` (68 passed), `just examples`,
  `git diff --check`, and `wc -l msup/*.py` (921 total).

## Final validation

Run after Phase 5:

```bash
just test
just examples
git diff --check
wc -l msup/*.py
```

All commands must pass. The direct function example must print valid JSON for
its arguments, and the README must not document an unsupported invocation.
