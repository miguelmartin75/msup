# **M**icro **S**erialization **U**tilities for **P**ython

With no required dependencies and only 496 LOC (`cloc ./msup`), this library enables you to:
- create a CLI application from nested dataclass definitions (see [example](#example) below)
- serialize/deserialize dataclasses or regular python classes to/from json and python dictionaries without dependencies

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
    - basic primitives: float, str, int,
    - optionals
    - unions if there is no ambiguity
    - nested dataclasses
    - callables defined as a string
    - sub-objects can be loaded from a string representing a:
      - JSON, e.g. `'{"x": 3, "name": "abc"}'`
      - a file to JSON, e.g. `myfile.json`
      - TODO: in a future version, hooks will be added to the library to support other serialization formats such as JSON or YAML
- other python classes with `__init__`, e.g. `torch.optim.Adam` (see [examples/pt_basic.py](./examples/pt_basic.py))

# TODOs

- [ ] parameter sweep example
- [ ] hooks to support other serialization formats, e.g. YAML
- [ ] basic SQLite ORM, supporting:
    - schema generation with support to mark fields as a PK, FK and an index
    - encode/decode from SQLite
- [ ] dataclass serialization
    - [ ] renaming fields
    - [ ] enum
    - [ ] union tests (aside from Optional)
- [ ] CI tests
    - [ ] iterate over all examples/tests and run them

## examples

- simple CLI: [examples/simple.py](./examples/simple.py)
- multiple CLI commands with nested config (see below): [examples/mutlicli.py](./examples/multicli.py)
- create a pytorch model and optimizer from config: [examples/pt_dummpy.py](./examples/pt_basic.py) 
    - This example constructs python classes, such as a `torch.optim.Adam`, or a user provided optimizer class, e.g.
        ```bash
        python examples/pt_basic.py test_optim_advanced --lr 0.42 --optim torch.optim.SGD
        ```

The following demonstrates automatically creating a multi-command CLI serializing a dataclass to JSON, you can find this example in [examples/mutlicli.py](./examples/multicli.py). 
```python
import os
from dataclasses import dataclass
from typing import Callable
from msup.cli import cli, cliarg, to_json

@dataclass
class ModelConfig:
    n_layers: int = cliarg(help="number of layers for the model", default=10)
    checkpoint_path: str | None = cliarg(short="-chkpt", help="path of the checkpoint", default=None)

def cosine_warmup_lr_step(i: int, base_lr: float): ...
@dataclass
class TrainArgs:
    model_config: ModelConfig = cliarg(default_factory=lambda: ModelConfig)
    lr: float = 0.01
    name: str = cliarg(help="name of experiment", default="example")
    lr_step_fn: Callable[[int, float], float] = cliarg(help="", default=cosine_warmup_lr_step)
    num_workers: int = -1
    cont: bool = cliarg(help="continue training from last known iter?", default=False)
    config_root_dir: str = cliarg(help="root directory where configuration is serialized to", default="./configs")

@dataclass
class EvalArgs:
    model_config: ModelConfig = cliarg(default_factory=lambda: ModelConfig)
    num_workers: int = -1
    # ...

def identity_step_fn(i: int, base_lr: float):
    return base_lr

def cosine_warmup_lr_step(i: int, base_lr: float):
    if args.warmup_iter and i < args.warmup_iter:
        return ((i+1) / args.warmup_iter) * base_lr
    else:
        t = torch.tensor((i - args.warmup_iter) / (args.niter - args.warmup_iter))
        t = torch.clamp(t, 0.0, 1.0)
        lr = base_lr * 0.5 * (1 + torch.cos(torch.pi * t))
        return lr

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
python examples/multicli.py train
```

Here's how we can change provide a custom python callable to use a different step function:

```bash
python examples/multicli.py train --lr_step_fn examples.multicli.identity_step_fn --lr 0.1 --name identity

# and now we can re-produce this config via:
python examples/multicli.py train configs/identity.json

# or provide --Args (or --TrainArgs) & optionally override args
python examples/multicli.py train --Args configs/identity.json --lr 0.2
```

We can also read a nested dataclasses from a file (e.g. JSON), or a string representing the encoded format (e.g. JSON), from the CLI, e.g.

```bash
python examples/multicli.py train --model_config configs/models/small.json

# or via a JSON object defined on the CLI
python examples/multicli.py train --model_config '{"n_layers": 1}'
```
