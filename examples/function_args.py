#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from typing import Annotated
from msup.base import to_json
from msup.cli import cli, CliArg

def show(name: Annotated[str, CliArg(short="n", help="your name")], count: int = 1):
    print(to_json(locals(), type_class=show))  # encode the function args to JSON

def echo(name: Annotated[str, CliArg(short="n", help="your name")], count: int = 1):
    print([name] * count)

# creates a CLI interface with sub-commands 'show' and 'echo'
cli({
    show: "show the input arguments as JSON", 
    echo: "echo your name N times", 
})
# or for a single command CLI
# cli(show)
