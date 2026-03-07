import argparse
from dataclasses import dataclass

from msup.cli import _add_args, _from_cli_args, cliarg


@dataclass
class Nested:
    enabled: bool = cliarg(help="nested bool", default=False)
    keep: bool = cliarg(help="nested bool default true", default=True)


@dataclass
class Args:
    nested: Nested = cliarg(help="nested config", default_factory=Nested)


def main():
    parser = argparse.ArgumentParser()
    _add_args(parser, Args)

    parsed = parser.parse_args([])
    args = _from_cli_args(Args, parsed)
    assert args.nested.enabled is False
    assert args.nested.keep is True

    parsed = parser.parse_args(["--nested.enabled", "true", "--nested.keep", "false"])
    args = _from_cli_args(Args, parsed)
    assert args.nested.enabled is True
    assert args.nested.keep is False


if __name__ == "__main__":
    main()
