"""Route param formatters. They match the built-in falcon converters"""

import datetime
import uuid
from typing import Final

from .route import RouteParam


class Str(RouteParam, id="", anno=str, shortcut=str):
    """Route parameter: string"""

    def __str__(self):
        return f"{{{self.id}}}"

    def interpolate(self, val: str):
        return val


class Int(RouteParam, id="int", anno=int, shortcut=int):
    """Route parameter: int"""

    __slots__ = ("max", "min", "num_digits")

    def __init__(
        self,
        id: str,
        num_digits: int | None = None,
        min: int | None = None,
        max: int | None = None,
    ) -> None:
        super().__init__(id)
        self.min: Final = min
        self.max: Final = max
        self.num_digits: Final = num_digits

    def get_cfg(self) -> list[str | None]:
        return [
            str(self.num_digits) if self.num_digits else None,
            f"min={self.min}" if self.min is not None else None,
            f"max={self.max}" if self.max is not None else None,
        ]

    def interpolate(self, val: int):
        return str(int(val))


class Float(RouteParam, id="float", anno=float, shortcut=float):
    """Route parameter: float"""

    __slots__ = ("finite", "max", "min")

    def __init__(
        self,
        id: str,
        min: float | None = None,
        max: float | None = None,
        finite: bool = True,  # noqa FBT001
    ):
        super().__init__(id)
        self.min: Final = min
        self.max: Final = max
        self.finite: Final = finite

    def get_cfg(self) -> list[str | None]:
        return [
            f"min={self.min}" if self.min is not None else None,
            f"max={self.max}" if self.max is not None else None,
            "finite=False" if not self.finite else None,
        ]

    def interpolate(self, val: float):
        return str(float(val))


class Uuid(RouteParam, id="uuid", anno=uuid.UUID, shortcut=uuid.UUID):
    """Route parameter: uuid"""

    def interpolate(self, val: uuid.UUID):
        return str(val)


class Datetime(RouteParam, id="dt", anno=datetime.datetime, shortcut=datetime.datetime):
    """Route parameter: datetime"""

    __slots__ = "format_string"

    def __init__(
        self,
        id: str,
        format_string: str | None = None,
    ):
        super().__init__(id)
        self.format_string: Final = format_string

    def get_cfg(self) -> list[str | None]:
        return [f'"{self.format_string}"' if self.format_string else None]

    def interpolate(self, val: datetime.datetime):
        return val.strftime(self.format_string or "%Y-%m-%dT%H:%M:%S%z")


class Path(RouteParam, id="path", anno=str, is_multisegment=True):
    """Route parameter: path. Consumes all remaining segments"""

    def interpolate(self, val: str):
        return val
