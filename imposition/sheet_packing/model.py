"""Immutable native-millimetre contracts for rectangular packing."""

import math
from dataclasses import dataclass
from numbers import Real

EPS = 1e-7


def number(value, name):
    try:
        valid = not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} requires a finite number")
    return float(value)


def identifier(value, max_length=200):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"object/instance ID requires 1..{max_length} nonblank characters")
    return value


@dataclass(frozen=True)
class RectMM:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        for key in ("x", "y", "width", "height"):
            object.__setattr__(self, key, number(getattr(self, key), key))
        if (
            self.width <= 0
            or self.height <= 0
            or not all(math.isfinite(v) for v in (self.right, self.bottom))
        ):
            raise ValueError("rectangle requires positive finite extents")

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def contains(self, other):
        return (
            self.x - EPS <= other.x
            and self.y - EPS <= other.y
            and self.right + EPS >= other.right
            and self.bottom + EPS >= other.bottom
        )

    def intersects(self, other):
        return (
            self.x < other.right - EPS
            and other.x < self.right - EPS
            and self.y < other.bottom - EPS
            and other.y < self.bottom - EPS
        )


def ring(points):
    if not isinstance(points, (tuple, list)) or not 3 <= len(points) <= 10000:
        raise ValueError("polygon ring requires 3..10000 points")
    copied = []
    for point in points:
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            raise ValueError("polygon point requires XY")
        copied.append(tuple(number(v, "coordinate") for v in point))
    result = tuple(copied)
    if len(set(result)) < 3:
        raise ValueError("polygon requires distinct points")
    return result


@dataclass(frozen=True)
class PolygonRegion:
    outer: tuple
    holes: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "outer", ring(self.outer))
        if not isinstance(self.holes, (tuple, list)):
            raise ValueError("holes require a sequence")
        object.__setattr__(self, "holes", tuple(ring(h) for h in self.holes))


@dataclass(frozen=True)
class ObjectFootprint:
    object_id: str
    trim_regions: tuple
    occupied_bounds: RectMM
    rotations: tuple

    def __post_init__(self):
        identifier(self.object_id)
        if not isinstance(self.occupied_bounds, RectMM):
            raise ValueError("occupied bounds require RectMM")
        if not isinstance(self.trim_regions, (tuple, list)) or not all(
            isinstance(r, PolygonRegion) for r in self.trim_regions
        ):
            raise ValueError("trim regions require PolygonRegion records")
        object.__setattr__(self, "trim_regions", tuple(self.trim_regions))
        angles = self.rotations
        if (
            not isinstance(angles, (list, tuple))
            or not angles
            or any(type(v) is not int or v not in (0, 90) for v in angles)
            or len(set(angles)) != len(angles)
        ):
            raise ValueError("rotations require a nonempty unique subset of [0,90]")
        object.__setattr__(self, "rotations", tuple(sorted(angles)))
        b = self.occupied_bounds
        if any(
            not (b.x - EPS <= x <= b.right + EPS and b.y - EPS <= y <= b.bottom + EPS)
            for r in self.trim_regions
            for x, y in r.outer
        ):
            raise ValueError("occupied bounds must contain trim geometry")


@dataclass(frozen=True)
class PackingInstance:
    instance_id: str
    footprint: ObjectFootprint

    def __post_init__(self):
        identifier(self.instance_id, max_length=205)
        if not isinstance(self.footprint, ObjectFootprint):
            raise ValueError("instance requires ObjectFootprint")


@dataclass(frozen=True)
class SheetArea:
    width_mm: float
    height_mm: float
    usable_front: RectMM
    usable_back: RectMM | None = None
    margins: tuple = (0, 0, 0, 0)
    faces: str = "front"
    flip: str | None = None

    def __post_init__(self):
        for key in ("width_mm", "height_mm"):
            v = number(getattr(self, key), key)
            if not 0 < v <= 1e6:
                raise ValueError("sheet dimensions require 0..1e6 mm")
            object.__setattr__(self, key, v)
        if not isinstance(self.usable_front, RectMM):
            raise ValueError("usable front rectangle requires RectMM")
        if self.faces not in ("front", "both") or (
            self.faces == "front" and (self.flip is not None or self.usable_back is not None)
        ):
            raise ValueError("invalid sheet face/flip selection")
        if self.faces == "both":
            if self.flip not in ("left-right", "top-bottom"):
                raise ValueError("paired sheet requires a flip")
            if self.usable_back is None:
                object.__setattr__(self, "usable_back", self.usable_front)
        physical = RectMM(0, 0, self.width_mm, self.height_mm)
        for rect in (self.usable_front, self.usable_back):
            if rect is not None and (not isinstance(rect, RectMM) or not physical.contains(rect)):
                raise ValueError("usable rectangle must be inside sheet")
        if not isinstance(self.margins, (list, tuple)) or len(self.margins) != 4:
            raise ValueError("margins require top/right/bottom/left")
        values = tuple(number(v, "margin") for v in self.margins)
        if min(values) < 0:
            raise ValueError("margins must be nonnegative")
        object.__setattr__(self, "margins", values)


@dataclass(frozen=True)
class PackedInstance:
    instance_id: str
    sheet_index: int
    rotation: int
    front_matrix: tuple
    occupied_bounds: RectMM

    def __post_init__(self):
        identifier(self.instance_id, max_length=205)
        if type(self.sheet_index) is not int or self.sheet_index < 0:
            raise ValueError("invalid sheet index")
        if type(self.rotation) is not int or self.rotation not in (0, 90):
            raise ValueError("invalid packed rotation")
        if not isinstance(self.front_matrix, (tuple, list)) or len(self.front_matrix) != 6:
            raise ValueError("matrix requires six numbers")
        object.__setattr__(
            self, "front_matrix", tuple(number(v, "matrix") for v in self.front_matrix)
        )
        if not isinstance(self.occupied_bounds, RectMM):
            raise ValueError("packed bounds require RectMM")


@dataclass(frozen=True)
class PackingResult:
    strategy: str
    placements: tuple
    sheet_count: int

    def __post_init__(self):
        if self.strategy not in ("grid", "maxrects"):
            raise ValueError("invalid resolved strategy")
        if type(self.sheet_count) is not int or self.sheet_count <= 0:
            raise ValueError("invalid sheet count")
        if not isinstance(self.placements, (tuple, list)) or not all(
            isinstance(p, PackedInstance) for p in self.placements
        ):
            raise ValueError("placements require packed records")
        object.__setattr__(self, "placements", tuple(self.placements))
