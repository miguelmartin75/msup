# **M**icro **S**erialization **U**tilities for **P**ython

[![coverage](https://miguelmartin75.github.io/msup/coverage.svg)](https://miguelmartin75.github.io/msup/coverage/)

> [!TIP]
> msup can be used as a Python-based alternative to [just](https://github.com/casey/just). See [run.py](./run.py).

msup converts typed Python values between dictionaries, JSON, and command-line
arguments. It has no required runtime dependencies. Pydantic v2 support is
optional.

```python
from typing import Annotated as A, Callable as C

from msup.base import to_json
from msup.cli import CliArg, cli


def sir(name: str) -> str:
    return f"Sir {name}"


def miss(name: str) -> str:
    return f"Miss {name}"


def show(
    name: A[str, CliArg(short="n", help="your name")],
    count: int = 1,
    name_fn: C[[str], str] = miss,
) -> None:
    print(to_json(locals(), type_class=show))


def echo(
    name: A[str, CliArg(short="n", help="your name")],
    count: int = 1,
    name_fn: C[[str], str] = sir,
) -> None:
    print([name_fn(name)] * count)


if __name__ == "__main__":
    cli(
        {
            show: "show the input arguments as JSON",
            echo: "echo your name N times",
        }
    )
```

```bash
./examples/function_args.py echo --name Bob --count 2 --name_fn examples.function_args.sir
./examples/function_args.py echo --Args '{"name": "Bob", "count": 2}'
```

`--Args` accepts inline JSON or a `.json` file path.

# Callable kwargs relations

A callable selector can drive the schema of a following `Kwargs` mapping. The
selected callable is reflected and the mapping is typed, but msup does not
invoke or construct that selected target. The application chooses when to call
it.

```python
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable

from msup.base import Kwargs
from msup.cli import CliArg, cli


@dataclass
class Limits:
    memory_gb: int = 4


def launch(workers: int, limits: Limits, label: str = "default") -> None:
    print(workers, limits, label)


@dataclass
class Job:
    target: Callable[..., Any] = launch
    kwargs: Annotated[
        Kwargs,
        CliArg(kwargs_for="target", help="arguments for the selected target"),
    ] = field(default_factory=lambda: {"label": "batch"})


def run(job: Job) -> None:
    # msup constructed Job, but did not call launch.
    job.target(**job.kwargs)


if __name__ == "__main__":
    cli(run)
```

The matching dependency-free example is
[examples/kwargs_for.py](./examples/kwargs_for.py). It has a conversion command
that keeps the target uncalled and a command that invokes it explicitly.

```bash
./examples/kwargs_for.py convert
./examples/kwargs_for.py run --kwargs.workers 6 --kwargs.limits.memory_gb 24
```

The CLI first resolves the effective `target`, then makes selected-target
options available. For example, `limits: Limits` produces
`--kwargs.limits.memory_gb`. A whole mapping is also accepted through
`--kwargs '{"workers": 6, "limits": {"memory_gb": 24}}'` or a `.json` file.

`Kwargs` is `dict[str, Any]`. `Metadata(kwargs_for="target")` is the
base-level relation marker for dictionary and JSON conversion. `CliArg`
inherits `Metadata`, so use `CliArg(kwargs_for="target", ...)` when the field
also participates in a CLI. The selector must be a preceding
`Callable[..., Any]` field and the dependent field must be `Kwargs` or
`dict[str, Any]`.

Callable references use canonical `module.qualname` strings, such as
`examples.kwargs_for.launch`. Loading a reference imports Python code, so
dictionary, JSON, environment, and CLI callable references are trusted input.
Only importable functions, methods, and classes have a canonical reference.

For non-CLI conversion, `from_dict(Job, payload)` and `from_json(Job, text)`
produce a typed `Job`; `to_dict(job)` and `to_json(job)` emit a canonical target
reference and typed explicit kwargs. `kwargs_from_dict(target, values)` converts
only the selected target's explicit mapping. `from_kwargs(owner, values)` does
the same relation-aware conversion for dataclass, regular-class, Pydantic v2,
or direct-function owners and returns an argument mapping without calling a
direct function.

## Dynamic CLI precedence and defaults

For a relation path, sources are applied from lowest to highest priority:

1. The containing owner's copied default or needed `default_factory`.
2. `--Args` JSON.
3. A containing structured-field environment value.
4. A containing structured whole-field CLI value.
5. Descendant field environments and whole-field CLI values.
6. Descendant dotted CLI options.
7. Selected-target parameter environments.
8. Generated selected-target dotted CLI options.

Mappings overlay by key, so `--kwargs.workers 6` keeps a default `label`.
Defaults are copied and factories run at most once when their layer is needed.
An explicit selector replaces a selector default. Existing materialized owner
objects are authoritative and do not cause their factory to run again.

Run `--help` with the same command arguments you will use. Root help does not
import a target. Command help stays static without an effective selector and
shows generated options when a default, configuration value, environment value,
or selector option identifies one.

Dynamic target parameters use canonical qualified long options only. Existing
static short options continue to work, but selected target parameters cannot
define a short option. Positional and remainder arguments cannot share a parser
scope with a callable kwargs relation.

## Owner support and boundaries

Relations work in dataclasses, regular Python class constructors, Pydantic v2
models, and direct functions or methods. They can be nested in statically known
dataclass, regular-class, or Pydantic v2 owners. Pydantic v2 receives one native
`model_validate` call after its linked selector and kwargs are converted, so its
normal validation remains active. Linked Pydantic selector and kwargs fields
must use their canonical names; string aliases, `AliasPath`, and `AliasChoices`
are not supported. Pydantic v1 is also not supported for linked fields.

The selected target may be a function, method, or class with annotated
positional-or-keyword or keyword-only parameters. Its body or constructor is
not invoked by reflection, conversion, serialization, or CLI parsing. A target
with positional-only parameters, `*args`, or `**kwargs` is not a dynamic kwargs
target. A dynamically selected structured target parameter may use ordinary
dotted options, but cannot introduce another `kwargs_for` relation.

Direct function owners are useful outside `cli` too:

```python
from typing import Annotated, Any, Callable

from msup.base import Kwargs, Metadata, from_kwargs


def run(
    target: Callable[..., Any],
    kwargs: Annotated[Kwargs, Metadata(kwargs_for="target")],
) -> None:
    target(**kwargs)


arguments = from_kwargs(
    run,
    {"target": "examples.kwargs_for.launch", "kwargs": {"workers": 2, "limits": {"memory_gb": 8}}},
)
# run has not been called. The application may now choose run(**arguments).
```

# More examples

Nested dataclasses produce dotted options such as `--optimizer.lr`
([source](./examples/readme/train.py)):

```python
from dataclasses import dataclass, field

from msup.cli import cli


@dataclass
class Optimizer:
    lr: float = 0.1


@dataclass
class Train:
    optimizer: Optimizer = field(default_factory=Optimizer)


def train(args: Train) -> None:
    print(args)


cli(train)
```

```bash
./examples/readme/train.py --optimizer.lr 0.01
```

Pydantic v2 also works with `cli` ([source](./examples/pydantic_basic.py)):

```python
from typing import Annotated

from pydantic import BaseModel, Field

from msup.cli import CliArg, cli


class Args(BaseModel):
    name: Annotated[str, CliArg(help="name to greet")] = "world"
    values: Annotated[list[int], CliArg(help="values to show", short="v")] = Field(
        default_factory=lambda: [1, 2]
    )


def greet(args: Args) -> None:
    print(f"hello, {args.name}: {args.values}")


cli(greet)
```

```bash
./examples/pydantic_basic.py --name "wow pydantic" --values 1 2
```

Regular classes can be constructed and serialized as dictionaries or JSON:

```python
from msup.base import from_dict, to_dict, to_json, to_kwargs


class Optimizer:
    def __init__(self, lr: float, steps: int = 1):
        self.lr = lr
        self.steps = steps


optimizer = from_dict(Optimizer, {"lr": 0.1})
payload = to_dict(optimizer)
json_text = to_json(optimizer)
kwargs = to_kwargs(Optimizer, optimizer)
print(json_text)
```

```bash
./examples/readme/regular_class.py
```

A final positional list captures all remaining tokens, including option-like
values ([source](./examples/remainder.py)):

```bash
./examples/remainder.py --cwd build --retries 2 run --target staging --verbose
```

- Direct function arguments: [examples/function_args.py](./examples/function_args.py)
- Callable kwargs relations: [examples/kwargs_for.py](./examples/kwargs_for.py)
- Nested dataclass command: [examples/nested.py](./examples/nested.py)
- Multiple CLI commands: [examples/multicli.py](./examples/multicli.py)
- Simple CLI: [examples/simple.py](./examples/simple.py)
- Pydantic v2 CLI: [examples/pydantic_basic.py](./examples/pydantic_basic.py)
- Regular-class and PyTorch construction: [examples/pt_basic.py](./examples/pt_basic.py)

# Features

- Typed conversion and serialization
  - Primitives: `str`, `int`, `float`, and `bool`.
  - Other types: `Any`, optionals, and unambiguous unions. Non-optional unions
    are conversion-only, not CLI annotations.
  - Collections: lists, dictionaries, and tuples convert recursively. The CLI
    supports lists and variable-length tuples; fixed-length tuples are
    conversion-only.
  - Enum values serialize as declared member values and deserialize through the
    declared Enum type.
- CLI commands
  - Use direct typed functions or one dataclass, regular class, or Pydantic v2
    model parameter. A mapping of functions creates named subcommands.
  - `CliArg(pos=True)` makes a value positional. A final positional list or
    variable-length tuple with `opt=False` receives all remaining arguments.
- CLI metadata
  - `Annotated[T, CliArg(...)]` sets help text, short options, environment
    variables, positional and optional behavior, and hides secret defaults from
    help.
  - Nested dataclass and Pydantic v2 values accept dotted options, inline JSON
    objects, and JSON file paths.
- JSON I/O
  - `from_json` reads strings, `StringIO`, other file-like streams, and paths.
    `to_json` returns JSON or writes to file-like streams and `.json` paths.

# Design philosophy

- Minimal code and no required runtime dependencies.
- Standard-library-first and opinionated APIs that reduce boilerplate.
- Typed configuration conversion without implicit application execution.

# Install

```bash
uv pip install msup
```

Or add it to a project:

```bash
uv add msup
```
