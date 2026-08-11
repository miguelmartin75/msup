# Python Code Guidelines

`AGENTS.md` contains the project-wide rules. This document adds Python-specific guidance.

## Imports

- Keep imports at module scope. Use local imports only for optional dependencies, unavoidable cycles, or measured startup improvements.
- Use `if TYPE_CHECKING:` only for static-only annotations. Import normally when a serializer, framework, or `typing.get_type_hints()` resolves an annotation at runtime.

```py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maprift.execution.lepton import LeptonBatchJobSpec


def submit_batch_job(spec: LeptonBatchJobSpec) -> str: ...
```

## Comments and Docstrings

- Comment rationale, constraints, or surprising behavior, not what the code already says. Keep comments beside the code they explain.
- Add a docstring when a public API or non-obvious contract is unclear from its signature and names. Document behavior, constraints, returns, and errors, not parameter names.

```py
def calculate_total_size(object_sizes: list[int | None]) -> int:
    result = 0
    for object_size in object_sizes:
        # S3 reports no object size for directory placeholders.
        if object_size is None:
            continue
        result += object_size
    return result
```

## Naming and API Semantics

- Treat acronyms as normal words: use `parse_url` and `HttpHeader`, not `parse_URL` or `HTTPHeader`.
- Use familiar abbreviations such as `dir`, `msg`, `arg`, `param`, `cfg`, `env`, `url`, `rect`, `coord`, `sym`, `lit`, `err`, and `opts`. Spell out unfamiliar abbreviations.
- Use verbs for actions. Use `is_`, `has_`, `can_`, `should_`, or an established predicate for booleans, such as `file_exists` instead of `exists_file`.
- Name error and exception types with an `Error` suffix.
- Use `create_*`, not `new_*`, for one logical object and `make_*` for aggregates or multiple objects. Avoid `factory` in API names.
- Use `find_*` for a match or position, and `has_*` or `contains_*` for booleans.
- In custom collections, use `add` for membership insertion and `append` for insertion at a sequence's end.
- Distinguish copy-returning operations from mutating ones, such as `with_timeout` and `set_timeout`.
- Prefer direct attributes. Use properties only for cheap, side-effect-free access and verb-named methods for work, side effects, or non-constant-time access.
- Use `UpperCamelCase` for classes, dataclasses, enums, and exception types. Use `lower_snake_case` for modules, functions, methods, variables, and parameters. Use `UPPER_SNAKE_CASE` for module constants.

```py
class HttpRequestError(Exception):
    pass


def parse_url(url: str) -> str: ...


def file_exists(path: str) -> bool: ...


def find_token(tokens: list[str], expected: str) -> int | None: ...
```

## Formatting

- Follow the Ruff configuration in `pyproject.toml` for formatting, imports, indentation, quotes, and line length.
