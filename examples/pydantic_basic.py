#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup[pydantic]"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from typing import Annotated

from pydantic import BaseModel, Field

from msup.cli import CliArg, cli


class Args(BaseModel):
    name: Annotated[str, CliArg(help="name to greet")] = "world"
    values: Annotated[list[int], CliArg(help="values to show", short="v")] = Field(default_factory=lambda: [1, 2])


def greet(args: Args):
    print(f"hello, {args.name}: {args.values}")


if __name__ == "__main__":
    cli(greet)
