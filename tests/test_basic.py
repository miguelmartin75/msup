import io
import json
from dataclasses import dataclass
from typing import Callable, Dict, Union

from msup.base import _from_value, _is_compat, dict_from_str, from_dict, from_json, to_dict, to_json, to_kwargs
from msup.cli import ex_default_callable

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


@dataclass
class OptionalCallableHolder:
    x: Callable | None = None


@dataclass
class MixedUnionHolder:
    x: Foo | int


class VarArgBaz:
    def __init__(self, name: str, *args, enabled: bool = False, **kwargs):
        self.name = name
        self.enabled = enabled

def test_is_compat_for_supported_types():
    assert _is_compat(int, int)[0]
    assert _is_compat(bool, int)[0]
    assert _is_compat(dict, Dict[int, int])[0]
    assert _is_compat(Foobar, dict)[0]
    assert _is_compat(Foobar | None, dict)[0]
    assert _is_compat(Union[int, None], int)[0]
    assert _is_compat(Union[int, None], type(None))[0]
    assert _is_compat(Callable | None, str)[0]


def test_dataclass_round_trip():
    f = Foobar(dd=dict(), foo=Foo(a=3, b=5), bar=Bar(x=[1.5]), z=None)
    assert from_dict(Foobar, to_dict(f)) == f
    assert from_dict(Foo, {"a": 1, "b": 5}) == Foo(a=1, b=5)


def test_from_dict_supports_regular_python_classes():
    baz = from_dict(Baz, {"name": "ok", "count": None, "meta": {"k": 1}})
    assert isinstance(baz, Baz)
    assert baz.name == "ok"
    assert baz.count is None
    assert baz.meta == {"k": 1}


def test_optional_callable_round_trip():
    holder = OptionalCallableHolder(x=ex_default_callable)

    payload = to_dict(holder)
    assert payload == {"x": "msup.cli.ex_default_callable"}
    assert from_dict(OptionalCallableHolder, payload).x is ex_default_callable
    assert from_dict(OptionalCallableHolder, {"x": None}).x is None


def test_general_union_round_trip_uses_matching_branch():
    foo_holder = MixedUnionHolder(x=Foo(a=1, b=2))
    int_holder = MixedUnionHolder(x=7)

    assert to_dict(foo_holder) == {"x": {"a": 1, "b": 2}}
    assert to_dict(int_holder) == {"x": 7}
    assert from_dict(MixedUnionHolder, {"x": {"a": 1, "b": 2}}) == foo_holder
    assert from_dict(MixedUnionHolder, {"x": 7}) == int_holder


def test_json_helpers_support_string_file_like_and_path(tmp_path):
    payload = Foobar(dd={"k": 1}, primitive=5, foo=Foo(a=2, b=4), bar=Bar(x=[1.5, 2.5]))

    serialized = to_json(payload, indent=None)
    assert from_json(Foobar, s=serialized) == payload

    buffer = io.StringIO()
    to_json(payload, file_like=buffer, indent=None)
    buffer.seek(0)
    assert from_json(Foobar, file_like=buffer) == payload

    path = tmp_path / "payload.json"
    to_json(payload, file_like=str(path), indent=None)
    assert from_json(Foobar, path=str(path)) == payload


def test_dict_from_str_accepts_inline_json_and_paths(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({"x": 3}), encoding="utf-8")

    assert dict_from_str('{"x": 3}') == {"x": 3}
    assert dict_from_str(str(path)) == {"x": 3}


def test_to_dict_accepts_callable_strings_too():
    holder = OptionalCallableHolder(x="msup.cli.ex_default_callable")

    assert to_dict(holder) == {"x": "msup.cli.ex_default_callable"}


def test_to_kwargs_handles_dicts_and_vararg_classes():
    assert to_kwargs(Foo, {"a": 1, "b": 2, "ignored": 3}) == {"a": 1, "b": 2}

    baz = from_dict(VarArgBaz, {"name": "ok", "enabled": True})
    assert isinstance(baz, VarArgBaz)
    assert baz.name == "ok"
    assert baz.enabled is True


def test_union_helpers_report_ambiguous_and_invalid_cases():
    try:
        _is_compat(int | float, int)
    except AssertionError as exc:
        assert "multiple matching types" in str(exc)
    else:
        assert False, "expected ambiguous primitive union to raise"

    assert _is_compat(Foo | dict[str, int], float) == (False, None)

    try:
        dict_from_str("not-json")
    except AssertionError as exc:
        assert "unexpected str" in str(exc)
    else:
        assert False, "expected invalid dict string to raise"


def test_from_value_handles_dataclass_instances_and_rejects_invalid_types():
    foo = Foo(a=5, b=6)

    assert _from_value(foo, Foo, Foo, "foo") == foo

    try:
        _from_value(3, Foo, int, "foo")
    except AssertionError as exc:
        assert "cannot be converted" in str(exc)
        return

    assert False, "expected invalid dataclass conversion to raise"
