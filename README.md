# **M**icro **S**erialization **U**tilities for **P**ython

```python
from msup.base import to_json
from msup.cli import cli

def greet(name: str, count: int = 1):
    print(to_json(locals(), type_class=greet))

cli(greet)
```

With no required dependencies and only 921 LOC (`wc -l msup/*.py`), this library lets you:

- create CLIs from typed functions and nested dataclass or Pydantic v2 definitions
- construct regular Python classes from their `__init__` parameters and serialize or deserialize regular classes, dataclasses, and Pydantic v2 models as JSON and Python dictionaries

Yes, the small LOC is an intentional feature.

# Install

```bash
uv pip install msup
```

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

- simplicity
- minimal LOC
- no dependencies by default, so dependencies are opt-in
- opinionated to reduce boilerplate

# More Examples

Nested dataclasses produce nested options:

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

A mapping of functions creates subcommands:

```python
from msup.cli import cli

def train(name: str):
    print(name)

def evaluate(name: str):
    print(name)

cli({train: "train a model", evaluate: "evaluate a model"})
```

`Optimizer` is a regular class that can be built from a dictionary and serialized to a dictionary or JSON. CLI commands require typed functions, dataclasses, or Pydantic v2 models. `to_kwargs` prepares matching settings for `torch.optim.Adam`:

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
```

See:
- Direct function arguments: [examples/function_args.py](./examples/function_args.py)
- Nested dataclass command: [examples/nested.py](./examples/nested.py)
- Multiple CLI commands: [examples/multicli.py](./examples/multicli.py)
- Simple CLI: [examples/simple.py](./examples/simple.py)
- Pydantic v2 CLI: [examples/pydantic_basic.py](./examples/pydantic_basic.py)
- Regular-class and PyTorch construction: [examples/pt_basic.py](./examples/pt_basic.py)
- Contributor backlog: [dev/TODO.md](./dev/TODO.md)
