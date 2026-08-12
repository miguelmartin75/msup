# kwargs_for follow-ups

## Status

- Phase 1: Complete
- Phase 2: Complete
- Phase 3: Complete
- Phase 4: Not started
- Phase 5: Not started
- Phase 6: Not started

Update each phase to `In progress`, `Complete`, or `Blocked` while executing it.
Record the exact validation command and result beneath every completed phase.

## Goal

Keep the completed `kwargs_for` feature and reduce its implementation to the
smallest clear design. Relation reflection remains a base concern for
dataclasses, Pydantic v2 models, classes, functions, and methods. Conversion,
serialization, and CLI parsing must continue to use the selected target's
signature without constructing or calling that target.

The recommended approach is to restore unrelated code to the `abca9b07`
baseline shape, keep one focused second reflection pass for relation fields,
and add relation-specific behavior directly at the existing conversion and CLI
decision points. Do not replace ordinary CLI parsing with a generic source
tree, materialization state, or parallel dynamic-owner framework.

After every correctness-review cycle, inspect the production LOC delta and
apply accepted behavior-preserving simplifications before completing the
phase. The final combined LOC of `msup/base.py` and `msup/cli.py` must be lower
than the 1,443-line pre-follow-up state at commit `4e89338`.

## User design constraints

Retain these comments as explicit acceptance constraints:

- "You've lost the plot if you think this is acceptable. `from_kwargs` has a
  lot of unnecessary complexity."
- "why is `to_dict` not as simple as it was before, but slightly modified?"
- Use `inspect.signature` through selected-target reflection only after the
  runtime selector value is known, and inspect each selected callable once.
- Apply the baseline field-loop plus the smallest relation-specific branch to
  `to_dict`, `from_kwargs`, and analogous consumers.
- `validation_value`, `validation_paths`, and `set_validation_value` are design
  red flags. Remove them rather than moving Pydantic alias traversal into
  `FieldSpec`; native alias handling must stay narrowly scoped to active
  relation fields.
- Production LOC reduction must come from simpler algorithms and deleted
  state, not compressed forward declarations, deleted useful docstrings, or
  formatting changes.

## Code map

- `msup/base.py:13-37` exposes the base public API and shared annotations.
- `msup/base.py:50-225` defines metadata, field reflection, and the static
  `FieldSpec.kwargs_relation` link.
- `msup/base.py:257-325` contains annotation, collection, union, and enum
  helpers that should retain the baseline control-flow shapes.
- `msup/base.py:442-730` converts values and implements dictionary conversion,
  serialization, and owner construction.
- `msup/cli.py:1-160` defines CLI metadata, argument conversion, and recursive
  option registration.
- `msup/cli.py:284-676` merges config, environment, and CLI input, runs the
  relation bootstrap/second parse, and constructs command arguments.
- `tests/test_basic.py` covers reflection, conversion, dict/JSON round trips,
  selected signatures, and non-invocation behavior.
- `tests/test_cli.py` covers parser shape, source precedence, help,
  subcommands, relation options, and factories.
- `tests/test_pydantic.py` covers Pydantic v2 aliases, defaults, and relation
  serialization/construction.
- `dev/plans/kwargs-for.md` is the feature contract to preserve.

## Invariants

- A dependent field is `Annotated[Kwargs, Metadata(kwargs_for="selector")]`
  or the equivalent `dict[str, Any]` annotation. Its selector is declared
  earlier and is annotated as `Callable`.
- `fields_or_init_kwargs` does one normal reflection pass followed by one
  relation-link pass. The latter only examines relation fields and records a
  link to an already-reflected selector.
- Default values and factories remain lazy. An overridden selector factory is
  not evaluated; a required mapping factory is evaluated at most once.
- Input precedence remains config, then environment, then explicit CLI, with
  nested mappings merged at the existing layer boundaries.
- Pydantic v2 validation aliases retain their native behavior. Relation code
  adds no blanket string-only alias restriction.
- `kwargs_for` supports `--Args`, nested models, direct functions,
  subcommands, help output, and selected-target dotted options. It never
  invokes the selected callable while parsing, converting, or serializing.

## Phase 1: Simplify base reflection and restore unrelated helpers

**Status:** Complete

