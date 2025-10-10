from dataclasses import dataclass

from msup.cli import cli, cliarg


@dataclass
class Nested:
    lr: float
    name: str = cliarg("a name", default="test")

@dataclass
class FooArgs:
    nest: Nested = cliarg("some additional params", short="-n")
    x: int = cliarg("assign an x")
    y: float = 20

@dataclass
class BarArgs:
    out_f: str

def foo(args: FooArgs):
    print(f"foo: {args=}")

def bar(args: BarArgs):
    print(f"bar: {args=}")

if __name__ == "__main__":
    # cli(foo)

    cli({
        foo: "run foo",
        bar: "bar",
    })
