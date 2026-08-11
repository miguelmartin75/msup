# AGENTS.md

Follow the repository instructions in `CODE_GUIDELINES.md` when changing Python code.

## Commands

`./run.py` is the repository-local executable task runner. Run it directly from this checkout.

- `./run.py setup_dev`: install development dependencies.
- `./run.py test`: run the test suite.
- `./run.py coverage`: run the test suite and generate coverage reports.
- `./run.py check`: run type, lint, and formatting checks.
    - `./run.py lint_check`: check Ruff linting without modifying files.
    - `./run.py format_check`: check formatting without modifying files.
    - `./run.py type_check`: type check the repository with ty.
- `./run.py lint`: apply Ruff lint fixes.
- `./run.py format`: apply Ruff formatting.
- `./run.py examples`: run every executable example.
- Release:
    - `./run.py tag_release <version>`: create and push a release commit and tag.
    - `./run.py publish_release`: build and upload a release to PyPI.

## Python Design and Code Rules

- Keep the top-of-module forward declarations that summarize the intended public interface.
- These declarations are intentionally redundant at runtime. They let readers identify the public API before implementation details and must not be removed or moved as a declaration-order cleanup.
- Make module declarations and class members public by default. Use leading underscores only for framework hooks or implementation details callers must not rely on, never merely because a declaration is a helper or omitted from `__all__`.
- Use conditionals or return values for expected outcomes. Raise exceptions for invalid boundary input, violated preconditions, I/O failures, or external failures. Catch only to recover, add context, or translate at a boundary.
- Use `list[T]` for variable-length homogeneous collections and fixed tuples for short-lived unpacked values. Use `dataclass` for named structured values stored, passed across boundaries, or used at multiple call sites.
- Prefer branching to early returns. Use early returns only for guards, successful searches, or measurable runtime improvements. Return simple expressions directly.
- When a return value must be assembled across multiple steps, use `result` as the default variable name and return it once.
- Order modules top-down by dependency: imports; constants and aliases; enums and classes; functions; entry point. Dependency order overrides grouping. Keep mutual recursion adjacent unless breaking the cycle is simpler.
- Keep literals inline for up to three same-meaning uses. Name them at four uses, or earlier to convey units, protocols, formats, sentinels, domain thresholds, or defaults.
- Prefer plain functions and direct construction. Add reuse abstractions only at four same-meaning uses; tests count. Use builders, frameworks, or metaprogramming only for concrete state, lifecycle, polymorphism, correctness, performance, or substantial code reduction.
- Large functions are acceptable for one operation. Do not create single-use helper functions.
- Before implementing functionality, check the standard library, then applicable runtime dependencies in `pyproject.toml`. Prefer the standard library; add a dependency only when neither meets the need.

## Testing

- Do not introduce tests that cover source code content existence
- Aim to minimize the number of unit tests
- Robustness tests must use mocks/interfaces to simulate failures for where failures may occur (opening files) with iterations, e.g. call-site 1 fails, then call-site 2 fails, etc.
