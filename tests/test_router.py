# from __future__ import annotations
import pytest
import datetime
from typing import Any
import uuid

from falcon_url import Router, param, Route, RoutesCollection


def test_int():
    assert str(param.Int("foo", min=1, max=10, num_digits=3)) == "{foo:int(3, min=1, max=10)}"

    assert str(param.Int("foo", max=10, num_digits=-1)) == "{foo:int(-1, max=10)}"

    assert str(param.Int("foo", min=1, max=10)) == "{foo:int(min=1, max=10)}"

    assert str(param.Int("foo")) == "{foo:int}"


def test_float():
    assert str(param.Float("foo", min=1, max=10, finite=True)) == "{foo:float(min=1, max=10)}"

    assert str(param.Float("foo", min=1, finite=False)) == "{foo:float(min=1, finite=False)}"

    assert str(param.Float("foo")) == "{foo:float}"

    assert str(param.Float("foo", max=0)) == "{foo:float(max=0)}"


def test_dt():
    assert str(param.Datetime("foo")) == "{foo:dt}"

    assert str(param.Datetime("foo", format_string="%Y")) == '{foo:dt("%Y")}'
    v = param.Datetime("bla")
    now = datetime.datetime.now()
    assert v.interpolate(now) == now.strftime("%Y-%m-%dT%H:%M:%S%z")


def test_route_kitchen():
    route = (
        Route.root()
        / "foo"
        / "bar"
        / param.Str("str1")
        / param.Int("int1")
        / "sep"
        / param.Float("float1")
        / ""
        / param.Uuid("uuid1")
        / ""
    )

    assert str(route) == "/foo/bar/{str1}/{int1:int}/sep/{float1:float}//{uuid1:uuid}/"
    uuid1 = uuid.uuid4()

    assert str(route.as_url(str1="1", int1=2, float1=3.14, uuid1=uuid1)) == f"/foo/bar/1/2/sep/3.14//{ uuid1 }/"

    assert str(Route("")) == ""

    assert param.Float("a").interpolate(3) == "3.0"


def test_route_escape():
    route = Route("") / "foo,foo" / "bar" / param.Str("str1")
    assert str(route) == "/foo,foo/bar/{str1}"

    assert (
        str(route.as_url(str1="word with spaces and ,,,").with_query(kw=" , ,Я"))
        == r"/foo%2Cfoo/bar/word%20with%20spaces%20and%20%2C%2C%2C?kw=+%2C+%2C%D0%AF"
    )


def test_route_query():
    route = Route("") / "foo" / "bar" / param.Str("str1") / param.Int("int1")
    assert str(route) == "/foo/bar/{str1}/{int1:int}"

    assert (
        str(
            route.as_url(str1="1", int1=12).with_query(k1=True, k3=False, q=333, f="444", b=[1, 2, 3, 4, "bla"], z=None)
        )
        == "/foo/bar/1/12?k1=true&k3=false&q=333&f=444&b=1&b=2&b=3&b=4&b=bla"
    )


def test_route_frag():
    route = Route("") / "foo" / "bar" / param.Str("str1") / param.Int("int1")
    assert str(route) == "/foo/bar/{str1}/{int1:int}"

    assert str(route.as_url(str1="1", int1=12).with_fragment(" 333")) == "/foo/bar/1/12#%20333"

    assert str(route.as_url(str1="1", int1=12).with_fragment("")) == "/foo/bar/1/12#"


def test_partial_segments():
    route = Route("") / ("foo", "bar_", param.Int("why"), ":", param.Uuid("uu"), "-baz") / "bar"

    assert str(route) == "/foobar_{why:int}:{uu:uuid}-baz/bar"

    route = Route("") / ("foo" + "bar_" + param.Int("why") + ":" + param.Uuid("uu") + "-baz") / "bar"

    assert str(route) == "/foobar_{why:int}:{uu:uuid}-baz/bar"


