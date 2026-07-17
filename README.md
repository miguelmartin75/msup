# **M**icro **S**erialization **U**tilities for **P**ython

With no required dependencies and only 605 LOC, you can:

- create a CLI application from nested dataclass definitions (see [example](#example) below)
- serialize/deserialize dataclasses to/from JSON and Python dictionaries without pydantic

Yes, the small LOC is a feature.

Serialization and deserialization of dataclasses supports:

- validating types
- basic primitives: float, str, int
- optionals
- unions if there is no ambiguity
- nested dataclasses
- callables defined as a string
- sub-objects loaded from a JSON string or `.json` file path
- Features that are TODOs:
  - [ ] enum
  - [ ] renaming fields

This library is designed with the following design philosophies:

- simplicity
- minimal LOC
- no dependencies by default, i.e. dependencies are opt-in
- opinionated to reduce boilerplate

## Example

The following demonstrates a multi-command CLI that serializes a dataclass to JSON. A related runnable example is at [examples/cli/multicli.py](./examples/cli/multicli.py).

```python
import os
from dataclasses import dataclass
from typing import Callable

from examples.cli.callbacks import cosine_warmup_lr_step
from msup.cli import cli, cliarg, to_json

@dataclass
class ModelConfig:
    n_layers: int = cliarg(help="number of layers for the model", default=10)
    checkpoint_path: str | None = cliarg(short="-chkpt", help="path of the checkpoint", default=None)

@dataclass
class TrainArgs:
    model_config: ModelConfig = cliarg(default_factory=ModelConfig)
    lr: float = 0.01
    name: str = cliarg(help="name of experiment", default="example")
    lr_step_fn: Callable[[int, float], float] = cliarg(default=cosine_warmup_lr_step)
    num_workers: int = -1
    cont: bool = cliarg(help="continue training from last known iter?", default=False)
    config_root_dir: str = cliarg(default="./configs")

@dataclass
class EvalArgs:
    model_config: ModelConfig = cliarg(default_factory=ModelConfig)
    num_workers: int = -1

def train(args: TrainArgs):
    print(to_json(args))
    os.makedirs(args.config_root_dir, exist_ok=True)
    to_json(args, os.path.join(args.config_root_dir, args.name + ".json"))

def eval(args: EvalArgs):
    print(to_json(args))

if __name__ == "__main__":
    cli({train: "train a model", eval: "evaluate a model"})
```

From the repository root:

```bash
PYTHONPATH=. python3 examples/cli/multicli.py train

# Use an importable Python callable and reproduce a JSON configuration.
PYTHONPATH=. python3 examples/cli/multicli.py train --lr_step_fn examples.cli.callbacks.identity_step_fn --lr 0.1 --name identity
PYTHONPATH=. python3 examples/cli/multicli.py train --Args configs/identity.json --lr 0.2
```

Nested dataclasses accept a JSON file path or JSON object from the CLI:

```bash
PYTHONPATH=. python3 examples/cli/multicli.py train --model_config configs/models/small.json
PYTHONPATH=. python3 examples/cli/multicli.py train --model_config '{"n_layers": 1}'
```

CLI fields support primitives, `Any`, nested dataclasses, importable `Callable[...]`, `dict[K, V]`, `list[T]`, and `tuple[T, ...]`. `T | None` works for any supported type, including `list[int] | None`; other unions are rejected because CLI input is ambiguous. Use `cliarg(pos=True, opt=False, default_factory=list)` on a final `list[str]` field to capture remaining positional arguments.

Configuration can be a JSON object or `.json` file passed with `--Args` or `--<DataclassName>`. Explicit CLI values override environment values, configuration, and dataclass defaults, in that order.
