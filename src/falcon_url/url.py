import html
from typing import Final, Iterable, Sequence
from urllib.parse import quote, urlencode

QArg = str | bool | int | float | Iterable[str | bool | int | float]


def _tostr(v: str | bool | int | float):  # noqa: FBT001
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v)


def _make_qs(args: Iterable[tuple[str, QArg | None]]):
    query: list[tuple[str, str]] = []

    for k, v in args:
        if v is None:
            continue

        if isinstance(v, (str, int, float)):
            query.append((k, _tostr(v)))
        else:
            if all(isinstance(elt, str | int | float) for elt in v):
                query.extend([(k, _tostr(elt)) for elt in v])

    return query


class Url:
    """Immutable object representing URL. Manipulating URL components produces another URLs.
    The division operator is overloaded to allow composing URL ala pathlib.Path:
    ```
    Url("") / "foo" / "bar"
    ```
    """

    __slots__ = ("_frag", "_loc", "_query", "_root", "_segments")

    def __init__(
        self,
        root: str | None,
        *segments: str,
        location: str | None = None,
        query: Sequence[tuple[str, str]] | None = None,
        fragment: str | None = None,
    ):
        self._root: Final = root
        self._loc: Final = location
        self._segments: Final = segments
        self._query: Final = query
        self._frag: Final = fragment

    # cache ?
    def as_str(self):
        """Render as quoted (percent-encoded) string"""
        segments = self._segments
        if self._root is not None:
            segments = [self._root, *segments]
        url = "/".join(segments)
        url = quote(url)
        if self._loc:
            url = self._loc + url

        if self._query:
            qs = urlencode(self._query, doseq=True)
            if qs:
                url += f"?{qs}"
        if self._frag is not None:
            url += f"#{quote(self._frag)}"
        return url

    def __getitem__(self, index_or_slice: int | slice):
        segments = self._segments[index_or_slice]
        if not isinstance(segments, tuple):
            segments = (segments,)
        return Url(
            self._root,
            *segments,
            location=self._loc,
            query=self._query,
            fragment=self._frag,
        )

    def __bytes__(self):
        return self.as_str().encode("ascii")

    def __truediv__(self, right: str):
        return Url(
            self._root,
            *self._segments,
            right,
            location=self._loc,
            query=self._query,
            fragment=self._frag,
        )

    def __rtruediv__(self, left: str):
        return Url(
            self._root,
            left,
            *self._segments,
            location=self._loc,
            query=self._query,
            fragment=self._frag,
        )

    # hash is inprecise, since query key-values are hashed as is without processing.
    # But good enough for practical purposes, that is objects with same hash should compare equal
    def __hash__(self):
        return hash((self._loc, self._root, self._segments, self._query, self._frag))

    def __eq__(self, other: object):
        if not isinstance(other, Url):
            return NotImplemented
        if other is self:
            return True
        return self.as_str() == other.as_str()

    def __html__(self):
        """Render as HTML-safe string for direct inclusion in markup"""
        return html.escape(self.as_str())

    def with_location(self, location: str):
        """Make new URL with the location changed. Location is schema, netloc and port (
        for example, "http://www.example.com"). Location is NOT quoted"""
        return Url(
            self._root,
            *self._segments,
            location=location,
            query=self._query,
            fragment=self._frag,
        )

    def with_query(self, **keyvals: QArg | None):
        """Make new URL with the query part changed. Keyvals are key:value mapping,
        for example
        ```
        foo="bar", boo=2, zoo=None, more=[1,2,3,4]
        ```
        None values are ignored. Iterables are encoded as repeated key-value pairs:
        ```
        more=1&more=2&more=3&more=4
        ```
        """
        qs = _make_qs(keyvals.items())
        return Url(
            self._root,
            *self._segments,
            location=self._loc,
            query=qs,
            fragment=self._frag,
        )

    def with_fragment(self, fragment: str):
        """Make new URL with the fragment (aka #hash) changed. Fragment should not include #,
        it would be added automatically."""
        return Url(
            self._root,
            *self._segments,
            location=self._loc,
            query=self._query,
            fragment=fragment,
        )

    def with_root(self, root: str):
        """Make new URL with the root prefix changed. Root prefix may contain slashes.
        This is intended for rebasing URL to the different subpath via WSGI SCRIPT_NAME.
        """
        return Url(
            root,
            *self._segments,
            location=self._loc,
            query=self._query,
            fragment=self._frag,
        )

    __str__ = as_str
