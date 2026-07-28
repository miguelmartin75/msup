#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from dataclasses import dataclass, field
from typing import Annotated, Callable

from msup.cli import CliArg, cli


@dataclass
class DatasetConfig:
    target: Annotated[Callable, CliArg(help="dataset class path")] = None
    name: Annotated[str | None, CliArg(help="name of dataset")] = None


@dataclass
class DataloaderConfig:
    dataset: Annotated[DatasetConfig, CliArg(help="dataset")] = field(default_factory=DatasetConfig)


@dataclass
class TrainConfig:
    train_data: Annotated[DataloaderConfig, CliArg(help="train dset")] = field(default_factory=DataloaderConfig)
    val_data: Annotated[DataloaderConfig, CliArg(help="train dset")] = field(default_factory=DataloaderConfig)


def train(config: TrainConfig):
    print(config)


if __name__ == "__main__":
    cli(train)
