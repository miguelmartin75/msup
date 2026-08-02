#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "../..", editable = true }
# ///

from dataclasses import dataclass, field

from msup.cli import cli


@dataclass
class Optimizer:
    lr: float = 0.1


@dataclass
class Train:
    optimizer: Optimizer = field(default_factory=Optimizer)


def train(args: Train):
    print(args)


if __name__ == "__main__":
    cli(train)
