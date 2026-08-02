# AGENTS.md

Follow the repository instructions in `CODE_GUIDELINES.md` when changing Python code.

## Commands

`./run` is the repository-local executable task runner. Run it directly from this checkout.

- `./run setup_dev`: install development dependencies.
- `./run test`: run the test suite.
- `./run coverage`: run the test suite and generate coverage reports.
- `./run check`: run type, lint, and formatting checks.
    - `./run lint_check`: check Ruff linting without modifying files.
    - `./run format_check`: check formatting without modifying files.
    - `./run type_check`: type check the repository with ty.
- `./run lint`: apply Ruff lint fixes.
- `./run format`: apply Ruff formatting.
- `./run examples`: run every executable example.
- Release:
    - `./run tag_release <version>`: create and push a release commit and tag.
    - `./run publish_release`: build and upload a release to PyPI.

## Public Interface Exception

- Keep the top-of-module forward declarations that summarize the intended public interface.
- These declarations are intentionally redundant at runtime. They let readers identify the public API before implementation details and must not be removed or moved as a declaration-order cleanup.
