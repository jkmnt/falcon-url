# falcon-url

This is an extension to the [Falcon](https://github.com/falconry/falcon) web framework for all of us missing Flask-like `url_for`.

Despite being REST-first framework, Falcon is good for traditional HTML too. Even json endpoints ocassionaly need to return hyperlinks.
Lack of `url_for` really make the URL composing cumbersome and error-prone.

`falcon-url` provides custom router and a few classes representing URLs and routes.
Router subclasses the Falcon's default one, augumenting a few methods. All routing is still handled by the Falcon.

# Installation

falcon-url is not on a PyPI yet. Download and install it locally.

# Basic usage

If you just want to upgrade your existing project:

```python
from falcon import App, Request, Response
from falcon_url import Router


class Thing:
    def on_get(self, req: Request, resp: Response, *, thing_id: int, foo: str): ...
    def on_post(self, req: Request, resp: Response, *, thing_id: int, foo: str): ...


router = Router()
app = App(router=router)

thing_ep = Thing()

thing_route = router.add_route("/api/{thing_id:int}/{foo}", thing_ep)

url = thing_route(thing_id=1, foo="bar")
print(url)  # /api/1/bar

url = url.with_query(a=1, b=2, c=["baz", " jazz"], d=True, e=False, f=None)
print(url)  # /api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false

url = url.with_fragment("article")
print(url)  # /api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false#article

url = url.with_root("/subapp")
print(url)  # /subapp/api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false#article

url = url.with_location("http://www.example.com")
print(url)  # http://www.example.com/subapp/api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false#article

print(url.as_html()) # http://www.example.com/subapp/api/1/bar?a=1&amp;b=2&amp;c=baz&amp;c=+jazz&amp;d=true&amp;e=false#article

```

Router returns the route object as a by-product of route addition. Calling it with parameters produce the concrete URL object.

URL objects are immutable and behave similar to the `pathlib.Path` objects. They even overload the division operator same way.

# Advanced usage

## Verification

Pass `strict` flag to the router to verify the routes. Makes sense to enable it in debug mode of your app.

```python
router = Router(strict=True)
router.add_route("/api/{thing_id:int}/{foo:int}", thing_ep)
# ValueError: type annotation mismatch for parameter foo (<class 'str'> vs <class 'int'>)
```

Router will check if responders arguments and route parameters match. It checks the names and types, so please type-annotate your arguments. All route-related arguments should be keyword-only.

## Typechecking and IDE autocomplete

There is no way to obtain signature of responder from the resource class.
But you could specify it manually. Your IDE will start to suggest parameters in a magical way.

Also you may specialize the request and response type for more type-safety.

```python

router = Router[falcon.Request, falcon.Response](strict=True)

thing_route = router.add_route("/api/{thing_id:int}/{foo}", thing_ep, typical_responder=thing_ep.on_get)

url = thing_route(foo=1) # Argument missing for parameter "thing_id"

```

## Explicit responders-methods mapping

```python
thing_route = router.add("/api/{thing_id:int}/{foo}", GET=thing_ep.on_get, POST=thing_ep.on_post)
```

This style of route registration is a good fit for HTML endpoints. You could map same form handler to both `GET` and `POST` methods and check the concrete method inside the responder body.

```python
 def on_getpost_create(self, req: Request, resp: Response):
    form = CreateThingForm()

    if req.method == "POST":
        form.fill_from(req)

        if form.validate():
            raise HTTPSeeOther(<url of new location>)
    else:
        form.default()

    resp.text = render_some_html(form)
```

Responders may belong the the different classes. Or even be standalone functions.
Since reponders signatures are known, this style is typesafe out of the box.
Also you may use it instead of the suffixed responders.

_Side-note_: there are a lot of ways to generate HTML without Jinja or Django templates.
See [htmf](github.com/jkmnt/htmf) project of mine :-)

## Object-oriented routes

`pathlib.Path`strikes again:

```python

from falcon_url import Route

api_root = Route("") / "api"
router.add(api_root / {"thing_id":int} / {"foo"}, GET=thing_ep.on_get)
router.add(api_root / "db" / {"table"}, GET=table_ep.on_get)

```

Or, almost the same without set/dict syntax hacks:

```python
from falcon_url import Router, param

router.add(api_root / param.Int("thing_id", max=12) / param.Str("foo"), GET=thing_ep.on_get)
```

In fact, it's the internal representation of routes in `falcon-url`.
The classic string templates are parsed into these route objects.

You may use them directly to get more type-safety and reduce the parsing overhead.

## Passing routes around the app

You are free to organize the routes store any way you like.

The simplest way is to have a global registry dict.

The recommended way is to store them in your app instance and pass the reference to all endpoints:

