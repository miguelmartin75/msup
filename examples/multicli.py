#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

import os
from dataclasses import dataclass, field
from typing import Annotated, Callable

from examples.cli.callbacks import cosine_warmup_lr_step
from msup.cli import CliArg, cli, to_json


@dataclass
class ModelConfig:
    n_layers: Annotated[int, CliArg(help="number of layers for the model")] = 10
    checkpoint_path: Annotated[str | None, CliArg(short="-chkpt", help="path of the checkpoint")] = None


@dataclass
class TrainArgs:
    model_config: Annotated[ModelConfig, CliArg(short=None)] = field(default_factory=ModelConfig)
    lr: float = 0.01
    name: Annotated[str, CliArg(help="name of experiment")] = "example"
    lr_step_fn: Annotated[Callable[[int, float], float], CliArg(help="learning-rate step function")] = (
        cosine_warmup_lr_step
    )
    num_workers: int = -1
    cont: Annotated[bool, CliArg(help="continue training from last known iter?")] = False
    config_root_dir: Annotated[str, CliArg(help="root directory where configuration is serialized to")] = "./configs"


@dataclass
class EvalArgs:
    model_config: Annotated[ModelConfig, CliArg(short=None)] = field(default_factory=ModelConfig)
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
    cli(
        {
            train: "train a model",
            eval: "evaluate a trained model",
        }
    )
