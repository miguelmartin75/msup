# **M**icro **S**erialization **U**tilities for **P**ython

[![coverage](https://miguelmartin75.github.io/msup/coverage.svg)](https://miguelmartin75.github.io/msup/coverage/)

> [!TIP]
> msup can be used as a [just](https://github.com/casey/just) replacement. See [just.py](./just.py).

```python
from typing import Annotated, Callable
from msup.base import to_json
from msup.cli import cli, CliArg

def sir(name: str) -> str:
    return f"Sir {name}"

def miss(name: str) -> str:
    return f"Miss {name}"

def show(name: Annotated[str, CliArg(short="n", help="your name")], count: int = 1, name_fn: Callable[[str], str] = miss):
    print(to_json(locals(), type_class=show))  # encode the function args to JSON

def echo(name: Annotated[str, CliArg(short="n", help="your name")], count: int = 1, name_fn: Callable[[str], str] = sir):
    print([name_fn(name)] * count)

if __name__ == "__main__":
    # creates a CLI interface with sub-commands 'show' and 'echo'
    cli({
        show: "show the input arguments as JSON", 
        echo: "echo your name N times", 
    })
```

Run the above:
```bash
./examples/function_args.py echo --name 'Bob' --count 2 --name_fn examples.function_args.sir
```

or, provide JSON, e.g. `./examples/function_args.py echo --Args '{"name": "bob", "count": 2}'`; `--Args` can point to a filepath too. See [More Examples](#more-examples) below or in the [examples](./examples) folder.

---

With no required dependencies and only 891 LOC (`wc -l msup/*.py`), this library lets you:

- create CLIs from typed functions and nested dataclass or Pydantic v2 definitions
- construct regular Python classes from their `__init__` parameters and serialize or deserialize regular classes, dataclasses, and Pydantic v2 models as JSON and Python dictionaries

Yes, the small LOC is an intentional feature.

# More Examples

Nested dataclasses produce nested options, e.g. `--class.field` ([source](./examples/readme/train.py)):

```python
from dataclasses import dataclass, field
from msup.cli import cli

@dataclass
class Optimizer:
    lr: float = 0.1

@dataclass
class Train:
    optimizer: Optimizer = field(default_factory=Optimizer)

def train(args: Train):
    print(args)

cli(train)
```

```bash
./examples/readme/train.py --optimizer.lr 0.01
```

A Pydantic v2 model provides typed CLI options ([source](./examples/pydantic_basic.py)):

```python
from typing import Annotated

from pydantic import BaseModel, Field

from msup.cli import CliArg, cli

class Args(BaseModel):
    name: Annotated[str, CliArg(help="name to greet")] = "world"
    values: Annotated[list[int], CliArg(help="values to show", short="v")] = Field(default_factory=lambda: [1, 2])

def greet(args: Args):
    print(f"hello, {args.name}: {args.values}")

cli(greet)
```

```bash
./examples/pydantic_basic.py --name integration --values 1 2
```

`Optimizer` is a regular Python class that can be constructed and serialized to/from a dict or JSON.

```python
from msup.base import from_dict, to_dict, to_json, to_kwargs

class Optimizer:
    def __init__(self, lr: float, steps: int = 1):
        self.lr = lr
        self.steps = steps

optimizer = from_dict(Optimizer, {"lr": 0.1})
payload = to_dict(optimizer)
json_text = to_json(optimizer)
kwargs = to_kwargs(Optimizer, optimizer)  # to construct a copy via `Optimizer(**kwargs)`
print(json_text)
```

```bash
./examples/readme/regular_class.py
```

A final positional list captures all remaining tokens, including option-like values ([source](./examples/remainder.py)):

```python
from typing import Annotated

from msup.cli import CliArg, cli

def forward(
    command: Annotated[str, CliArg(pos=True)],
    cwd: str = ".",
    retries: int = 1,
    # opt=False makes this final list consume every remaining token.
    remaining: Annotated[list[str] | None, CliArg(pos=True, opt=False)] = None,
):
    print(f"{command=}: {cwd=}: {retries=}: {remaining=}")

cli(forward)
```

```bash
./examples/remainder.py --cwd build --retries 2 run --target staging --verbose
```

Here's some more examples:
- Direct function arguments: [examples/function_args.py](./examples/function_args.py)
- Nested dataclass command: [examples/nested.py](./examples/nested.py)
- Multiple CLI commands: [examples/multicli.py](./examples/multicli.py)
- Simple CLI: [examples/simple.py](./examples/simple.py)
- Pydantic v2 CLI: [examples/pydantic_basic.py](./examples/pydantic_basic.py)
- Regular-class and PyTorch construction: [examples/pt_basic.py](./examples/pt_basic.py)

# Features

- Typed conversion and serialization
    - Primitives: `str`, `int`, `float`, and `bool`.
    - Other types: `Any`, optionals, and unambiguous unions. Non-optional unions are conversion-only, not CLI annotations.
    - Collections: lists, dictionaries, and tuples convert recursively. The CLI supports lists and variable-length tuples; fixed-length tuples are conversion-only.
    - Importable callables use `module.name` strings for loading and serialization.
    - `from_dict`, `to_dict`, `from_json`, and `to_json` convert typed values. `to_kwargs` prepares matching constructor settings, for example for `torch.optim.Adam`.
    - `to_json(locals(), type_class=handler)` serializes only the handler's declared arguments, using its annotations.
- CLI commands
    - Use direct typed functions or one dataclass or Pydantic v2 model parameter. A mapping of functions creates named subcommands.
    - `CliArg(pos=True)` makes a value positional. A final positional list or variable-length tuple with `opt=False` receives all remaining arguments.
- CLI configuration and metadata
    - `Annotated[T, CliArg(...)]` sets help text, short options, environment variables, positional and optional behavior, and hides secret defaults from help.
    - Nested dataclass and Pydantic v2 values accept dotted options such as `optimizer.lr`, inline JSON objects, and JSON file paths.
    - Missing values use defaults and default factories. Precedence is: explicit option, `CliArg(env=...)`, `--Args` JSON (inline or from a `.json` file), then the default.
- JSON I/O
    - `from_json` reads strings, `StringIO`, other file-like streams, and paths. `to_json` returns JSON or writes to file-like streams and `.json` paths.

# Design Philosophy

- minimal LOC
- no dependencies by default; dependencies are opt-in (i.e. Pydantic is optional)
- opinionated to reduce boilerplate

# Install

```bash
uv pip install msup
```

or with a `pyproject.toml`

```
uv add msup
```
