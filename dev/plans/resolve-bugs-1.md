# Resolve CLI annotation and argument-capture bugs

## Status

- [x] Phase 1: Audit the current CLI and serialization paths.
- [x] Phase 1a: Establish the public CLI type and source-precedence contract.
- [x] Phase 2: Define and implement normalized CLI annotation handling.
- [x] Phase 3: Make positional remainder capture and configuration merging reliable.
- [x] Phase 4: Add regression coverage and document the supported CLI contract.

## Context and decisions

## Execution status

Phase 1a regression tests now define the CLI contract before the Phase 2
normalization refactor. They use `unittest` because the repository has no
pytest dependency. The remaining Phase 1a coverage for `typing.Optional[T]`,
fixed-length tuples, and enums will be completed with schema validation in
Phase 4. The shared annotation normalization, parser construction, CLI
materialization, configuration precedence, explicit remainder capture,
regression coverage, and documentation are complete. All plan success criteria
are satisfied.

`msup` derives an `argparse` interface from dataclass fields. The current code
selects an argument action from the raw field annotation. Consequently,
`list[T] | None` is treated as an ordinary scalar rather than a list: it gets
no `nargs`, and its `type` is the parameterized `list[T]` object. This rejects
multiple values and produces incorrect element values for a single one.

The same raw-annotation dispatch is also responsible for broken optional
`bool`, `dict`, dataclass, and callable fields. Non-optional unions cannot be
used as an `argparse` converter, bare/untyped collections have no defined
conversion behavior, tuples have no sequence action, and collection conversion
in `msup/base.py` discards the declared element types.

Remaining positional capture is already expressible, but is neither documented
nor tested:

```python
@dataclass
class CommandArgs:
    extra: list[str] = cliarg(pos=True, opt=False, default_factory=list)
```

This must remain an explicit opt-in. Automatically treating every `list[T]`
field as a positional remainder would make existing list options ambiguous and
would silently change the CLI schema. A remainder list is final among
positionals, following `argparse`'s `nargs="*"` rule; options may still appear
before it.

Recommended approach: add a small shared annotation-normalization layer and
make parser construction and value materialization use it. This is preferable
to adding independent special cases for each optional wrapper because the same
effective type is needed in at least the parser, CLI materializer, and base
deserializer. Define a deliberate CLI type contract: primitives, `Any`, typed
and untyped `list`/variable-length `tuple`, dictionaries encoded as JSON or a
JSON file, dataclasses, callables, and an optional wrapper around any of those.
Reject non-optional unions and unsupported annotations at parser construction
with a useful `TypeError`. A command-line string cannot select safely between
ambiguous alternatives such as `int | str`; silently picking a union member
would be a fragile policy. Preserve base serialization's documented
non-ambiguous union support separately, fixing its existing implementation
errors.

## Audit findings and code pointers

- `msup/cli.py:116-125` unwraps optionals only to choose an `argparse` type,
  while `msup/cli.py:183-240` still dispatches on the original field type.
  `list[str] | None` therefore misses the list action at
  `msup/cli.py:197-205`.
- The same mismatch bypasses the bool, dict, dataclass, and callable actions at
  `msup/cli.py:183-240`. For example, `bool | None` invokes Python's
  `bool("false")`, which is true.
- `msup/base.py:110-123` has an unusable non-optional union branch: it refers
  to undefined names. `msup/base.py:193-197` recursively converts collection
  elements using their runtime types instead of their declared annotations.
- Parser registration for `--Args` and the optional positional config is at
  `msup/cli.py:132-147`, but `msup/cli.py:41-114` never reads `args.args`.
  The README configuration examples at `README.md:102-106` therefore cannot
  work as documented.
- Nested dataclass recursion resets rather than accumulates its prefix at
  `msup/cli.py:190-195` and `msup/cli.py:73`; direct nested overrides also
  calculate a converted value but assign the raw value at `msup/cli.py:61-71`.
- `msup/cli.py:29-39` already uses resolved function hints, but dataclass
  field processing reads `Field.type` directly. Future annotations therefore
  reach `argparse` as strings. The invalid-argument diagnostic there also
  references undefined names.
- `tests/test_basic.py:1-34` covers only a few serialization assertions under
  a `__main__` guard. There is no automated CLI coverage.

## Phase 1: Establish the public CLI type and source-precedence contract

1. Add focused executable regression tests in `tests/test_cli.py` before
   changing behavior. Exercise the public `cli()` entry point with controlled
   `sys.argv` and handlers that retain their materialized dataclass. Use
   subprocess-style tests only for expected `argparse` exits and stderr.
2. Record the supported annotation matrix in test names and later in the
   README: direct and optional primitives, `list[T]`, `tuple[T, ...]`, `dict`,
   dataclasses, `Callable`, `Any`, and the explicit positional-remainder list.
   Cover `typing.Optional[T]`, `T | None`, and `None | T` so optional handling
   cannot depend on union member order.