1. In `msup/base.py:fields_or_init_kwargs`, retain the completed first pass
   that builds all `FieldSpec` values. Replace `indexed_fields`,
   `linked_selectors`, and selector-metadata rechecks with a direct second
   pass using the already-seen `prior_fields` mapping.
2. For each field, read its relation metadata. If it is a relation field,
   normalize and validate only its dependent annotation, look up
   `metadata.kwargs_for` in `prior_fields`, validate that field has `Callable`
   origin, and assign it to `field.kwargs_relation`. Add the current field to
   `prior_fields` after processing it. Lookup before insertion rejects missing,
   self, and later selectors through one error path. Do not add separate self,
   order, selector-metadata, duplicate-selector, or Pydantic alias-type checks.
3. Allow multiple dependent fields to reference the same preceding selector.
   Consumers must process each dependent field through its own
   `kwargs_relation` and must not assume an inverse selector-to-single-dependent
   relation. Remove the owner-wide Pydantic validation-alias pass entirely.
   Preserve input keys and let native Pydantic `model_validate` apply
   `AliasPath`, `AliasChoices`, and string alias semantics.
4. Restore the exact `abca9b07` control-flow bodies of `maybe_idx`,
   `get_optional_type`, `get_collection_args`, `annotation_origin`,
   `effective_type`, `union_member`, and `validate_enum_values`. Restore the
   relation-free branches of `from_dict_value` and the ordinary CLI helpers.
   Use `normalize_annotation` only at relation-specific `Kwargs`
   inspection/conversion sites and selected-signature checks that require
   `TypeAliasType` unwrapping. Preserve only named feature-required deviations:
   relation metadata/linking, lazy Pydantic factory extraction, canonical
   callable loading/dumping, selected-target reflection, relation
   conversion/serialization, the second CLI parse, and shared `str_to_bool`.
5. Move `str_to_bool` to `msup/base.py` as a public shared conversion helper and
   add it to the module's forward declarations.
   Make its error and accepted spellings suitable for both dictionary and CLI
   conversion, and import it from `msup.cli`.

**Success criteria:** reflection is plainly a two-pass operation, relation
links are correct for every supported owner kind, and unrelated helper diffs
from `abca9b07` are removed without changing their baseline behavior.

**Validation:** `uv run --group dev --extra pydantic pytest tests/test_basic.py
-k 'not kwargs_relation_schemas_reject_invalid_links'` passed with 25 tests
and 1 deselected; `uv run --group dev --extra pydantic ty check msup`,
`./run.py lint_check`, and `./run.py format_check` passed. `./run.py check`
reached the known Phase 5 test import of `msup.cli.strtobool` and stopped with
one type diagnostic because that test has not yet moved to public
`msup.base.str_to_bool`.

## Phase 2: Inline base relation conversion and serialization

**Status:** Complete

1. Delete `_kwargs_from_fields`. Inline selected-parameter unknown-key,
   required-key, and conversion logic into `kwargs_from_dict`, into
   `from_kwargs` where parameters have already been reflected, and into the
   CLI relation-finalization branch. Do not add `kwargs_from_fields` unless
   execution reveals a fourth real same-meaning production use. Remove all
   private base imports from `msup.cli`.
2. Remove `_to_dict` and fold its relation-aware traversal into `to_dict`.
   Keep a small value-level conversion only if it is reused at least four
   times; otherwise keep recursion directly readable in `to_dict` and
   `to_dict_value`. Serialize a dependent kwargs mapping using the selected
   target parameter annotations and reject a kwargs mapping whose selector is
   unavailable.
3. Remove `_from_kwargs` and `_construct_owner`. Inline declaration-order
   owner conversion into `from_kwargs` and make `from_dict` call that public
   operation only for relation-owning owners. Construct dataclasses directly
   from converted arguments. For Pydantic owners, resolve each selector and
   dependent relation value from the same winning input location Pydantic uses
   for its `validation_alias`, including string aliases, `AliasPath`, and
   ordered `AliasChoices`. Write the converted value back to that winning
   location, or to the field's accepted primary validation location when
   applying a default. Preserve unrelated input keys, never leave a conflicting
   unconverted alias value beside a canonical-name overlay, and call native
   `model_validate` exactly once.
