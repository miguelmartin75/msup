# **M**icro **S**erialization **U**tilities for **P**ython

```
uv pip install msup
```

With no required dependencies and only 591 LOC (`wc -l msup/*.py`), this library enables you to:

- create a CLI application from nested dataclass definitions (see [example](#example) below)
- serialize/deserialize dataclasses or regular Python classes to/from JSON and Python dictionaries without dependencies

Yes, the small LOC is an intentional feature.

# design philosophy

This library is designed with the following design philosophies:

- simplicity
- minimal LOC
- no dependencies by default, i.e. dependencies are opt-in
- opinionated to reduce boilerplate

# feature list

Serialization and de-serialization of:

- dataclasses
    - validating types
    - basic primitives: float, str, int
    - optionals, including `list[T] | None`
    - unions if there is no ambiguity
    - nested dataclasses
    - callables defined as importable strings
    - sub-objects loaded from a string representing a:
      - JSON object, e.g. `'{"x": 3, "name": "abc"}'`
      - JSON file, e.g. `myfile.json`
    - CLI collection fields and final positional argument capture
    - CLI JSON configuration with CLI, environment, config, and default precedence
    - TODO: in a future version, hooks will be added to support other serialization formats such as YAML
- other Python classes with `__init__`, e.g. `torch.optim.Adam` (see [examples/pt_basic.py](./examples/pt_basic.py))

# TODOs

- [ ] parameter sweep example
- [ ] hooks to support other serialization formats, e.g. YAML
- [ ] basic SQLite ORM, supporting:
    - schema generation with support to mark fields as a PK, FK and an index
    - encode/decode from SQLite
- [ ] dataclass serialization
    - [ ] renaming fields
    - [ ] enum

## examples

- simple CLI: [examples/simple.py](./examples/simple.py)
- multiple CLI commands with nested config (see below): [examples/multicli.py](./examples/multicli.py)
- create a PyTorch model and optimizer from config: [examples/pt_basic.py](./examples/pt_basic.py)
    - This example constructs Python classes, such as a `torch.optim.Adam`, or a user-provided optimizer class, e.g.
        ```bash
        python examples/pt_basic.py test_optim_advanced --lr 0.42 --optim torch.optim.SGD
        ```

The following demonstrates automatically creating a multi-command CLI serializing a dataclass to JSON. You can find this example in [examples/multicli.py](./examples/multicli.py).

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
    model_config: ModelConfig = cliarg(short="", default_factory=ModelConfig)
    lr: float = 0.01
    name: str = cliarg(help="name of experiment", default="example")
    lr_step_fn: Callable[[int, float], float] = cliarg(help="learning-rate step function", default=cosine_warmup_lr_step)
    num_workers: int = -1
    cont: bool = cliarg(help="continue training from last known iter?", default=False)
    config_root_dir: str = cliarg(help="root directory where configuration is serialized to", default="./configs")

@dataclass
class EvalArgs:
    model_config: ModelConfig = cliarg(short="", default_factory=ModelConfig)
    num_workers: int = -1

def train(args: TrainArgs):
    print("train args:")
    print(to_json(args))
    os.makedirs(args.config_root_dir, exist_ok=True)
    config_out_path = os.path.join(args.config_root_dir, args.name + ".json")

    print(f"\nwriting config to: {config_out_path}")
    to_json(args, config_out_path)

def eval(args: EvalArgs):
    print("eval args:")
    print(to_json(args))

if __name__ == "__main__":
    cli({
        train: "train a model",
        eval: "evaluate a trained model",
    })
```

With this example, you can run the train or eval function via `python <script> {train,eval} [optional-args...]`, e.g.:

```bash
PYTHONPATH=. python3 examples/multicli.py train
```

Use an importable Python callable and reproduce a JSON configuration:

```bash
PYTHONPATH=. python3 examples/multicli.py train --lr_step_fn examples.cli.callbacks.identity_step_fn --lr 0.1 --name identity
PYTHONPATH=. python3 examples/multicli.py train --Args configs/identity.json --lr 0.2
```

Nested dataclasses can be read from a JSON file or JSON object from the CLI:

```bash
PYTHONPATH=. python3 examples/multicli.py train --model_config configs/models/small.json
PYTHONPATH=. python3 examples/multicli.py train --model_config '{"n_layers": 1}'
```
