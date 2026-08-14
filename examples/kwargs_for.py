#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "..", editable = true }
# ///

from dataclasses import dataclass, field
from typing import Annotated, Any, Callable

from msup.base import Kwargs, from_dict, from_json, from_kwargs, kwargs_from_dict, to_json
from msup.cli import CliArg, cli


calls = 0


@dataclass
class Limits:
    memory_gb: int = 4


def launch(workers: int, limits: Limits, label: str = "target-default") -> str:
    global calls
    calls += 1
    return f"launch {calls=}: {workers=}, {limits.memory_gb=}, {label=}"


@dataclass
class Job:
    target: Callable[..., Any] = launch
    kwargs: Annotated[
        Kwargs,
        CliArg(kwargs_for="target", help="arguments for the selected target"),
    ] = field(default_factory=lambda: {"label": "factory"})


def convert() -> None:
    payload = {
        "target": "examples.kwargs_for.launch",
        "kwargs": {"workers": "2", "limits": {"memory_gb": "8"}},
    }
    job = from_dict(Job, payload)
    json_text = to_json(job)
    round_trip = from_json(Job, json_text)
    print(json_text)
    print(f"{round_trip.kwargs=}")
    print(f"{calls=}")

    prepared = kwargs_from_dict(launch, payload["kwargs"])
    launch_later = from_kwargs(launch, prepared)
    assert calls == 0
    print(f"before explicit function call: {calls=}")
    print(launch_later())
    print(f"after explicit function call: {calls=}")


def run(job: Job) -> None:
    print(f"before target call: {calls=}")
    print(job.target(**job.kwargs))
    print(f"after target call: {calls=}")


if __name__ == "__main__":
    cli(
        {
            convert: "convert Job values without invoking its target",
            run: "construct a Job and explicitly invoke its selected target",
        }
    )
