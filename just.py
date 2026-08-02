#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = ".", editable = true }
# ///

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from msup.cli import CliArg, cli


repo_root = Path(__file__).parent


def run(cmd: Sequence[str] | str) -> None:
    args = shlex.split(cmd) if isinstance(cmd, str) else cmd
    result = subprocess.run(args, cwd=repo_root)
    if result.returncode:
        raise SystemExit(result.returncode)


def setup_dev() -> None:
    run("uv sync --group dev")


def test() -> None:
    run("uv run --group dev --extra pydantic pytest")


def coverage() -> None:
    run("uv run --group dev --extra pydantic pytest --cov=msup --cov-report=term-missing")


def no_extra_import() -> None:
    run('uv run --no-default-groups --no-extra pydantic -- python -c "import msup.base; import msup.cli"')


def examples() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        run("./examples/simple.py --help")
        run("./examples/simple.py foo --help")
        run("./examples/simple.py foo --nest '{\"lr\": 0.1}' --x 1")
        run("./examples/simple.py bar --help")
        run(["./examples/simple.py", "bar", "--out_f", str(temp_path / "bar.txt")])
        run("./examples/nested.py --help")
        run("./examples/nested.py --train_data.dataset.name training --val_data.dataset.name validation")
        run("./examples/multicli.py --help")
        run("./examples/multicli.py train --help")
        run(["./examples/multicli.py", "train", "--config_root_dir", temp_dir, "--name", "train"])
        run("./examples/multicli.py eval --help")
        run("./examples/multicli.py eval")
        run("./examples/pt_basic.py --help")
        run("./examples/pt_basic.py test_model --help")
        run("./examples/pt_basic.py test_model --dim 4 --n_layers 1")
        run("./examples/pt_basic.py test_optim --help")
        run("./examples/pt_basic.py test_optim --model.dim 4 --model.n_layers 1")
        run("./examples/pt_basic.py test_optim_advanced --help")
        run("./examples/pt_basic.py test_optim_advanced --model.dim 4 --model.n_layers 1")
        run("./examples/pt_basic.py test_optim_advanced_alt --help")
        run("./examples/pt_basic.py test_optim_advanced_alt --model.dim 4 --model.n_layers 1")
        run("./examples/pydantic_basic.py --help")
        run("./examples/pydantic_basic.py --name integration --values 1 2")
        run("./examples/function_args.py --help")
        run("./examples/function_args.py show --name integration --count 2")
        run("./examples/function_args.py echo --name integration --count 2")
        run("./examples/readme/train.py --optimizer.lr 0.01")
        run("./examples/readme/subcommands.py train --name integration")
        run("./examples/readme/regular_class.py")
        run("./examples/remainder.py --cwd build --retries 2 run --target staging --verbose")


def lint() -> None:
    run("uv run --group dev ruff check .")


def type() -> None:
    run("uv run --group dev ty check .")


def check() -> None:
    lint()


def tag_release(version: Annotated[str, CliArg(pos=True, opt=False)]) -> None:
    if not version:
        raise SystemExit(1)
    run(["uv", "version", version, "--frozen"])
    run("git add pyproject.toml uv.lock")
    run(["git", "commit", "-m", f"Release {version}"])
    run(["git", "tag", "-a", f"v{version}", "-m", f"Release {version}"])
    run("git push origin HEAD")
    run(["git", "push", "origin", f"v{version}"])


def publish_release() -> None:
    dist = repo_root / "dist"
    if dist.is_symlink() or dist.is_file():
        dist.unlink()
    elif dist.exists():
        shutil.rmtree(dist)
    run(["uv", "build", "--out-dir", str(dist)])
    run(
        [
            "uv",
            "run",
            "--group",
            "dev",
            "python",
            "-m",
            "twine",
            "upload",
            *[str(path) for path in dist.glob("*")],
        ]
    )


if __name__ == "__main__":
    cli(
        {
            setup_dev: "install development dependencies",
            test: "run the test suite",
            coverage: "run the test suite with coverage",
            no_extra_import: "verify the base install imports without optional dependencies",
            examples: "run every executable example",
            lint: "lint the repository",
            type: "type check the repository",
            check: "run the lint check",
            tag_release: "create and push a release tag",
            publish_release: "build and publish a release",
        },
        description="Project task runner and justfile replacement.",
    )
