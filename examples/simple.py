from dataclasses import dataclass
from typing import Annotated

from msup.cli import CliArg, cli


@dataclass
class Nested:
    lr: float
    name: Annotated[str, CliArg(help="a name")] = "test"


@dataclass
class FooArgs:
    nest: Annotated[Nested, CliArg(help="some additional params", short="-n")]
    x: Annotated[int, CliArg(help="assign an x")]
    y: float = 20


@dataclass
class BarArgs:
    out_f: str


def foo(args: FooArgs):
    print(f"foo: {args=}")


def bar(args: BarArgs):
    print(f"bar: {args=}")


if __name__ == "__main__":
    cli(
        {
            foo: "run foo",
            bar: "run bar",
        }
    )
