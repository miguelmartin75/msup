#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from typing import Annotated

from msup.cli import CliArg, cli


def forward(
    command: Annotated[str, CliArg(pos=True)],
    cwd: str = ".",
    retries: int = 1,
    # opt=False makes this final list consume every remaining token.
    remaining: Annotated[list[str] | None, CliArg(pos=True, opt=False)] = None,
):
    print(f"{command=}: {cwd=}: {retries=}: {remaining=}")


if __name__ == "__main__":
    cli(forward)