4. Keep relation-free `from_dict` and `from_dict_value` on their prior direct
   paths. For nested relation-owning structured values, recurse through the
   public owner conversion at the existing structured-model branch rather than
   introducing a construction wrapper.
5. Keep errors at real boundaries: mapping type validation, selected target
   signature validation, missing selector, unknown target kwarg, and missing
   required target parameter. Remove defensive wrapping/checks that merely
   repeat a prior pass or obscure the source error.

**Success criteria:** no `_to_dict`, `_from_kwargs`, or `_construct_owner`
remains; no module imports private base helpers; round trips retain typed
kwargs and selected targets remain uncalled.

**Validation:** `uv run --group dev --extra pydantic pytest
tests/test_basic.py -k 'not kwargs_relation_schemas_reject_invalid_links'`
passed with 25 tests and 1 deselected; `uv run --group dev --extra pydantic
pytest tests/test_pydantic.py -k 'not
pydantic_relation_owners_use_native_validation_and_string_aliases'` passed
with 17 tests and 1 deselected; `uv run --group dev --extra pydantic ty check
msup`, `./run.py lint_check`, `./run.py format_check`, and `git diff --check`
passed. Focused probes passed for string and sequence `AliasPath` fallback,
ordered `AliasChoices`, copy-on-write sibling preservation, nested diagnostic
paths, optional structured `None`, multiple dependents, and target
non-invocation. The post-review simplification pass removed 19 production
lines; combined production LOC is 1,547, with the remaining reduction owned by
Phase 3's CLI pipeline removal.

## Phase 3: Restore the ordinary CLI flow and isolate relation parsing

**Status:** Complete

1. Remove `_RAW_MATERIALIZED`, `_is_dynamic_owner`, `_field_sources`,
   `_has_descendant_source`, `_source_tree`, and the current broad dynamic-owner
   construction pipeline. Restore the `abca9b07` static paths in
   `argument_type`, `_add_argument`, `_add_args`, `add_direct_args`,
   `_config_values`, `has_nested_source`, `_from_cli_args`,
   `from_direct_cli_args`, `_parse_args`, and ordinary dispatch. Relation-free
   commands must use those paths unchanged.
2. Keep `_contains_relation` as the direct one-line scan:
   `return any(field.kwargs_relation is not None for field in
   fields_or_init_kwargs(owner))`, and call it only with reflectable owners.
   Discover nested relations while the existing structured-model recursion
   walks fields. Do not make `_contains_relation` recursive and do not replace
   `_is_dynamic_owner` with an equivalent renamed predicate.
3. Build the static parser with help disabled, parse the original argv with
   `parse_known_args`, and identify only the active command. Resolve each
   active relation selector through the same config, environment, and explicit
   CLI precedence as the ordinary path. A higher selector source skips its
   default or factory. Cache any evaluated selector or containing-owner default
   by qualified field path so the second parse reuses it and evaluates it at
   most once. Keep this state in parse-local mappings, never in user source
   dictionaries.
4. Reflect each resolved selector once, store its selected target fields by
   dependent-field path, add generated dotted options only to the active
   command parser, add help actions once, and parse the unchanged argv again.
5. Extend the existing declaration-order `_from_cli_args` and direct-function
   loops only at relation fields. Ordinary fields retain highest-source-wins
   behavior. A dependent kwargs field overlays, by key, a copied default or one
   lazy factory result, config mapping, environment mapping, whole CLI mapping,
   and generated dotted parameter values. Convert and validate selected
   parameters inline without invoking the target. Recurse through the existing
   structured-model path for nested owners.
6. A complete containing mapping or existing containing object suppresses its
   containing factory. A partial descendant source may materialize the
   containing default once. A fully supplied dependent mapping suppresses its
   kwargs factory. An explicit selector suppresses its selector factory.
7. For Pydantic CLI owners, read and write relation values at the same winning
   validation-alias location native Pydantic would use, including ordered
   `AliasChoices` and nested `AliasPath` values. Preserve unrelated keys,
   remove any conflicting unconverted relation input, and perform one final
   native `model_validate`. Do not implement only string aliases or reject
   non-string aliases.
