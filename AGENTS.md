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

## Public Interface Exception

- Keep the top-of-module forward declarations that summarize the intended public interface.
- These declarations are intentionally redundant at runtime. They let readers identify the public API before implementation details and must not be removed or moved as a declaration-order cleanup.
