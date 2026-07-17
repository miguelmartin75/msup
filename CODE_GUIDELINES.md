# Python Code Guidelines

## Simplicity

- Prefer simple direct code and solutions over abstractions, unless clearly repeated many times, e.g. >3x
    - Three similar lines is better than a premature abstraction.
    - Add helpers only when the logic is used more than 3 times. When judging whether a helper is warranted, shared usage from tests counts toward that threshold.
    - Avoid trivial helpers that perform little to no computation unless they are used frequently and materially improve readability.
- Prefer simpler language features. Only reach for metaprogramming, framework indirection, or other advanced language specific constructs when they provide a quantifiable benefit.
    - Prefer plain functions and direct construction over builders, helper classes, or framework-style indirection unless stateful behavior, lifecycle management, polymorphism, or another concrete need justifies the abstraction.
- Keep Cyclic Code Complexity at a moderate level; if a function gets too long or branchy, refactor it into smaller parts.
    - When performing this refactor: take out the biggest chunks first in greedy manner until Cyclic Code Complexity is back to moderate; don't immediately refactor everything into helpers.
- Prefer the standard library and built-in platform APIs over third-party dependencies unless there is a clear justification.

## Scope and Simplicity

- Keep changes small and direct.
- Prefer simple direct code and solutions over abstractions, unless clearly repeated many times (>3x).
- Three similar lines is better than a premature abstraction.
- Prefer plain functions and direct construction over builders, helper classes, or framework-style indirection unless stateful behavior, lifecycle management, polymorphism, or another concrete need justifies the abstraction.
- Avoid trivial helpers that perform little to no computation unless they are used frequently and materially improve readability.
- Don't declare a constant if it is only used <3x. Magic constants are NOT scary.
- Prefer the simpler language feature or control-flow shape. Only reach for metaprogramming, framework indirection, or other advanced constructs when they provide a quantifiable benefit.
- Only use a more complex language construct such as a decorator, descriptor, metaclass, or dynamic attribute hook when it is necessary for correctness, measurable performance, meaningful LOC reduction, or another quantifiable improvement.

```py
# Do
# assume used >3 times
def normalize_slug(slug: str) -> str:
    return slug.strip().lower()

def build_route(title: str) -> dict[str, str]:
    slug = normalize_slug(title)
    return {"title": title, "path": f"/{slug}"}

# Don't
class RouteBuilder:
    def build(self, title: str) -> dict[str, str]:
        return {"title": title, "path": f"/{title.strip().lower()}"}
```

## Declaration Order

- Keep declarations topologically sorted where practical.
- Keep imports at module scope by default. Use local, lazy, or type-only imports only when they materially improve correctness, optionality, startup cost, or cycle management.
- Define helpers close enough to their usage that a reader can scan top-to-bottom without jumping.
- If declarations become mutually recursive or force awkward forward references, keep them adjacent only when a simpler refactor is not practical, and otherwise refactor to break the cycle.
- In Python modules, use this file order: imports, exported types, module constants, small pure helpers, larger functions, classes, module entry point if needed.
- Use `if TYPE_CHECKING:` for annotation-only imports or cycle avoidance instead of importing type-only modules at runtime.
- Do not use `from __future__ import annotations`; treat it as deprecated functionality and use modern Python annotations directly.

```py
# Do

# assume used >3 times
def normalize_slug(slug: str) -> str:
    return slug.strip().lower()

def route_path(title: str) -> str:
    return f"/posts/{normalize_slug(title)}"

def build_route(title: str) -> dict[str, str]:
    return {"title": title, "path": route_path(title)}

if __name__ == "__main__":
    from app.cli import main

    raise SystemExit(main())

# Don't
from app.cli import main

def build_route(title: str) -> dict[str, str]:
    return {"title": title, "path": route_path(title)}

DEFAULT_BASE_PATH = "/posts"

def route_path(title: str) -> str:
    return f"{DEFAULT_BASE_PATH}/{normalize_slug(title)}"

def normalize_slug(slug: str) -> str:
    return slug.strip().lower()
```

## Dependencies and Comments

- Do not add third-party dependencies unless they solve the problem directly.
- Prefer the standard library and built-in platform APIs over third-party dependencies unless there is a clear justification, such as measurable performance benefits, explicit instructions, or existing use in the same module.
- Keep comments brief and only where they add real clarity (where logic is unclear)
- Use docstrings for public APIs or non-obvious contracts, not to restate obvious code.

## Returns and Control Flow

- Prefer real control flow (if/elif/else/break) over early returns. Use early `return` only for real early exits, such as guard clauses, invalid input, empty data, or stopping a linear scan once the answer is found.
- Do not use `return` as a substitute for explicit branching when `if` / `else`, `switch`, `case`, or `match` would keep the alternatives clearer.
- Do not introduce a temporary variable only to immediately return it unchanged.
- In small callbacks, lambdas, comparators, or key functions, direct returns are fine.
- When a value is assembled across several steps, use a local variable and one final `return`.

