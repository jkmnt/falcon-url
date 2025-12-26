from __future__ import annotations

from typing import Any, Callable, ClassVar, Final, Mapping, Self

from .url import Url

_KNOWN_PARAMS: dict[str | type, type[RouteParam]] = {}


class RouteParam:
    """Represents (dynamic) parameter in route"""

    __slots__ = ("id",)

    _type_id: ClassVar[str]
    _anno: ClassVar[type]
    _is_multisegment: ClassVar[bool]

    def __init__(self, id: str):
        self.id: Final = id

    def interpolate(self, val: Any) -> str:
        raise NotImplementedError()

    def get_cfg(self) -> list[str | None]:
        return []

    def __str__(self):
        params = ", ".join(param for param in self.get_cfg() if param is not None)
        if not params:
            return f"{{{self.id}:{self._type_id}}}"
        return f"{{{self.id}:{self._type_id}({params})}}"

    def __add__(
        self,
        right: str | RouteParamSpec | RouteSegment | tuple[str | RouteParamSpec, ...],
    ):
        return RouteSegment(self, *RouteSegment.from_parts(right))

    def __radd__(
        self,
        left: str | RouteParamSpec | RouteSegment | tuple[str | RouteParamSpec, ...],
    ):
        return RouteSegment(*RouteSegment.from_parts(left), self)

    def __init_subclass__(
        cls,
        *,
        id: str,
        anno: type,
        shortcut: type | None = None,
        is_multisegment: bool = False,
    ):
        cls._type_id = id
        cls._anno = anno
        cls._is_multisegment = is_multisegment

        _KNOWN_PARAMS[id] = cls
        if shortcut is not None:
            _KNOWN_PARAMS[shortcut] = cls


class Route:
    """Immutable route template. Route consist of segments with static and dynamic parts.
    The division operator is overloaded to allow composing ala pathlib.Path:
    ```
    Route("") / "foo" / "bar" / param.Int("thing") / param.Str("user") / ""
    ```
    """

    __slots__ = ("segments",)

    def __init__(self, *segments: str | RouteSegment):
        self.segments = tuple(
            seg if isinstance(seg, RouteSegment) else RouteSegment(seg)
            for seg in segments
        )

    def __str__(self):
        return "/".join([str(seg) for seg in self.segments])

    def __iter__(self):
        yield from self.segments

    def __truediv__(
        self,
        right: str | RouteSegment | RouteParamSpec | tuple[str | RouteParamSpec, ...],
    ):
        return Route(*self.segments, RouteSegment.from_parts(right))

    def __rtruediv__(
        self,
        left: str | RouteSegment | RouteParamSpec | tuple[str | RouteParamSpec, ...],
    ):
        return Route(RouteSegment.from_parts(left), *self.segments)

    def _get_params(self):
        return [part for seg in self.segments for part in seg._get_params()]

    def __getitem__(self, index_or_slice: int | slice):
        segments = self.segments[index_or_slice]
        if not isinstance(segments, tuple):
            segments = (segments,)
        return Route(*segments)

    def as_url(self, **params: Any):
        """Resolve route to the URL substituting parameters from the provided keyword arguments"""
        segments: list[str] = []

        for seg in self.segments:
            seg_parts: list[str] = []
            for part in seg.parts:
                if isinstance(part, str):
                    seg_parts.append(part)
                else:
                    param = params.pop(part.id)
                    seg_parts.append(part.interpolate(param))
            segments.append("".join(seg_parts))

        return Url(*segments)

    @classmethod
    def root(cls):
        return cls("")


