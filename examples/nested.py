from dataclasses import dataclass

from typing import Callable

from msup.cli import cli, cliarg



@dataclass
class DatasetConfig:
    target: Callable = cliarg(help="dataset class path", default=None)
    name: str | None = cliarg(help="name of dataset", default=None)


@dataclass
class DataloaderConfig:
    dataset: DatasetConfig = cliarg(help="dataset", default_factory=DatasetConfig)

@dataclass
class TrainConfig:
    train_data: DataloaderConfig = cliarg(help="train dset", default_factory=DataloaderConfig)
    val_data: DataloaderConfig = cliarg(help="train dset", default_factory=DataloaderConfig)

def train(config: TrainConfig):
    print(config)

if __name__ == "__main__":
    cli(train)

