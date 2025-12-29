# falcon-url

You like the [Falcon web framework](https://github.com/falconry/falcon) but miss the `url_for`?
Miss no longer!

`falcon-url` provides a custom router and a few URL-representing classes.
The router really just adds a few methods to the stock one, so the core routing is unaffected.

# Installation

```shell
pip install falcon-url
```

# Basic usage

If you just want to upgrade an existing project:

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
print(url)
# /api/1/bar

url = url.with_query(a=1, b=2, c=["baz", " jazz"], d=True, e=False, f=None)
print(url)
# /api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false

url = url.with_fragment("article")
print(url)
# /api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false#article

url = url.with_root("/subapp")
print(url)
# /subapp/api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false#article

url = url.with_location("http://www.example.com")
print(url)
# http://www.example.com/subapp/api/1/bar?a=1&b=2&c=baz&c=+jazz&d=true&e=false#article

print(url.as_html())
# http://www.example.com/subapp/api/1/bar?a=1&amp;b=2&amp;c=baz&amp;c=+jazz&amp;d=true&amp;e=false#article

```

The router returns the route object as a by-product of route addition. Calling it with parameters produces the concrete URL object.

URL objects are immutable and behave similarly to the `pathlib.Path` objects.

**NOTE**: Registration via `app.add_route` won't work.
Use the router directly.

# Advanced usage

## Verification

Pass a `strict` flag to the router to enable extra checks.
It makes sense to enable it in debug mode of your app.

```python
router = Router(strict=True)
router.add_route("/api/{thing_id:int}/{foo:int}", thing_ep)
# ValueError: type annotation mismatch for parameter foo (<class 'str'> vs <class 'int'>)
```

The router will check if method arguments and route parameters match.
Types are checked too, so please add type annotations. All route-related arguments should be keyword-only.

## Type checking and code editor autocomplete

`falcom-url` binds the route object to the responder's signature. It means the route is type-safe, and your code editor is able to suggest parameters and offer autocompletion.

For more type safety, you should specialize the request, response, and return type:

```python
router = Router[falcon.Request, falcon.Response, None](strict=True)

thing_route = router.add_route("/api/{thing_id:int}/{foo}", thing_ep)

reveal_type(thing_route) # pyright: Type of "thing_route" is "BoundRoute[(*, thing_id: int, foo: str)]

thing_route(foo="yyy") # pyright: Argument missing for parameter "thing_id"
thing_route(thing_id="xxx", foo="yyy") # pyright: Argument of type "Literal['xxx']" cannot be assigned to parameter "thing_id" of type "int"
```

Matching ASGI responders:

```python
class SyncThing:
    def on_get(self, req: Request, resp: Response, *, thing_id: int, foo: str) -> None: ...

class AsyncThing:
    async def on_get(self, req: Request, resp: Response, *, thing_id: int, foo: str) -> None: ...

sync_thing = SyncThing()
async_thing = AsyncThing()

router = Router[asgi.Request, asgi.Response, Awaitable[None]]()

router.add_route("/api/{thing_id:int}/{foo}", async_thing) # Ok

router.add_route("/api/{thing_id:int}/{foo}", sync_thing) # pyright: Argument of type "SyncThing" cannot be assigned to parameter "resource" of type ...

```

## Explicit responder-method mapping

`falcon-url` has an alternative mechanism of route registration with explicitly associated HTTP verbs and responders:

```python
thing_route = router.add("/api/{thing_id:int}/{foo}", GET=thing_ep.on_get, POST=thing_ep.on_post)
```

This style of route registration is a good fit for HTML endpoints.
Sometimes it's handy to have the same responder for both `GET` and `POST`:

```python
 def on_getpost_create_thing(self, req: Request, resp: Response):
    form = CreateThingForm()

    if req.method == "POST":
        form.fill_from(req)

        if form.validate():
            raise HTTPSeeOther(<url of new location>)
    else:
        form.default()

    resp.text = render_some_html(form)
```

_Promotion time_: Want to generate HTML in Python without Jinja templates?
Check out [htmf](https://github.com/jkmnt/htmf) project of mine :-)

Responders may belong to the different classes, or even be standalone functions.

## Object-oriented routes

The `pathlib.Path` strikes again:

```python
from falcon_url import Route

api_root = Route("") / "api" / "v2"
router.add_route(api_root / {"thing_id":int} / {"foo"}, thing_ep)
router.add_route(api_root / "db" / {"table"}, table_ep)
```

Or, almost the same without set/dict syntax hacks:

```python
from falcon_url import Router, param

router.add_route(api_root / param.Int("thing_id", max=12) / param.Str("foo"), thing_ep)
```

In fact, it's the internal representation of routes in `falcon-url`.
The classic string templates are parsed into these route objects.
You may use them directly for more type safety and reduced parsing overhead.

## Passing routes around the app

You are free to organize the route store any way you like.

The simple way is to keep a global dict-based registry.

The recommended way is to store routes in your app instance and pass the reference to endpoints:

```python
from falcon_url import RoutesCollection

class BaseEp:
    def __init__(self, app: MyApp):
        self.app = app

class ThingEp(BaseEp):
    def on_get(self, req: Request, resp: Response, *, thing_id: int):
        # Accessing another endpoint's route !
        url = self.app.routes.another(foo="bar")

class AnotherEp(BaseEp):
    def on_get(self, req: Request, resp: Response, *, foo: str):
        url = self.app.routes.thing(thing_id=1)

class MyApp:
    def __init__(self):
        thing_ep = ThingEp(self)
        another_ep = AnotherEp(self)

        router = Router()
        self.falcon = falcon.App(router=router)

        class Routes(RoutesCollection):
            thing = router.add(Route("") / "api" / "things" / {"thing_id": int}, GET=thing_ep.on_get)
            another = router.add(Route("") / "api" / "another" / {"foo"}, GET=another_ep.on_get)

        self.routes = Routes
```

Or, maybe, let endpoints manage their own routes?

```python
class ThingEp:
    def __init__(self, app: MyApp, mount: Route, router: Router):
        self.app = app
        self.route_for_on_get = router.add(mount / {"thing_id": int})


class MyApp:
    def __init__(self):
        router = Router()
        mount = Route("") / "api" / "v2"

        class Endpoints:
            ep = ThingEp(self, root, router)
            another_ep = AnotherEp(self, root, router)

        self.endpoints = Endpoints
```

These patterns let us have well-typed route objects in an always-in-sync store.

See the next topic for an explanation of why it's beneficial to base `Routes` on `RoutesCollection`.

# Subpath support

If you need to host your app under a subpath, any WSGI-compliant server has this feature built in.
Basically, it strips the subpath prefix from the incoming requests, making your app's routes unaffected.
On the outgoing side, your app should append this prefix to the generated URLs.

Falcon exposes the subpath prefix via the `Request.root_path` attribute.
Yes, your generated URLs may vary depending on a request!

Prefix may be set manually via `URL.with_root`. It's fine for managing a small number of URLs.

```python
def on_get(self, req: Request, resp: Response, *, thing_id: int):
    url = self.app.routes.another_ep(foo="bar").with_root(req.root_path)
```

For more hyperlink-heavy responses, `falcon-url` has a feature to make it easier.
Routes in the `RoutesCollection` _class_ are request-independent. Routes in the `RoutesCollection` class _instance_
are request-specific.

```python
def on_get(self, req: Request, resp: Response, *, thing_id: int):
    # now these routes have the root_path of the request
    req_specific_routes = self.app.routes(root_path=req.root_path)
    # including this one
    route = req_specific_routes.another_ep(foo="bar")
```

## Responders with extra non-route arguments

You may have responders with extra arguments not related to the route, for example, injected by the decorator.
`falcon-url` (and typechecker) would complain about them.
One way to silence complaints is to use the kwargs.

```python

def on_get(self, req: Request, resp: Response, *, thing_id: int, foo: str, **kwargs: Any): ...
```

Or make the argument non-keyword and ensure the decorator is typed correctly [unreadable enough]:

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

You may expect the URL object to accept unknown extra keywords and render them in a query part, as Flask's `url_for` does.
It's a bad idea. One shouldn't mix URL segments and parameters.

If query parameters are important enough, the recommended pattern is to use a dataclass:

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

Bonus feature: later, if you decide to transport parameters in a request body, just add another factory method:

```python

@classmethod
def from_json(cls, req: Request):
    json = req.media
    a = json["a"]
    b = json["b"]
    ...
```