8. Root help with no selected subcommand remains static and evaluates no
   unselected command factories. Help for a single command or active
   subcommand resolves only the selector needed to display that target's
   options and never evaluates the dependent kwargs factory. Add generated
   options only to the selected subcommand. Preserve `--Args` and
   positional/remainder behavior for relation-free commands, plus the explicit
   positional restriction for relation owners.
9. Let `effective_type` retain annotation semantics. Relation handling belongs
   at parser and conversion sites where the selector value is available. Use
   public `str_to_bool` and existing public base APIs; import no private base
   helpers.

**Success criteria:** normal commands follow the familiar pre-feature CLI
path; relations preserve config, environment, and CLI precedence; factories
run at most once and only when needed; nested relations, native Pydantic
aliases, active-subcommand isolation, static and expanded help, and `--Args`
work; and CLI conversion never constructs or invokes selected targets.

**Validation:** the import-only compatibility-shim run of `tests/test_cli.py`
passed 55 public behavior tests and 22 subtests; the sole failure was the
intentionally dummy `_bootstrap_owner` assertion removed in Phase 5. Focused
base validation passed 25 tests and 17 subtests with the stale schema test
deselected. Pydantic validation passed 18 current-contract tests; only two
stale Phase 5 negative assertions expecting `AliasPath` and `AliasChoices`
rejection remained. `uv run --group dev --extra pydantic ty check msup`,
`./run.py lint_check`, `./run.py format_check`, and `git diff --check` passed.
Correctness review confirmed selected signatures and required factories are
evaluated once, selected targets remain uninvoked, and all prior CLI findings
are resolved. The post-review simplification removed unused parser-cache owner
state and duplicate root reflection. Combined production LOC is 1,441.

## Phase 4: Reduce base consumers to baseline-shaped relation branches

**Status:** Not started

1. Simplify `to_dict` to the `abca9b07` field loop and value lookup shape.
   Ordinary fields delegate directly to `to_dict_value`; the only ordinary
   deviation may preserve a containing diagnostic path for an already
   structured runtime value. A dependent relation branch reads its runtime
   selector, reflects the selected signature exactly once, and converts and
   serializes supplied parameters in one loop without invoking the target.
2. Redesign `from_kwargs` as a declaration-order baseline conversion loop with
   relation-only branches. Do not resolve validation aliases for every field,
   do not maintain a general parallel converted-field map, and do not perform
   owner-wide topology traversal. Leave ordinary Pydantic inputs untouched for
   one native `model_validate` call. Convert ordinary non-Pydantic values with
   the existing direct `from_dict_value` path.
3. Resolve selectors only when a dependent relation needs them. Cache only
   runtime selector values or selected signatures that are reused by multiple
   dependents. Preserve lazy defaults and factories, independent mappings for
   multiple dependents, nested relation owners, full diagnostic paths, and
   target non-invocation.
4. Remove `FieldSpec.validation_paths`, `FieldSpec.validation_value`, and
   `FieldSpec.set_validation_value`. Implement only the Pydantic alias
   read/write behavior required for active selector, dependent, and nested
   relation fields. Support string aliases, `AliasPath`, and ordered
   `AliasChoices` without creating a general field-input framework.
5. Simplify `from_dict` and CLI integration after the base loop is reduced so
   they do not reconstruct reflection work or shift the removed complexity to
   another layer. Re-run the public CLI behavior suite and Pydantic alias
   probes after removing the `FieldSpec` alias state.
6. Run a correctness review and a separate simplification review. Measure
   semantic production LOC with public documentation and readable declarations
   intact.

**Success criteria:** `to_dict` and `from_kwargs` visibly follow their baseline
field loops with small relation branches; the three validation-path
declarations are absent; ordinary Pydantic fields remain native; selected
targets are inspected once and never invoked; all relation, alias, laziness,
round-trip, and CLI behavior remains intact; and production LOC remains below
1,443 without cosmetic compression.

## Phase 5: Align and minimize tests

**Status:** Not started

1. Update boolean-helper imports and assertions for public
   `msup.base.str_to_bool`. Remove tests and imports for `_add_target_args`,
   `_bootstrap_owner`, `_kwargs_from_fields`, `_construct_owner`,
   `_from_kwargs`, `_RAW_MATERIALIZED`, and any new implementation-only
   replacement.
