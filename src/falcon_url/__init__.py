"""Falcon router with url_for-like support"""

__version__ = "0.1.0"

from . import param
from .route import (
    Route,
    RouteParam,
    RoutesCollection,
    RouteSegment,
)
from .router import Router, inspect_routes
from .url import Url

__all__ = [
    "Route",
    "RouteParam",
    "RouteSegment",
    "Router",
    "RoutesCollection",
    "Url",
    "inspect_routes",
    "param",
]
