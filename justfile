set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

setup-dev:
    uv sync --group dev

test:
    uv run --group dev pytest

coverage:
    uv run --group dev pytest --cov=msup --cov-report=term-missing

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