def test_prefix():
    route = Route("") / "foo" / "bar" / param.Str("str1") / param.Int("int1")
    url = route.as_url(str1="1", int1=12)
    assert str(url.as_str()) == "/foo/bar/1/12"
    assert str(url.with_root("/my-app").as_str()) == "/my-app/foo/bar/1/12"
    assert str(url.with_location("http://www.example.com:8000").as_str()) == "http://www.example.com:8000/foo/bar/1/12"
    assert (
        str(url.with_root("/my- app").with_location("http://www.example.com:8000").as_str())
        == r"http://www.example.com:8000/my-%20app/foo/bar/1/12"
    )


def test_route_descriptor():

    class Resource:
        def __init__(self, mount: Route, router: Router):
            class Route(RoutesCollection):
                get = router.add(mount / param.Str("foo"), get=self.on_get)
                post = router.add(mount / "deeper" / param.Int("bar"), GET=self.on_post)

            self.routes = Route

        def on_get(self, req: Any, resp: Any, *, foo: str):
            return None

        def on_post(self, req: Any, resp: Any, *, bar: int):
            return None

    router = Router()
    router.compile()

    res = Resource(Route("") / "base", router)

    assert res.routes.get(foo="1").as_str() == "/base/1"
    assert res.routes.post(bar=1).as_str() == "/base/deeper/1"

    with_req = res.routes(root_path="/app")

    assert with_req.get(foo="1").as_str() == "/app/base/1"
    assert with_req.post(bar=1).as_str() == "/app/base/deeper/1"

    class AllRoutes(RoutesCollection):

        class Deeper(RoutesCollection):
            resource = res.routes.desc()

        deeper = Deeper.desc()

    all_routes = AllRoutes

    assert all_routes.deeper.resource.get(foo="1").as_str() == "/base/1"
    assert all_routes.deeper.resource.post(bar=1).as_str() == "/base/deeper/1"

    all_with_req = all_routes(root_path="/app")

    assert all_with_req.deeper.resource.get(foo="1").as_str() == "/app/base/1"
    assert all_with_req.deeper.resource.post(bar=1).as_str() == "/app/base/deeper/1"


def test_parse_template():

    class Resource:
        def on_get(self, req: Any, resp: Any, *, foo: str):
            return None

        def on_post(self, req: Any, resp: Any, *, bar: int):
            return None

    res = Resource()

    ra = Router()
    rb = Router()

    aget = ra.add(
        Route.root()
        / param.Str("foo")
        / "s"
        / param.Int("bar")
        / param.Float("baz", min=-10.33, max=50.123)
        / param.Int("far", num_digits=+3, max=42)
        / param.Uuid("uu")
        / param.Datetime("dt", format_string="%Y")
        / ("user_" + param.Str("user") + "_id")
        / "",
        GET=res.on_get,
    )

    template = '/{foo}/s/{bar:int}/{baz:float(min=-10.33, max=50.123)}/{far:int(3, max=42)}/{uu:uuid}/{dt:dt("%Y")}/user_{user}_id/'

    bget = rb.add(template, GET=res.on_get)
    assert str(aget) == str(bget)
    assert str(aget) == template


def test_magic():
    route = (
        Route.root()
        / "foo"
        / "bar"
        / {"str1"}
        / {"str2": str}
        / {"int1": int}
        / "sep"
        / {"float1": float}
        / ""
        / ("prefix_", {"uuid1": uuid.UUID}, "_suffix")
        / ""
        / {"dt": datetime.datetime}
        / {"int2": param.Int}
        / {"int3": lambda name: param.Int(name, num_digits=-4)}
        / {"int4": "int"}
        / ("end-", {"tail": param.Path})
    )

    assert (
        str(route)
        == "/foo/bar/{str1}/{str2}/{int1:int}/sep/{float1:float}//prefix_{uuid1:uuid}_suffix//{dt:dt}/{int2:int}/{int3:int(-4)}/{int4:int}/end-{tail:path}"
    )


