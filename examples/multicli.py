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
