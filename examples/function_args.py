#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from msup.base import to_json
from msup.cli import cli


def greet(name: str, count: int = 1):
    print(to_json(locals(), type_class=greet))


if __name__ == "__main__":
    cli(greet)
