set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

setup-dev:
    uv sync --group dev

test:
    uv run --group dev pytest

coverage:
    uv run --group dev pytest --cov=msup --cov-report=term-missing

tag-release version:
    test -n "{{version}}"
    test -z "$(git status --porcelain)"
    uv version "{{version}}" --frozen
    git add pyproject.toml
    git commit -m "Release {{version}}"
    git tag -a "v{{version}}" -m "Release {{version}}"
    git push origin HEAD
    git push origin "v{{version}}"

publish-release:
    rm -rf dist
    uv build --out-dir dist
    uv run --group dev python -m twine upload dist/*
