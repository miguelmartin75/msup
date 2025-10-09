import src.sdc

assert _is_compat(int, int)[0]
assert not _is_compat(bool, int)[0]
assert _is_compat(dict, Dict[int, int])[0]
assert _is_compat(Foobar, dict)[0]
assert _is_compat(Foobar | None, dict)[0]
assert _is_compat(Union[int, None], int)[0]
assert _is_compat(Union[int, None], type(None))[0]

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

f = Foobar(dd=dict(), foo=Foo(a=3, b=5), bar=Bar(x=[1.5]), z=None)
assert from_dict(Foobar, to_dict(f)) == f
assert from_dict(Foo, '{"a": 1, "b": 5}') == Foo(a=1, b=5)

