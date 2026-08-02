set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

setup-dev:
    uv sync --group dev

test:
    uv run --group dev --extra pydantic pytest

coverage:
    uv run --group dev --extra pydantic pytest --cov=msup --cov-report=term-missing

no-extra-import:
    uv run --no-default-groups --no-extra pydantic -- python -c 'import msup.base; import msup.cli'

examples:
    #!/usr/bin/env bash
    set -euxo pipefail
    temp_dir="$(mktemp -d)"
    trap 'rm -rf "$temp_dir"' EXIT
    ./examples/simple.py --help
    ./examples/simple.py foo --help
    ./examples/simple.py foo --nest '{"lr": 0.1}' --x 1
    ./examples/simple.py bar --help
    ./examples/simple.py bar --out_f "$temp_dir/bar.txt"
    ./examples/nested.py --help
    ./examples/nested.py --train_data.dataset.name training --val_data.dataset.name validation
    ./examples/multicli.py --help
    ./examples/multicli.py train --help
    ./examples/multicli.py train --config_root_dir "$temp_dir" --name train
    ./examples/multicli.py eval --help
    ./examples/multicli.py eval
    ./examples/pt_basic.py --help
    ./examples/pt_basic.py test_model --help
    ./examples/pt_basic.py test_model --dim 4 --n_layers 1
    ./examples/pt_basic.py test_optim --help
    ./examples/pt_basic.py test_optim --model.dim 4 --model.n_layers 1
    ./examples/pt_basic.py test_optim_advanced --help
    ./examples/pt_basic.py test_optim_advanced --model.dim 4 --model.n_layers 1
    ./examples/pt_basic.py test_optim_advanced_alt --help
    ./examples/pt_basic.py test_optim_advanced_alt --model.dim 4 --model.n_layers 1
    ./examples/pydantic_basic.py --help
    ./examples/pydantic_basic.py --name integration --values 1 2
    ./examples/function_args.py --help
    ./examples/function_args.py show --name integration --count 2
    ./examples/function_args.py echo --name integration --count 2
    ./examples/readme/train.py --optimizer.lr 0.01
    ./examples/readme/subcommands.py train --name integration
    ./examples/readme/regular_class.py
    ./examples/remainder.py --cwd build --retries 2 run --target staging --verbose

lint:
    uv run --group dev ruff check .

type:
    uv run --group dev ty check .

check: lint

tag-release version:
    test -n "{{version}}"
    uv version "{{version}}" --frozen
    git add pyproject.toml uv.lock
    git commit -m "Release {{version}}"
    git tag -a "v{{version}}" -m "Release {{version}}"
    git push origin HEAD
    git push origin "v{{version}}"

publish-release:
    rm -rf dist
    uv build --out-dir dist
    uv run --group dev python -m twine upload dist/*