class BoundRoute[**P]:
    """Holds the route with the concrete type-aware parameters and optional root_path prefix (subdirectory).
    Resolves the route to the concrete URL on call:
    ```
    me(foo="bar", baz=3) -> Url
    ```

    May be used as a class attribute descriptor to infer `root_path` from that class instance.
    Then all routes would have an automatically defined `root_path`.
    """

    __slots__ = ("root_path", "route")

    def __init__(self, route: Route, *, root_path: str | None = None):
        self.route: Final = route
        self.root_path: Final = root_path or ""

    def resolve(self, *args: P.args, **kwargs: P.kwargs) -> Url:
        return self.route.as_url(**kwargs).with_root(self.root_path)

    def __get__(self, obj: object | None, objtype: Any = None) -> BoundRoute[P]:
        return type(self)(self.route, root_path=getattr(obj, "root_path", None))

    def __str__(self):
        return str(self.route)

    __call__ = resolve

    @staticmethod
    def from_simple_callable[**Pc](
        route: Route, _func: Callable[P, Any], root_path: str | None = None
    ):
        """Make class with signature borrowed from callable"""
        return BoundRoute[P](route, root_path=root_path)


class RouteSegment:
    """Immutable route segment between slash separators.
    May consist of strings and parameters:
    ```
    RouteSegment("head-', param.Str("op"), "-tail)
    ```
    encodes the `head-{op}-tail` segment with dynamic `op`.

    Such segments could also be created with `+` operation:
    ```
    Route("") / ("head-" + param.Str("op") + "-tail") / "foo"
    ```
    """

    __slots__ = ("parts",)

    def __init__(self, *items: RouteParam | str):
        self.parts: Final = items

    def __str__(self):
        return "".join(str(part) for part in self.parts)

    def __iter__(self):
        yield from self.parts

    def _get_params(self):
        return [part for part in self.parts if isinstance(part, RouteParam)]

    def __add__(
        self,
        right: str | RouteParamSpec | RouteSegment | tuple[str | RouteParamSpec, ...],
    ):
        return RouteSegment(*self, *RouteSegment.from_parts(right))

    def __radd__(
        self,
        left: str | RouteParamSpec | RouteSegment | tuple[str | RouteParamSpec, ...],
    ):
        return RouteSegment(*RouteSegment.from_parts(left), *self)

    @classmethod
    def from_parts(
        cls, spec: str | RouteParamSpec | RouteSegment | tuple[str | RouteParamSpec, ...]
    ):
        if isinstance(spec, (RouteSegment, tuple)):
            items = spec
        else:
            items = (spec,)

        parts: list[str | RouteParam] = []
        for item in items:
            if isinstance(item, (str, RouteParam)):
                part = item
            else:
                if len(item) != 1:
                    raise ValueError("Bad param spec", item)
                if isinstance(item, set):
                    name = list(item)[0]
                    ctor = _KNOWN_PARAMS[str]
                elif isinstance(item, dict):
                    name, v = list(item.items())[0]
                    if isinstance(v, type):
                        if issubclass(v, RouteParam):
                            ctor = v
                        else:
                            ctor = _KNOWN_PARAMS[v]
                    elif isinstance(v, str):
                        ctor = ctor = _KNOWN_PARAMS[v]
                    else:
                        ctor = v
                else:
                    raise TypeError("Unsupported param spec", item)
                part = ctor(name)
            parts.append(part)
        return cls(*parts)


# TODO: add the global loc too ?
class RoutesCollection:
    """Container for the BoundRoutes.
    Instance of the cointainer provides common `root_path` to the routes.
    """

    def __init__(self, *, root_path: str | None = None):
        self.root_path = root_path

    @classmethod
    def desc(cls) -> RouteCollectionDescriptor[Self]:
        """Wraps class with the descriptor, simplifying usage inside another
        RoutesCollection"""
        return RouteCollectionDescriptor(cls)


# TODO: Could we combine RoutesCollection and RouteCollectionDescriptor in a single class ?
# maybe with some overloads ... ?
class RouteCollectionDescriptor[T: RoutesCollection]:
    """Allows using RouteCollection inside another RouteCollection with automatic
    propagation of root_path"""

    __slots__ = ("cls",)

    def __init__(self, cls: type[T]):
        self.cls = cls

    def __get__(self, obj: object | None, objtype: Any = None):
        return self.cls(root_path=getattr(obj, "root_path", None))


RouteParamSpec = (
    RouteParam
    | set[str]
    | Mapping[str, type[RouteParam] | type | str | Callable[[str], RouteParam]]
)
