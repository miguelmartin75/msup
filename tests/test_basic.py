from dataclasses import dataclass
from typing import Dict, Union

from msup.base import _is_compat, from_dict, to_dict

@dataclass
class Foo:
    a: int
    b: int

@dataclass
class Bar:
    x: list[float]
    yy: str = "lol"

@dataclass
class Foobar:
    dd: dict
    primitive: Union[int, None] = 3
    foo: Foo | None = None
    z: Dict[int, int] | None = None
    bar: Bar | None = None

class Baz:
    def __init__(self, name: str, count: int | None = None, meta: Dict[str, int] | None = None):
        self.name = name
        self.count = count
        self.meta = meta

if __name__ == "__main__":
    assert _is_compat(int, int)[0]
    assert _is_compat(bool, int)[0]
    assert _is_compat(dict, Dict[int, int])[0]
    assert _is_compat(Foobar, dict)[0]
    assert _is_compat(Foobar | None, dict)[0]
    assert _is_compat(Union[int, None], int)[0]
    assert _is_compat(Union[int, None], type(None))[0]

    f = Foobar(dd=dict(), foo=Foo(a=3, b=5), bar=Bar(x=[1.5]), z=None)
    assert from_dict(Foobar, to_dict(f)) == f
    assert from_dict(Foo, {"a": 1, "b": 5}) == Foo(a=1, b=5)

    baz = from_dict(Baz, {"name": "ok", "count": None, "meta": {"k": 1}})
    assert isinstance(baz, Baz)
    assert baz.name == "ok"
    assert baz.count is None
    assert baz.meta == {"k": 1}