3. Specify and test precedence at the public boundary: explicit CLI values
   override environment values, environment values override a supplied
   `--Args`/positional config mapping, and that mapping overrides dataclass
   defaults/default factories. Treat a present `--items` with no values as an
   explicit empty list, not as omission.
4. Add negative tests asserting schema-time errors for ambiguous non-optional
   unions, fixed-length tuples if they are not implemented in this change, enums,
   and other annotations outside the published contract. The error must identify
   the dataclass field and annotation.

Success criteria: the project has an executable specification for the supported
types, reversed optional order, input-source precedence, and unsupported-type
diagnostics; current failures are reproduced without relying on ad hoc scripts.

## Phase 2: Normalize annotations and convert values from their declared type

1. In `msup/base.py`, introduce small type-inspection functions used by both
   modules: resolve dataclass hints with `get_type_hints`, identify a two-member
   `None` union regardless of order, expose its non-None annotation, and retrieve
   a collection's declared item/key/value type with sensible `Any` defaults for
   bare collections. Keep these functions narrowly focused rather than creating a
   parser framework.
2. Repair `_is_compat()` and `_from_value()` in `msup/base.py:101-203` so they
   select exactly one compatible non-optional union member or report ambiguity
   using real local values, preserve `None`, and recurse into list/tuple values
   using their declared item annotation. Do the same for dictionary keys and
   values. Repair `_to_dict_value()`'s inverted union-match check at
   `msup/base.py:69-78` and add base-level tests for these conversion paths.
3. Refactor `_get_cli_arg_type()` and `_add_args()` in `msup/cli.py:116-240` to
   work from the normalized effective annotation. Register lists and supported
   variable tuples with the appropriate `nargs` and item converter, dictionaries
   as strings for JSON/file decoding, dataclasses and callables as strings,
   booleans with `to_bool`, and `Any` as strings. Do not pass parameterized
   typing objects or union objects directly to `argparse`.
4. Use resolved dataclass field hints throughout `_add_args()` and
   `_from_cli_args()`, including nested dataclasses. Reject unsupported CLI
   annotations before adding parser actions, with a clear field-qualified error.
   Fix `_get_first_arg()` and assertion diagnostics to report the real
   callable/type rather than undefined identifiers.

Success criteria: `list[int] | None` accepts zero or many values, produces
`list[int]`, and is `None` when omitted; optional bool/dict/dataclass/callable
use their specialized behavior; bare collections and `Any` are predictable;
and unsupported unions fail clearly before parsing.

## Phase 3: Materialize configuration, nested fields, and remainders correctly

1. Refactor `_from_cli_args()` in `msup/cli.py:41-114` to begin from a supplied
   root configuration mapping when `args.args` is present. Decode it using the
   same dataclass conversion path as nested config objects, then apply only
   explicitly supplied environment and CLI fields according to the Phase 1
   precedence contract. Configure parser defaults so omitted options can be
   distinguished from explicit values without losing dataclass defaults.
2. Apply CLI overrides through the shared typed conversion routine, including
   false, zero, empty strings, and empty lists. Eliminate the current truthiness
   test and raw assignment in nested overrides (`msup/cli.py:61-71`).
3. Carry the complete dotted field path through both parser registration and
   materialization recursion. Replace uses of `f.name` as a recursive prefix
   with the accumulated `name`, then test three nesting levels, full nested
   config input, and a leaf override.
4. Retain `cliarg(pos=True, opt=False, default_factory=list)` as the API for
   positional remainder capture. Ensure it receives the normalized list item
   converter, supports `list[int]` as well as `list[str]`, resolves to the
   default factory when absent, and behaves correctly beside ordinary optional
   flags. Document that it must be the last positional field.

Success criteria: both documented config input forms actually populate required
and optional fields; source precedence is deterministic; deep dotted overrides
are typed; and final positional `extra: list[str]` captures all remaining
positional tokens without changing ordinary list options.

## Phase 4: Complete regression coverage and documentation

1. Expand `tests/test_cli.py` into a compact matrix covering single-command and
   subcommand operation, list and optional-list parsing, optional scalar and
   structured types, positional remainder capture, environment/config/CLI
   precedence, nested paths, and error diagnostics. Move the existing
   serialization checks in `tests/test_basic.py` out of their `__main__` guard
   so the standard test runner executes them.
2. Update `README.md` after the behavior is implemented. Add a CLI annotation
   table, the explicit remainder-capture example, rules for list option values
   and final positionals, the configuration precedence order, and an explicit
   note that ambiguous non-optional CLI unions are rejected.
3. Run the full test suite and the documented `examples/cli/simple.py` and
   `examples/cli/multicli.py` commands, including configuration and nested
   override examples. Run the configured formatter/linter if available, and
   correct any violations introduced by the refactor.

Success criteria: all automated tests run under the repository's normal test
command, README examples match observed behavior, and the supported CLI type
contract has regression tests for every branch.