```python
from falcon_url import RoutesCollection

class BaseEp:
    def __init__(self, app: MyApp):
        self.app = app

class Ep(BaseEp):
    def on_get(self, req: Request, resp: Response, *, thing_id: int):
        # Accessing another endpoints route !
        url = self.app.routes.another_ep(foo="bar")

class AnotherEp(BaseEp):
    def on_get(self, req: Request, resp: Response, *, foo: str):
        url = self.app.routes.ep(thing_id=1)

class MyApp:
    def __init__(self):
        ep = Ep(self)
        another_ep = AnotherEp(self)

        router = Router()
        self.falcon = falcon.App(router=router)

        class Routes(RoutesCollection):
            ep = router.add(Route("") / "api" / "things" / {"thing_id": int}, GET=ep.on_get)
            another_ep = router.add(Route("") / "api" / "another" / {"foo"}, GET=another_ep.on_get)

        self.routes = Routes

```

Or, maybe, let endpoints manage their own routes ?

```python
class Ep:
    def __init__(self, app: MyApp, mount: Route, router: Router):
        self.app = app
        self.route_for_on_get = router.add(mount / {"thing_id": int})


class MyApp:
    def __init__(self):
        router = Router()
        mount = Route("") / "api"

        class Endpoints:
            ep = Ep(self, root, router)
            another_ep = AnotherEp(self, root, router)

        self.endpoints = Endpoints
```

This pattern allows to capture fully-typed route objects without 'identifiers' and other magic.

See next topic for explanation why it's beneficial to base `Routes` on `RoutesCollection`.

# Subpath support

If you need to host your app at some subpath, WSGI-compliant server will help you.
Server strips the subpath prefix from the incoming requests, so your app routes are not affected.
But now your app should append this prefix to the generated URLs in responses.
Falcon exposes incoming subpath prefix via `Request.root_path` attribute.
Yes, your URLs may vary depending on a request!

This simplest way is to set prefix manually via `URL.with_root`:

```python
def on_get(self, req: Request, resp: Response, *, thing_id: int):
    url = self.app.routes.another_ep(foo="bar").with_root(req.root_path)
```

It works ok if you have just a few URLs to manage. If you need to render a lot of URLs in one response, it quicky
becomes cumbersome.

`falcon-url` provides a special support to make it easier.
Routes in `RoutesCollection` _class_ are request-independent. Routes in the `RoutesCollection` class _instance_
are request-specific.

```python
 def on_get(self, req: Request, resp: Response, *, thing_id: int):
    # now these routes have root path of the request
    req_specific_routes = self.app.routes(root_path=req.root_path)
    # including this one
    route = req_specific_routes.another_ep(foo="bar")
```

## Responders with extra non-route arguments

You may have responders with extra arguments not related to the route, e.g. injected by the decorator.
`falcon-url` (and typechecker) would complain about them.
One way to silence complains is to move them to the kwargs:

```python
def on_get(self, req: Request, resp: Response, *, thing_id: int, foo: str, **kwargs: Any): ...
```

The better way is to make the argument non-keyword and have a correctly typed decorator.

```python

def with_extra_arg[
    TCls: BaseEp, **P
](f: Callable[Concatenate[TCls, Request, Response, MyArg, P], None]) -> Callable[Concatenate[TCls, Request, Response, P], None]:
    @wraps(f)
    def _wrapper(self: TCls, req: Request, resp: Response, *args: P.args, **kwargs: P.kwargs):
        my_arg = make_my_arg(self, req, resp)
        return f(self, req, resp, my_arg, *args, **kwargs)

    return _wrapper


# Ok !
@with_extra_arg
def on_get(self, req: Request, resp: Response, my_arg: MyArg, *, thing_id: int, foo: str): ...
```

## Query parameters

You may get used to the Flask's `url_for` semantic of moving extra keywords in a query part of URL. It's a bad idea. You really should use `URL.with_query`.

If you have a lot of query parameters and want them to be type-safe, a recommended pattern is to wrap them in dataclass:

```python
@dataclass
class MyParams:
    a: int
    b: float
    c: str | None = None

    def as_query(self):
        return {"a": self.a, "b": self.b, "c": self.c}

    @classmethod
    def from_req(cls, req: Request):
        a = req.get_param_as_int("a", required=True)
        b = req.get_param_as_float("b", required=True)
        c = req.get_param("c")
        return cls(a, b, c)

class Ep:
    def on_get(self, req: Request, resp: Response, *, thing_id: str):
        q = MyParams.from_req(req)

        do_something(q.a, q.b, q.c)

ep = Ep()

route = router.add(Route("") / {"thing_id"}, GET=ep.on_get)
url = route(thing_id="foo").with_query(**MyParams(1, 2, "bar").as_query())
```

Later, if you decide parameters should be in request body, you'll just add another factory method to the `MyParams`:

``` python

@classmethod
def from_json(cls, req: Request):
    json = req.media
    a = json["a"]
    b = json["b"]
    ...
```

## ASGI support

The typing for ASGI responders is on the roadmap. Meanwhile, in runtime everything should be fine.