2. Remove the Pydantic test expecting `AliasPath` and `AliasChoices` rejection.
   Add positive relation-conversion coverage through string aliases,
   `AliasPath`, and ordered `AliasChoices`, including conflicting canonical and
   alias inputs, so the converted winning value is the one native Pydantic
   receives. Change self and forward relation tests to expect the common
   preceding-selector lookup failure. Remove the reused selector rejection
   test and add a behavior test showing two dependent fields can link to the
   same preceding selector. Keep a relation field used as a selector only as
   an ordinary non-Callable-selector failure, not a special
   metadata-validation case.
3. Preserve focused coverage for dataclass, Pydantic v2, class constructor,
   function, and method relations; `Kwargs` and literal dictionary
   annotations; invalid dependent annotation, missing preceding selector, and
   non-Callable selector; selected signature validation; no target invocation;
   nested and multiple relations; JSON/dict round trips; defaults and lazy
   factories; and native Pydantic aliases.
4. Preserve CLI coverage for config/environment/CLI precedence, whole kwargs
   mappings plus selected dotted options, `--Args`, nested relation owners,
   help, subcommands, positional rules, and target-parameter validation.
   Prefer adapting existing behavior tests over adding implementation-shape
   tests.
5. Add regression tests only where simplification could otherwise lose a
   stated invariant, especially selector factory laziness, default mapping
   overlay, and the no-invocation guarantee.

**Success criteria:** tests describe the public contract, not removed helper
names, and all relation invariants are covered with the smallest useful set of
cases.

## Phase 6: Validate and review the final diff

**Status:** Not started

1. Run `./run.py check`.
2. Run focused suites first:
   `uv run --group dev --extra pydantic pytest tests/test_basic.py`,
   `uv run --group dev --extra pydantic pytest tests/test_cli.py`, and
   `uv run --group dev --extra pydantic pytest tests/test_pydantic.py`.
   Then run `./run.py test`.
3. Review `git diff -- msup/base.py msup/cli.py tests/test_basic.py
   tests/test_cli.py tests/test_pydantic.py` against this plan. Confirm the
   diff restores unrelated baseline formatting/control flow and does not leave
   stale private imports, hidden state sentinels, duplicate validation, or
   unreachable relation code.

**Success criteria:** every repository check passes, the entire test suite
passes, and the final production diff is limited to necessary relation support
and the shared boolean helper. The combined production LOC is below 1,443
lines.

## Review-comment disposition

| Comments | Required disposition |
| --- | --- |
| 1, 2, 3, 4, 5 | Phase 1 removes duplicate selector metadata checks, explicit self/order checks, duplicate-selector tracking, and the owner-wide Pydantic alias check; it uses `prior_fields` for the one required relation-link pass and permits multiple dependents per selector. |
| 6, 7 | Phase 1 restores the prior readable `get_collection_args` implementation. |
| 8 | Phase 1 restores the prior helper control-flow shapes for annotation origin, effective type, and union selection. |
| 9 | Phase 1 restores the named enum supported-types local. |
| 10, 17 | Phase 1 adds public `str_to_bool` to `msup/base.py`; Phase 3 imports and uses it from there. |
| 11 | Phase 2 inlines `_to_dict` into `to_dict`. |
| 12, 13 | Phase 2 removes repeated wrapping/validation and inlines the three-use `_kwargs_from_fields` logic instead of promoting a premature public abstraction. |
| 14 | Phase 2 inlines `_from_kwargs` into `from_kwargs` and deletes the private wrapper. |
| 15 | Phases 2 and 3 eliminate private base imports without adding a three-use public helper. |
| 16 | Phase 3 deletes `_RAW_MATERIALIZED` and its state propagation. |
| 18 | Phase 3 inlines and deletes `_is_dynamic_owner`. |
| 19 | Phase 3 reduces `_contains_relation` to the direct relation-field scan. |
| 20 | Phase 3 restores the ordinary CLI source/recursion flow and confines two-pass work to relation resolution and target-option registration. |

## Final success criteria

`kwargs_for` remains supported across base conversion, serialization, and the
CLI with the existing feature contract intact. The production code has no
unnecessary private cross-module APIs, redundant relation validation, broad
source-tree materialization state, or unrelated refactors, and all repository
checks pass.
