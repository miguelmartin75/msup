from dataclasses import dataclass
from typing import Callable

import torch
import torch.nn as nn
import torch.optim as optim

from msup.cli import cli, cliarg
from msup.base import to_kwargs, load_callable


@dataclass
class ModelConfig:
    dim: int = cliarg(help="hidden dim size", default=128)
    n_layers: int = cliarg(help="number of layers for the model", default=10)
    checkpoint_path: str | None = cliarg(short="-chkpt", help="path of the checkpoint", default=None)

@dataclass
class TrainConfig:
    model: ModelConfig = cliarg(help="model to use", default_factory=ModelConfig)
    lr: float = 0.1  # NOTE: not realistic, for testing

@dataclass
class TrainConfigAdvanced:
    model: ModelConfig = cliarg(help="model to use", default_factory=ModelConfig)
    lr: float = 0.1  # NOTE: not realistic, for testing
    optim: Callable = "torch.optim.SGD"

@dataclass
class TrainConfigAdvancedAlt:
    model: ModelConfig = cliarg(help="model to use", default_factory=ModelConfig)
    lr: float = 0.1  # NOTE: not realistic, for testing
    optim: str = "SGD"

class MyModel(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.layers = nn.ModuleList([
            nn.Linear(config.dim, config.dim),
            nn.ReLU(True)
        ] * config.n_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for layer in self.layers:
            x = layer(x) + x
        return x

# the same as above, but with arguments
class MyModelKwargs(nn.Module):
    def __init__(self, n_layers: int, dim: int):
        super().__init__()
        self.dim = dim
        self.n_layers = n_layers
        self.layers = nn.ModuleList([
            nn.Linear(dim, dim),
            nn.ReLU(True)
        ] * n_layers)

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
    cli({
        test_model: "constructs a MyModel & MyModelKwargs via to_kwargs and confirms they are constructed in the same manner",
        test_optim: "constructs an optimizer and prints it",
        test_optim_advanced: "constructs an optimizer (via callable) and prints it",
        test_optim_advanced_alt: "constructs an optimizer (by string) and prints it",
    })
