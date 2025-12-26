import ast
import re
from typing import Any

from . import param
from .route import _KNOWN_PARAMS, Route, RouteParam, RouteSegment


class ArgParseError(ValueError):
    pass


def _process_ast_arg(expr: ast.expr):
    neg = False
    if isinstance(expr, ast.UnaryOp):
        if isinstance(expr.op, ast.USub):
            neg = True
        elif isinstance(expr.op, ast.UAdd):
            pass
        else:
            raise ArgParseError("unsupported op", expr.op)
        value = expr.operand
    else:
        value = expr
    if not isinstance(value, ast.Constant):
        raise ArgParseError("expected ast.Constant", value)
    if neg:
        if not isinstance(value.value, (int, float)):
            raise ArgParseError("can't negate", value.value)
        return -value.value
    return value.value


def _parse_args(spec: str):
    params: list[Any] = []
    kw_params: dict[str, Any] = {}

    m = ast.parse(spec)
    body = m.body
    if len(body) != 1:
        raise ArgParseError()
    expr = body[0]
    if not isinstance(expr, ast.Expr):
        raise ArgParseError("expected ast.Expr", expr)
    expr_val = expr.value
    if isinstance(expr_val, ast.Name):
        cls = _KNOWN_PARAMS[expr_val.id]
    elif isinstance(expr_val, ast.Call):
        func = expr_val.func
        if not isinstance(func, ast.Name):
            raise ArgParseError("expected ast.Name", func)
        cls = _KNOWN_PARAMS[func.id]
        for arg in expr_val.args:
            value = _process_ast_arg(arg)
            params.append(value)

        for kw in expr_val.keywords:
            if kw.arg is None:
                raise ArgParseError("unexpected None")
            name = kw.arg
            value = _process_ast_arg(kw.value)
            kw_params[name] = value
    else:
        raise ArgParseError()

    return (cls, params, kw_params)


def _parse_param(template: str) -> RouteParam:
    splits = template.split(":")
    name = splits[0].strip()
    if len(splits) > 2:
        raise ArgParseError("Can't parse param")
    if len(splits) == 1:
        return param.Str(name)

    cls, args, kwargs = _parse_args(splits[1])
    return cls(name, *args, **kwargs)


def parse_template(template: str) -> Route:
    """Falcon template -> Route parser"""
    str_segments = template.split("/")

    pattern = re.compile(r"\{(.*?)\}")

    segments: list[RouteSegment] = []

    for str_seg in str_segments:
        str_parts = pattern.split(str_seg)
        parts: list[str | RouteParam] = []
        for i, str_part in enumerate(str_parts):
            assert isinstance(str_part, str)
            if i and not str_part:
                continue
            part = _parse_param(str_part) if i % 2 else str_part
            parts.append(part)
        segment = RouteSegment.from_parts(tuple(parts))
        segments.append(segment)
    return Route(*segments)
