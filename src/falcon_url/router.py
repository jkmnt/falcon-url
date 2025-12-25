from typing import Any, Awaitable, Callable, Concatenate, Final, final

from falcon import App, Request, Response
from falcon.asgi import Request as AsgiRequest
from falcon.asgi import Response as AsgiResponse
from falcon.routing.compiled import CompiledRouter

from .route import BoundRoute, Route

type Responder[TReq: Request, TResp: Response, **P] = Callable[Concatenate[TReq, TResp, P], None]

type AsgiResponder[TReq: AsgiRequest, TResp: AsgiResponse, **P] = Callable[
    Concatenate[TReq, TResp, P], None | Awaitable[None]
]


@final
class CatchallResource:
    pass


_catchall_resource: Final = CatchallResource()


def _parse_template(template: str):
    # do not import until really required
    from .template import parse_template

    return parse_template(template)


def _validate_responder(meth: str, handler: Callable[..., Any], route: Route):
    import inspect
    from inspect import Parameter

    sig = inspect.signature(handler, eval_str=True)
    params = sig.parameters.values()

    name = handler.__name__
    if not name.startswith("on_"):
        raise ValueError("name must begin with on_")

    route_args = route._get_params()
    # first two params are req, resp
    # last param may be **kwargs
    req, resp, *responder_params = params

    # req, resp should be positional or positional-or-keyword
    if not (
        req.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD) and req.default == Parameter.empty
    ):
        raise TypeError("wrong req parameter")

    if not (
        resp.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD) and resp.default == Parameter.empty
    ):
        raise TypeError("wrong resp parameter")

    # route arguments are keyword-only
    responder_params = [r for r in responder_params if r.kind == Parameter.KEYWORD_ONLY]

    # the args and params must match exactly, though may be in different order
    argset = {arg.id for arg in route_args}
    parset = {param.name for param in responder_params}
    diff = argset ^ parset
    if diff:
        raise ValueError(f"no matching argument and keyword-parameter: {sorted(diff)}")

    for arg in route_args:
        param = next(p for p in responder_params if p.name == arg.id)

        if param.default != Parameter.empty:
            raise TypeError(f"parameter {param.name} must have no default value")
        anno = param.annotation
        if anno == Parameter.empty:
            raise ValueError(f"missing type annotation for parameter {param.name}")
        if anno != arg._anno:
            raise ValueError(f"type annotation mismatch for parameter {param.name} ({anno} vs {arg._anno})")


# TODO: support ASGI responders type ?


class Router[TReq: Request, TResp: Response](CompiledRouter):
    """
    Note: the router class really should be type-specialized to get the
    responder signatures checking.
    """

    def __init__(self, *, strict: bool = False) -> None:
        super().__init__()
        self._strict = strict

    def add_route[
        **P
    ](
        self,
        route: Route | str,
        resource: object,
        *,
        typical_responder: Responder[TReq, TResp, P] | None = None,
        **kwargs: Any,
    ) -> BoundRoute[P]:
        """Add route to resource with autodetected methods.
        Supply extra typing-only argument `typical_responder` to have a typed URL in return.
        """
        if isinstance(route, str):
            route = _parse_template(route)

        if not str(route).startswith("/"):
            raise ValueError(f"route must begin with slash ({route!s})")

        if self._strict:
            methods = super().map_http_methods(resource, **kwargs)
            for http_method, responder in methods.items():
                _validate_responder(http_method, responder, route)

        super().add_route(str(route), resource, **kwargs)
        return BoundRoute[P](route)

    def add[
        **P
    ](
        self,
        route: Route | str,
        *,
        # most common methods here. other (webdav etc) are via kwargs
        GET: Responder[TReq, TResp, P] | None = None,
        POST: Responder[TReq, TResp, P] | None = None,
        PUT: Responder[TReq, TResp, P] | None = None,
        DELETE: Responder[TReq, TResp, P] | None = None,
        OPTIONS: Responder[TReq, TResp, P] | None = None,
        **responders: Responder[TReq, TResp, P] | None,
    ) -> BoundRoute[P]:
        """Register route with the provided responders.
        Returns BoundRoute, allowing to render URL ala url_for().
        Caller should keep result if intends to interpolate this route.

        There is a little typing quirk: signatures of all responders must match.
        In principle, they should. In practice, the may have extra kwarg
        arguments supplied by the decorators or middleware.

        Maybe this restriction could be lifted in the future.
        """
        if isinstance(route, str):
            route = _parse_template(route)

        template = str(route)

        if not template.startswith("/"):
            raise ValueError(f"route must begin with slash ({template})")

        # collect all handlers from explicit args, then group by resources
        by_meth = {
            "GET": GET,
            "POST": POST,
            "PUT": PUT,
            "DELETE": DELETE,
            "OPTIONS": OPTIONS,
            **responders,
        }

        by_resource: dict[object, dict[str, Responder[TReq, TResp, P]]] = {}
        for http_method, responder in by_meth.items():
            if responder:
                resource: object = getattr(responder, "__self__", _catchall_resource)
                by_resource.setdefault(resource, {})[http_method] = responder

        for resource, resps in by_resource.items():
            for http_method, responder in resps.items():
                if self._strict:
                    try:
                        _validate_responder(http_method, responder, route)
                    except Exception as e:
                        raise ValueError(f"Handler {responder} validation error: {e}") from e
            super().add_route(template, resource, _cooked=resps)

        return BoundRoute[P](route)

    def map_http_methods(
        self,
        resource: object,
        *,
        # for direct registration
        _cooked: dict[str, Callable[..., None]] | None = None,
        **kwargs: Any,
    ):
        if _cooked:
            return _cooked
        return super().map_http_methods(resource, **kwargs)

    def compile(self):
        # trigger compile
        self.find("")


def inspect_routes(app: App):
    import falcon.inspect

    try:
        falcon.inspect.register_router(type(app._router))(lambda router: falcon.inspect.inspect_compiled_router(router))
    except Exception:
        pass

    return falcon.inspect.inspect_app(app)
