# *m*icro *s*erialization *u*tilities for *p*ython

With no required dependencies and only 500 LOC, you can:
- create a CLI application from nested dataclass defintions (see [example](#example) below)
- serialize/deserialize dataclasses to/from json and python dictionaries without pydantic

Yes, the small LOC is a feature.

Serialization/de-serialization of dataclasses supports:
- validating types
- basic primitives: float, str, int,
- optionals
- unions if there is no ambiguty in type-checking
- nested dataclasses
- callables defined as a string
- sub-objects can be loaded from a string representing a:
  - JSON, e.g. `'{"x": 3, "name": "abc"}'`
  - a file to JSON or yaml, e.g. `myfile.json` or `myfile.yaml`
  - python code (if `safe=False`), e.g. `Foobar(x=3, name="abc")`
- Features that are TODOs:
    - [ ] tuples
    - [ ] enum
    - [ ] python modules
    - [ ] renaming fields

This library is designed with the following design philosophies:
- simplicity
- minimilism
    In <500 LOC and no required dependencies (outside of stdlib), you can:
- no dependencies by default (opt-in dependencies)
- opinionated to reduce boilerplate

## example

The following demonstrates automatically creating a multi-command CLI serializing a dataclass to JSON, you can find this example in [examples/mutlicli.py](./examples/multicli.py):
```python
from dataclasses import dataclass
from msup import cli, cliarg, to_json

@dataclass
class ModelConfig:
  n_layers: int = cliarg(help="number of layers for the model", default=10)
  checkpoint_path: str | None = cliarg(short="-chkpt", help="path of the checkpoint", default=None)

@dataclass
class TrainArgs:
   lr: float = 0.01
   name: str = cliarg(help="name of experiment", default="example")
   lr_step_fn: Callable[[int, float], float] = cliarg(help="", default=)
   model_config: ModelConfig = ModelConfig()
   num_workers: int = -1
   cont: bool = cliarg(help="continue training from last known iter?", default=False)
   config_root_dir: str = cliarg(help="root directory where configuration is serialized to", default="./configs")

@dataclass
class EvalArgs:
   model_config: ModelConfig = ModelConfig()
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
    print("train:\n", args)
    os.makedirs(args.config_root_dir, exist_ok=True)
    config_out_path = os.path.join(args.config_root_dir, args.name)

    print(f"\nwriting config to: {config_out_path}")
    to_json(args, config_out_path)

def eval(args: EvalArgs):
    print("eval:\n", args)

if __name__ == "__main__":
   cli({
     train: "train a model,
     eval: "evaluate a trained model",
   })
```

Now you can go ahead and run the train or eval function via `python <script> {train,eval} [optional-args...]`, e.g.:
```bash
python examples/multicli.py train
```

Here's how to incorporate a python callable, incase you want to train with a different step function:

```bash
python examples/multicli.py train --lr_step_fn examples.multicli.identity_step_fn --lr 0.1 --name identity

# and now we can re-produce this config via:
python examples/multicli.py train configs/identity.json

# & optionally override configs
python examples/multicli.py train configs/identity.json --lr 0.2
```

You can also read in nested dataclasses from a file (JSON), a JSON string, or python code directly from the CLI, e.g.
```bash
python examples/multicli.py train --model configs/models/small.json
# or via a JSON object defined on the CLI
python examples/multicli.py train --model '{"n_layers": 1}'
# or via a python object defined on the CLI (TODO: confirm)
python examples/multicli.py train --model 'ModelConfig(n_layers=123)'
```