def test_classic():
    class Resource:
        def on_get(self, req: Any, resp: Any, *, foo: str):
            return None

        def on_get_sfx(self, req: Any, resp: Any, *, foo: str):
            return None

        def on_post(self, req: Any, resp: Any, *, foo: int):
            return None

    router = Router()
    r = Resource()

    classic_route = router.add_route(Route("") / "base" / {"foo"}, r, typical_responder=r.on_get)
    classic_route_sfx = router.add_route(
        Route("") / "maze" / {"foo"}, r, typical_responder=r.on_get_sfx, suffix="sfx"
    )
    new_route = router.add(Route("") / "face" / {"moo"}, GET=r.on_get)

    router.compile()

    classic_route(foo="1")

    res = router.find("/base/abc")
    assert res
    cls, meths, *_ = res
    assert cls == r
    assert meths["GET"] == r.on_get
    assert meths["POST"] == r.on_post

    res = router.find("/maze/abc")
    assert res
    cls, meths, *_ = res
    assert cls == r
    assert meths["GET"] == r.on_get_sfx

    res = router.find("/face/abc")
    assert res
    cls, meths, *_ = res
    assert cls == r
    assert meths["GET"] == r.on_get


# just a few simple tests for validation. surely undertested )
def test_validate():
    def on_get1(req: Any, resp: Any, *, foo: str, dt: datetime.datetime):
        return None

    def on_get1_with_mw_injected(req: Any, resp: Any, injected: Any, *, foo: str, dt: datetime.datetime):
        return None

    def on_get_kwargs(req: Any, resp: Any, *, foo: str, dt: datetime.datetime, **kwargs: Any):
        return None

    def on_post1(req: Any, resp: Any, *, foo: int, bla: float):
        return None

    def on_post2(req: Any, resp: Any, *, foo: int, bla: float, rest: str):
        return None

    router = Router(strict=True)
    router.add(Route("") / "base" / {"foo"} / {"dt": datetime.datetime}, POST=on_get1)
    router.add(Route("") / "base" / {"foo"} / {"dt": datetime.datetime}, POST=on_get1_with_mw_injected)
    router.add(Route("") / "base" / {"foo"} / {"dt": datetime.datetime}, POST=on_get_kwargs)
    router.add(Route("") / "face" / {"foo": int} / {"bla": float}, POST=on_post1)
    router.add(Route("") / "face" / {"foo": int} / {"bla": float} / {"rest": param.Path}, POST=on_post2)

    with pytest.raises(ValueError, match="name must begin with on_"):

        def non_get1(req: Any, resp: Any, *, foo: str, dt: datetime.datetime):
            return None

        router.add(Route("") / "base" / {"foo"} / {"dt": datetime.datetime}, POST=non_get1)

    with pytest.raises(ValueError, match="no matching argument"):
        router.add(Route("") / "base" / {"dt": datetime.datetime}, POST=on_get1)

    with pytest.raises(ValueError, match="type annotation mismatch"):
        router.add(Route("") / "base" / {"foo"} / {"dt": int}, POST=on_get1)

    with pytest.raises(ValueError, match="type annotation mismatch"):
        router.add(Route("") / "base" / {"foo"} / {"dt": int}, POST=on_get1)

    with pytest.raises(ValueError, match="wrong req parameter"):

        def on_get_bad_req(*, req: Any, resp: Any, foo: str, dt: datetime.datetime):
            return None

        router.add(Route("") / "base" / {"foo"} / {"dt": int}, POST=on_get_bad_req)  # type: ignore

    with pytest.raises(ValueError, match="wrong resp parameter"):

        def on_get_bad_resp(req: Any, *, foo: str, dt: datetime.datetime):
            return None

        router.add(Route("") / "base" / {"foo"} / {"dt": int}, POST=on_get_bad_resp)  # type: ignore

    with pytest.raises(ValueError, match="must have no default"):

        def on_get_bad_kw(req: Any, resp: Any, *, foo: str = "1", dt: datetime.datetime):
            return None

        router.add(Route("") / "base" / {"foo"} / {"dt": int}, POST=on_get_bad_kw)