## Data Shapes

- Prefer named structured data for stable values that:
  - are stored or passed around as a named concept,
  - cross module or API boundaries,
  - have multiple independent call sites where field names materially improve clarity.
- Prefer tuples or other small local shapes for:
  - local temporary values,
  - return values that are immediately unpacked,
  - short-lived data used only at a small number of nearby call sites.
- For stable structured data in Python: prefer `dataclass`.
- Do not convert a small local tuple-like result into a heavier named structure just for style clean-up if the caller immediately unpacks it.
    - When in doubt, keep the smaller, more local data shape.

```py
# Do
from dataclasses import dataclass
from datetime import datetime

def split_md_and_yaml(data: str) -> tuple[str, SimpleYaml]:
    return data, SimpleYaml()

md, yaml = split_md_and_yaml(src)

@dataclass
class RouteInfo:
    title: str
    dt: datetime
    uri: str

routes.sort(key=lambda route: route.dt)
for route in routes:
    print(route.title, "->", route.uri)

# Don't
@dataclass
class ParsedMarkdown:
    md: str
    yaml: SimpleYaml

def split_md_and_yaml_bad(data: str) -> ParsedMarkdown:
    return ParsedMarkdown(md=data, yaml=SimpleYaml())
```

## Naming

- Treat acronyms like normal words.
- Prefer standard abbreviations such as `dir`, `msg`, `arg`, `param`, `cfg`, `env`, `url`, `rect`, `coord`, `sym`, `lit`, `err`, and `opts`.
- Prefer subject-verb names, e.g. `file_exists`, `fileExists`, not `exists_file` or `existsFile`.
- For booleans, prefer names such as `is_ready`, `isReady`, `has_items`, `hasItems`, `can_write`, `canWrite`, and `should_retry`, `shouldRetry`.
- Make top-level declarations public only when they are part of the module's intended public API. Keep implementation details and internal module-local helpers private, using a leading underscore where that is the project convention.
- Error and exception types should end in `Error`.
- Prefer direct object construction when it keeps the code simple.
- Avoid the word `factory` in names. Use `create` for functions or methods that construct one logical value.
- Use `make` when the operation allocates many objects or builds a larger aggregate such as a collection, table, map, or buffer.
- Use names that distinguish returning a position or match (`find...`) from returning a boolean (`has...` or `contains...`).
- Prefer `add` over `append` for custom collection APIs.
- If both mutating and copy-returning forms exist, use names that make that distinction obvious.
- Prefer direct field or property access over trivial getters and setters.
- If an accessor is needed, prefer property syntax only for cheap, side-effect-free access. Use verb-prefixed methods when the operation has side effects or non-trivial cost.
- In Python, use `UpperCamelCase` for classes, dataclasses, enums, and exception types.
- Use `lower_snake_case` for variables, parameters, functions, methods, and modules.
- Use `UPPER_SNAKE_CASE` for module-level constants.
- For more complex construction logic, prefer free functions such as `create_route(...)` over `new_route(...)`.
- If a getter or setter is needed, use `@property` only for cheap, side-effect-free access. Use `get_foo` and `set_foo` when the operation has side effects, is not `O(1)`, or is otherwise more than simple field access.

```py
# Do
def parse_url(url: str) -> str: ...
def check_http_header(header: str) -> bool: ...
def file_exists(path: str) -> bool: ...
def add_route(routes: list[Route], route: Route) -> None: ...

class RouteError(Exception):
    pass

def create_route(title: str) -> Route: ...

# Don't
def parse_URL(url: str) -> str: ...
def check_HTTP_header(header: str) -> bool: ...
def exists_file(path: str) -> bool: ...
def append_route(routes: list[Route], route: Route) -> None: ...

class route_error(Exception):
    pass

def new_route(title: str) -> Route: ...
```

## Formatting

- Let the formatter handle mechanical spacing, but do not use formatting to hide control flow or overly dense code.
- For multiline string literals, start the content on the next line.
- Prefer multiline formatting once literals, parameter lists, function calls, or props stop fitting comfortably on one line.
- Follow language-specific indentation and syntax-spacing conventions.
- Use 4 spaces for indentation.
- Write slices without spaces around the colon, e.g. `data[:count]` and `data[i:-3]`.

```py
# Do
xs = data[:count]
tail = data[i:-3]
msg = """
hello
world
"""

route = {
    "title": "Hello",
    "path": "/hello",
}

# Don't
xs = data[: count]
tail = data[i : -3]
msg = """hello
world
"""
```
