#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "../..", editable = true }
# ///

from msup.cli import cli


def train(name: str):
    print(name)


def evaluate(name: str):
    print(name)


if __name__ == "__main__":
    cli({train: "train a model", evaluate: "evaluate a model"})
