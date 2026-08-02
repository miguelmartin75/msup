#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.12"
# dependencies = ["msup"]
#
# [tool.uv.sources]
# msup = { path = "../..", editable = true }
# ///

from msup.base import from_dict, to_dict, to_json, to_kwargs


class Optimizer:
    def __init__(self, lr: float, steps: int = 1):
        self.lr = lr
        self.steps = steps


optimizer = from_dict(Optimizer, {"lr": 0.1})
payload = to_dict(optimizer)
json_text = to_json(optimizer)
kwargs = to_kwargs(Optimizer, optimizer)

print(json_text)
