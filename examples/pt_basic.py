#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "msup",
#     "numpy",
#     "torch>=2",
# ]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from dataclasses import dataclass, field
from typing import Annotated, Callable

import torch
import torch.nn as nn
import torch.optim as optim

from msup.base import load_callable, to_kwargs
from msup.cli import CliArg, cli


@dataclass
class ModelConfig:
    dim: Annotated[int, CliArg(help="hidden dim size")] = 128
    n_layers: Annotated[int, CliArg(help="number of layers for the model")] = 10
    checkpoint_path: Annotated[str | None, CliArg(short="-chkpt", help="path of the checkpoint")] = None


@dataclass
class TrainConfig:
    model: Annotated[ModelConfig, CliArg(help="model to use")] = field(default_factory=ModelConfig)
    lr: float = 0.1  # NOTE: not realistic, for demonstration


@dataclass
class TrainConfigAdvanced:
    model: Annotated[ModelConfig, CliArg(help="model to use")] = field(default_factory=ModelConfig)
    lr: float = 0.1  # NOTE: not realistic, for demonstration
    optim: Callable = torch.optim.SGD


@dataclass
class TrainConfigAdvancedAlt:
    model: Annotated[ModelConfig, CliArg(help="model to use")] = field(default_factory=ModelConfig)
    lr: float = 0.1  # NOTE: not realistic, for demonstration
    optim: str = "SGD"


class MyModel(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.layers = nn.ModuleList([nn.Linear(config.dim, config.dim), nn.ReLU(True)] * config.n_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for layer in self.layers:
            x = layer(x) + x
        return x


class MyModelKwargs(nn.Module):
    def __init__(self, n_layers: int, dim: int):
        super().__init__()
        self.dim = dim
        self.n_layers = n_layers
        self.layers = nn.ModuleList([nn.Linear(dim, dim), nn.ReLU(True)] * n_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for layer in self.layers:
            x = layer(x) + x
        return x


def test_optim(config: TrainConfig):
    model = MyModel(config.model)
    optimizer = optim.Adam(model.parameters(), **to_kwargs(optim.Adam, config))
    assert optimizer.state_dict()["param_groups"][0]["lr"] == config.lr
    print(optimizer)


def test_optim_advanced(config: TrainConfigAdvanced):
    model = MyModel(config.model)
    optimizer = config.optim(model.parameters(), **to_kwargs(config.optim, config))
    assert optimizer.state_dict()["param_groups"][0]["lr"] == config.lr
    print(optimizer)


def test_optim_advanced_alt(config: TrainConfigAdvancedAlt):
    model = MyModel(config.model)
    optim_class = load_callable("torch.optim." + config.optim)
    optimizer = optim_class(model.parameters(), **to_kwargs(optim_class, config))
    assert optimizer.state_dict()["param_groups"][0]["lr"] == config.lr
    print(optimizer)


def test_model(config: ModelConfig):
    model = MyModelKwargs(**to_kwargs(MyModelKwargs, config))
    model_config = MyModel(config)
    assert model_config.config.dim == model.dim
    assert model_config.config.n_layers == model.n_layers
    assert len(model_config.layers) == len(model.layers)
    print(model)


if __name__ == "__main__":
    cli(
        {
            test_model: "constructs a MyModel & MyModelKwargs via to_kwargs and confirms they are constructed in the same manner",
            test_optim: "constructs an optimizer and prints it",
            test_optim_advanced: "constructs an optimizer (via callable) and prints it",
            test_optim_advanced_alt: "constructs an optimizer (by string) and prints it",
        }
    )
